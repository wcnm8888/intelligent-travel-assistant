"""Call-owned, in-memory local replanning; never persists or commits a job."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid5

from intelligent_travel_assistant.application.planning import (
    DeepSeekProposalResolver,
    ProposalResolution,
)
from intelligent_travel_assistant.application.planning.final_validation import (
    FinalValidationIssue,
    FinalValidationIssueCode,
    FinalValidationSeverity,
)
from intelligent_travel_assistant.application.planning.scheduling import SchedulingWarningCode
from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    ModelTextOutput,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningToolName,
    PlanRepairBrief,
    PoiSearchRequest,
    QWeatherPort,
    ReplanSelectionScope,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.application.services.offline_planning import (
    RouteLookupStage,
    _governed_call,
    _lookup_allows_fallback,
    _lookup_has_usable_route,
    _lookup_route,
    _RouteLookup,
)
from intelligent_travel_assistant.application.services.provider_planning_jobs import (
    _ISSUE_MESSAGES,
    _PROVIDER_ERROR_MESSAGES,
    _SCHEDULING_WARNING_MESSAGES,
    _cost_item,
    _provider_errors,
    _sources,
)
from intelligent_travel_assistant.application.services.replan_candidate import (
    ActivityReplacement,
    build_replan_candidate,
)
from intelligent_travel_assistant.application.services.replan_facts import (
    EvidencedReplanResult,
    EvidenceEvent,
    ReplanEvidence,
    ReplanFactProjector,
    ReplanFacts,
    _ids,
)
from intelligent_travel_assistant.application.tooling import (
    PacedAttemptLimiter,
    ProviderAttemptRuntime,
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
)
from intelligent_travel_assistant.application.tooling.resilience import ProviderRunSession
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    CostItem,
    LocationRef,
    Money,
    PlanDay,
    PlanningStatus,
    ProviderName,
    RouteLeg,
    SourceRecord,
    TripPlanRequest,
    TripPlanRequestV2,
    Uncertainty,
    WeatherAlert,
    WeatherSnapshot,
)
from intelligent_travel_assistant.domain import (
    BudgetCostItem as DomainBudgetCostItem,
)
from intelligent_travel_assistant.domain import (
    BudgetSummaryResult,
    Coordinates,
    CoordinateSystem,
    CostCategory,
    CostConfidence,
    DataFreshness,
    DomainInvariantError,
    Provider,
    ProviderOperation,
    ProviderResult,
    ProviderResultStatus,
    ReplaceActivity,
    ReplanStatus,
    RouteMode,
    evaluate_freshness,
    summarize_budget,
)
from intelligent_travel_assistant.domain import Money as DomainMoney


class ProviderReplanPlanner:
    def __init__(
        self,
        *,
        amap: AmapPort,
        route_limiter: PacedAttemptLimiter,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
        sleeper: Callable[[float], Awaitable[None]],
        jitter: Callable[[], float],
        deepseek: DeepSeekPort | None = None,
        qweather: QWeatherPort | None = None,
    ) -> None:
        self.run_session: ProviderRunSession | None = None
        self.amap, self.route_limiter = amap, route_limiter
        self.clock, self.monotonic = clock, monotonic
        self.sleeper, self.jitter = sleeper, jitter
        self.deepseek, self.qweather = deepseek, qweather

    async def execute(
        self, job: PlanningJob, replan: ReplanRecord
    ) -> EvidencedReplanResult | ReplanOutcome:
        session = self.run_session
        if session is None:
            return await self._execute_with_runtime(job, replan)
        try:
            async with session.execution("replan", replan.replan_request_id) as execution:
                result = await self._execute_with_runtime(job, replan, (session, execution))
        except ToolCallGovernanceError as error:
            result = _governance_outcome(error)
        except TimeoutError:
            result = _governance_outcome(
                ToolCallGovernanceError(ToolCallGovernanceErrorCode.TASK_TIMEOUT)
            )
        if isinstance(result, ReplanOutcome):
            session.business_failure()
        return result

    async def _execute_with_runtime(
        self,
        job: PlanningJob,
        replan: ReplanRecord,
        observation: tuple[ProviderRunSession, UUID] | None = None,
    ) -> EvidencedReplanResult | ReplanOutcome:
        runtime = ProviderAttemptRuntime(
            clock=self.monotonic,
            sleeper=self.sleeper,
            jitter=self.jitter,
            task_timeout_seconds=90,
            attempt_limiter=self.route_limiter,
        )
        if observation is not None:
            runtime.bind_run(*observation)
        governor = ToolCallGovernor(clock=self.monotonic)
        try:
            return await self._execute(job, replan, governor, runtime)
        except asyncio.CancelledError:
            raise
        except ToolCallGovernanceError as error:
            return _governance_outcome(error)
        except (DomainInvariantError, ValueError, TypeError, AttributeError):
            return ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
        finally:
            await runtime.close()

    async def _execute(
        self,
        job: PlanningJob,
        replan: ReplanRecord,
        governor: ToolCallGovernor,
        runtime: ProviderAttemptRuntime,
    ) -> EvidencedReplanResult | ReplanOutcome:
        projector = ReplanFactProjector()
        at = self.clock()
        if not isinstance(job.request, TripPlanRequest) or not isinstance(
            job.result, PlanningJobResult
        ):
            return ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
        facts = projector.project(job.result, evaluated_at=at)
        if (
            replan.job_id != job.job_id
            or replan.expected_job_version != job.version
            or replan.baseline_plan_id != facts.plan.plan_id
            or replan.impact is None
        ):
            return ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
        events: list[EvidenceEvent] = []
        city_request = CityResolutionRequest(job.request.city)
        city_result: ProviderResult[CityResolution] | None = None
        replacement: ActivityReplacement | None = None
        model: ProposalResolution | None = None
        context: PlanningContext | None = None
        captured: _ModelCalls | None = None
        deepseek = self.deepseek
        if isinstance(replan.command, ReplaceActivity):
            if deepseek is None:
                return ReplanOutcome(ReplanStatus.FAILED, "internal_error")
            city_result = await _governed_call(
                governor,
                ToolCallCapability.RESOLVE_CITY,
                PlanningStatus.COLLECTING,
                lambda: self.amap.resolve_city(city_request),
                attempt_runtime=runtime,
                provider=Provider.AMAP,
                provider_operation=ProviderOperation.RESOLVE_CITY,
            )
            if city_result.data is None:
                return _required_outcome(city_result)
            target = facts.activities[replan.command.target_activity_id]
            baseline_location_ids_by_day = tuple(
                tuple(activity.location_id for activity in day.activities)
                for day in facts.plan.days
            )
            search = PoiSearchRequest(
                city_result.data.adcode,
                replan.command.replacement_categories,
                replan.command.replacement_categories,
                5,
            )
            pois = await _governed_call(
                governor,
                ToolCallCapability.SEARCH_POIS,
                PlanningStatus.COLLECTING,
                lambda: self.amap.search_pois(search),
                attempt_runtime=runtime,
                provider=Provider.AMAP,
                provider_operation=ProviderOperation.SEARCH_POIS,
            )
            candidates = (
                ()
                if pois.data is None
                else tuple(
                    p
                    for p in pois.data.candidates
                    # Retired locations still carry historical sources; replacing
                    # their facts would change objects outside this activity's scope.
                    if p.location_id not in facts.locations
                    and p.coordinates is not None
                    and p.city_adcode == facts.plan.city_adcode
                )[:5]
            )
            if not candidates:
                return _required_outcome(pois)
            poi_sources = _sources((pois,), job_id=job.job_id, evaluated_at=self.clock())[2:]
            candidate_locations = tuple(
                LocationRef(
                    **asdict(poi),
                    provider=ProviderName.AMAP,
                    source_ids=tuple(source.source_id for source in poi_sources),
                )
                for poi in candidates
            )
            local_date = facts.activity_days[target.item_id].local_date
            target_day_index = tuple(day.local_date for day in facts.plan.days).index(local_date)
            target_selection_index = tuple(
                activity.item_id for activity in facts.plan.days[target_day_index].activities
            ).index(target.item_id)
            anchor = facts.locations[facts.plan.days[0].accommodation_location_id]
            baseline_locations = tuple(
                facts.locations[location_id]
                for location_id in dict.fromkeys(
                    location_id for day in baseline_location_ids_by_day for location_id in day
                )
            )
            context = PlanningContext(
                city_result.data.city_name,
                facts.plan.city_adcode,
                facts.plan.start_date,
                facts.plan.end_date,
                job.request.travelers,
                DomainMoney(job.request.total_budget.amount),
                job.request.preferences.interests,
                job.request.preferences.hard_constraints,
                tuple(PlanningToolName),
                tuple(
                    PlanningLocation(
                        location.location_id, location.name, location.category, location.city_adcode
                    )
                    for location in (*baseline_locations, *candidate_locations)
                ),
                (),
                free_text=job.request.preferences.free_text,
                route_mode=RouteMode.PUBLIC_TRANSIT
                if any(m.value == "public_transit" for m in job.request.transport_modes)
                else RouteMode.WALKING,
                day_windows=tuple(
                    PlanningDayWindow(w.day_offset, w.start_time, w.end_time)
                    for w in job.request.day_windows
                ),
                accommodation=PlanningLocation(
                    anchor.location_id,
                    "accommodation anchor",
                    "accommodation_anchor",
                    anchor.city_adcode,
                ),
                activity_source_ids=_ids(
                    source_id
                    for location in (*baseline_locations, *candidate_locations)
                    for source_id in location.source_ids
                ),
                request_version="2" if isinstance(job.request, TripPlanRequestV2) else None,
                expected_dates=tuple(day.local_date for day in facts.plan.days)
                if isinstance(job.request, TripPlanRequestV2)
                else (),
                replan_selection_scope=ReplanSelectionScope(
                    target_activity_id=target.item_id,
                    target_local_date=local_date,
                    target_selection_index=target_selection_index,
                    baseline_location_ids_by_day=baseline_location_ids_by_day,
                    allowed_candidate_location_ids=tuple(
                        candidate.location_id for candidate in candidates
                    ),
                ),
            )
            captured = _ModelCalls(deepseek)
            model = await DeepSeekProposalResolver(captured).resolve(
                context, governor=governor, attempt_runtime=runtime
            )
            if model.error_code is not None:
                return ReplanOutcome(ReplanStatus.FAILED, model.error_code.value)
            if model.result.data is None:
                return _required_outcome(model.result)
            selected_location_id = (
                model.result.data.days[target_day_index]
                .selections[target_selection_index]
                .location_id
            )
            selected = next(
                candidate
                for candidate in candidates
                if candidate.location_id == selected_location_id
            )
            location = next(
                item for item in candidate_locations if item.location_id == selected_location_id
            )
            activity = target.model_copy(
                update={
                    "title": selected.name,
                    "location_id": selected.location_id,
                    "source_ids": location.source_ids,
                }
            )
            replacement = ActivityReplacement(local_date, activity, location, poi_sources)
            events.append(
                EvidenceEvent("location", local_date, (selected.location_id,), search, pois)
            )
        draft = build_replan_candidate(
            job,
            replan.command,
            replan.impact,
            evaluated_at=self.clock(),
            replacement=replacement,
        )
        sources = list(draft.sources)
        if city_result is not None:
            sources.extend(
                _sources((city_result,), job_id=job.job_id, evaluated_at=self.clock())[2:]
            )
        if replacement is not None:
            assert model is not None and model.result.data is not None
            if any(
                tuple(selection.location_id for selection in proposal_day.selections)
                != tuple(activity.location_id for activity in draft_day.activities)
                for proposal_day, draft_day in zip(model.result.data.days, draft.days, strict=True)
            ):
                return ReplanOutcome(ReplanStatus.FAILED, "model_output_invalid")
            sources.extend(
                _sources((model.result,), job_id=job.job_id, evaluated_at=self.clock())[2:]
            )
        days: list[PlanDay] = []
        mode = (
            RouteMode.PUBLIC_TRANSIT
            if any(m.value == "public_transit" for m in job.request.transport_modes)
            else RouteMode.WALKING
        )
        coordinates = {
            loc.location_id: Coordinates(
                loc.coordinates.longitude,
                loc.coordinates.latitude,
                CoordinateSystem(loc.coordinates.coordinate_system),
            )
            if loc.coordinates is not None
            else None
            for loc in draft.locations
        }
        requirement_indexes: dict[object, int] = {}
        for day in draft.days:
            routes: list[RouteLeg] = []
            local_refs: list[UUID] = []
            for edge in day.edges:
                existing_route = edge.route
                fresh = existing_route is not None and all(
                    facts.freshness[sid] is not DataFreshness.STALE
                    for sid in existing_route.source_ids
                )
                if fresh:
                    assert existing_route is not None
                    routes.append(existing_route)
                    continue
                if city_result is None:
                    city_result = await _governed_call(
                        governor,
                        ToolCallCapability.RESOLVE_CITY,
                        PlanningStatus.COLLECTING,
                        lambda: self.amap.resolve_city(city_request),
                        attempt_runtime=runtime,
                        provider=Provider.AMAP,
                        provider_operation=ProviderOperation.RESOLVE_CITY,
                    )
                    if (
                        city_result.data is None
                        or city_result.status is ProviderResultStatus.UNAVAILABLE
                    ):
                        return _required_outcome(city_result)
                    sources.extend(
                        _sources((city_result,), job_id=job.job_id, evaluated_at=self.clock())[2:]
                    )
                assert city_result.data is not None
                requirement_index = requirement_indexes.setdefault(
                    edge.requirement, len(requirement_indexes) + 1
                )
                lookup = await _lookup_route(
                    edge.requirement,
                    mode=mode,
                    stage=RouteLookupStage.PRIMARY,
                    requirement_index=requirement_index,
                    coordinates=coordinates,
                    citycode=city_result.data.citycode,
                    amap=self.amap,
                    governor=governor,
                    status=PlanningStatus.ENRICHING_ROUTES,
                    attempt_runtime=runtime,
                    evaluated_at=self.clock(),
                )
                primary = None
                if (
                    not _lookup_has_usable_route(lookup)
                    and _lookup_allows_fallback(lookup)
                    and mode is RouteMode.PUBLIC_TRANSIT
                    and any(m.value == "walking" for m in job.request.transport_modes)
                ):
                    primary = lookup.result
                    lookup = await _lookup_route(
                        edge.requirement,
                        mode=RouteMode.WALKING,
                        stage=RouteLookupStage.FALLBACK,
                        requirement_index=requirement_index,
                        coordinates=coordinates,
                        citycode=city_result.data.citycode,
                        amap=self.amap,
                        governor=governor,
                        status=PlanningStatus.ENRICHING_ROUTES,
                        attempt_runtime=runtime,
                        evaluated_at=self.clock(),
                    )
                if not _lookup_has_usable_route(lookup):
                    return _route_failure_outcome(lookup)
                assert lookup.result is not None and lookup.result.data is not None
                rid = (
                    existing_route.route_id
                    if existing_route is not None
                    else uuid5(replan.replan_id, f"route:{day.baseline.local_date}:{len(routes)}")
                )
                route = RouteLeg(route_id=rid, **asdict(lookup.result.data))
                routes.append(route)
                local_refs.append(rid)
                events.append(
                    EvidenceEvent(
                        "fallback" if primary else "route",
                        day.baseline.local_date,
                        (rid,),
                        lookup.request,
                        cast(ProviderResult[object], lookup.result),
                        primary=cast(ProviderResult[object] | None, primary),
                        city=city_result.data,
                    )
                )
                sources.extend(
                    _sources((lookup.result,), job_id=job.job_id, evaluated_at=self.clock())[2:]
                )
            if replacement is not None and day.baseline.local_date == replacement.local_date:
                assert model is not None and context is not None and captured is not None
                model_refs = _ids((*local_refs, replacement.activity.item_id))
                events.append(
                    EvidenceEvent(
                        "model_repair" if model.repaired else "model_generate",
                        replacement.local_date,
                        model_refs,
                        captured.repair if model.repaired else context,
                        cast(ProviderResult[object], model.result),
                        model_context=context if model.repaired else None,
                    )
                )
                local_refs.extend((*model_refs, replacement.location.location_id))
            if local_refs:
                assert city_result is not None and city_result.data is not None
                events.append(
                    EvidenceEvent(
                        "city",
                        day.baseline.local_date,
                        _ids(local_refs),
                        city_request,
                        cast(ProviderResult[object], city_result),
                    )
                )
            current_day = day.baseline.model_copy(
                update={"activities": day.activities, "routes": tuple(routes)}
            )
            roots = set(replan.impact.direct_refs) | set(replan.impact.route_refs)
            weather_refs = _ids(a.item_id for a in day.activities if a.item_id in roots)
            if not weather_refs:
                weather_refs = _ids(
                    r.route_id
                    for r, e in zip(routes, day.edges, strict=True)
                    if set(e.origin_refs) <= roots
                )
            if (
                self.qweather is not None
                and day.baseline.local_date in replan.impact.affected_dates
            ):
                current_day = await self._weather(
                    current_day, facts, weather_refs, governor, runtime, events, sources, job.job_id
                )
            if job.request.preferences.hard_constraints and weather_refs:
                events.append(
                    EvidenceEvent(
                        "constraint",
                        day.baseline.local_date,
                        weather_refs,
                        None,
                        FinalValidationIssue(
                            FinalValidationIssueCode.HARD_CONSTRAINT_UNVERIFIED,
                            FinalValidationSeverity.PARTIAL,
                        ),
                    )
                )
            days.append(current_day)
        # The conservative typed budget never invents a replacement quote or a zero fare.
        analysis_items = draft.budget_analysis.after.cost_items
        costs = {
            c.cost_id: facts.costs[c.cost_id].model_copy(
                update={
                    "confidence": type(facts.costs[c.cost_id].confidence)(c.confidence.value),
                    "amount": None if c.amount is None else Money(amount=c.amount.amount),
                }
            )
            if c.cost_id in facts.costs
            else _cost_item(c, job_id=job.job_id, trip_day_label="两日")
            for c in analysis_items
        }
        for i, plan_day in enumerate(days):
            activities = tuple(
                a.model_copy(
                    update={
                        "cost_items": tuple(
                            costs[c.cost_id] for c in a.cost_items if c.cost_id in costs
                        )
                        + (
                            tuple(c for cid, c in costs.items() if cid not in facts.costs)
                            if replacement is not None and a.item_id == replacement.activity.item_id
                            else ()
                        )
                    }
                )
                for a in plan_day.activities
            )
            days[i] = plan_day.model_copy(
                update={
                    "activities": activities,
                    "routes": tuple(
                        r.model_copy(update={"fare": costs.get(r.fare.cost_id)}) if r.fare else r
                        for r in plan_day.routes
                    ),
                }
            )
        budget = _candidate_budget(job.request.total_budget, tuple(costs.values()))
        summary = facts.plan.budget_summary.model_copy(
            update={
                "cost_items": tuple(costs.values()),
                "known_total": Money(amount=budget.known_total.amount),
                "unknown_count": budget.unknown_count,
                "assessment": type(facts.plan.budget_summary.assessment)(budget.assessment.value),
            }
        )
        scoped_cost_ids = set(draft.pending_cost_refs)
        budget_refs = _ids(
            cost.cost_id
            for cost in costs.values()
            if cost.confidence.value == "unknown"
            and (cost.cost_id in scoped_cost_ids or cost.cost_id not in facts.costs)
        )
        if budget_refs:
            events.append(
                EvidenceEvent(
                    "budget",
                    replan.impact.affected_dates[0],
                    budget_refs,
                    None,
                    budget,
                )
            )
        plan = facts.plan.model_copy(
            update={
                "plan_id": uuid5(replan.replan_id, "plan"),
                "locations": draft.locations,
                "days": tuple(days),
                "budget_summary": summary,
            }
        )
        result = replace(
            job.result, plan=plan, sources=tuple(sources), status=PlanningStatus.PARTIAL
        )
        result = _diagnostics(result, events, self.clock())
        provisional_evidence = ReplanEvidence.bind(
            job, replan.replan_id, replan.command, result, tuple(events)
        )
        result = projector.normalize_result(
            job,
            replan.command,
            replan.impact,
            result,
            evaluated_at=self.clock(),
            evidence=provisional_evidence,
        )
        evidence = ReplanEvidence.bind(job, replan.replan_id, replan.command, result, tuple(events))
        projector.changes(
            job, replan.command, replan.impact, result, evaluated_at=self.clock(), evidence=evidence
        )
        return EvidencedReplanResult(result, evidence)

    async def _weather(
        self,
        day: PlanDay,
        facts: ReplanFacts,
        refs: tuple[UUID, ...],
        governor: ToolCallGovernor,
        runtime: ProviderAttemptRuntime,
        events: list[EvidenceEvent],
        sources: list[SourceRecord],
        job_id: UUID,
    ) -> PlanDay:
        qweather = self.qweather
        assert qweather is not None
        old = day.weather
        old_ids = (
            () if old is None else (*old.source_ids, *(s for a in old.alerts for s in a.source_ids))
        )
        if old is not None and all(facts.freshness[s] is DataFreshness.FRESH for s in old_ids):
            return day
        lid = old.location_id if old is not None else day.accommodation_location_id
        loc = facts.locations[lid]
        if loc.coordinates is None:
            raise DomainInvariantError("replan_candidate_invalid", field="weather")
        coordinates = Coordinates(
            loc.coordinates.longitude,
            loc.coordinates.latitude,
            CoordinateSystem(loc.coordinates.coordinate_system),
        )
        forecast_start = day.local_date
        forecast_end = min(day.local_date + timedelta(days=6), facts.plan.end_date)
        if forecast_end == forecast_start:
            forecast_start = max(facts.plan.start_date, day.local_date - timedelta(days=1))
        requests = (
            WeatherForecastRequest(lid, coordinates, forecast_start, forecast_end),
            CurrentWeatherAlertsRequest(lid, coordinates),
        )
        weather = old
        calls: tuple[
            tuple[
                WeatherForecastRequest | CurrentWeatherAlertsRequest,
                str,
                ToolCallCapability,
                Callable[[], Awaitable[ProviderResult[Any]]],
            ],
            ...,
        ] = (
            (
                requests[0],
                "forecast",
                ToolCallCapability.GET_WEATHER_FORECAST,
                lambda: qweather.get_weather_forecast(requests[0]),
            ),
            (
                requests[1],
                "alerts",
                ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
                lambda: qweather.get_current_weather_alerts(requests[1]),
            ),
        )
        for request, operation, capability, invoke in calls:
            result = await _governed_call(
                governor,
                capability,
                PlanningStatus.COLLECTING,
                invoke,
                attempt_runtime=runtime,
                provider=Provider.QWEATHER,
                provider_operation=ProviderOperation.GET_WEATHER_FORECAST
                if operation == "forecast"
                else ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
            )
            result = _evidence_provider_result(result)
            events.append(
                EvidenceEvent(
                    operation,
                    day.local_date,
                    refs,
                    request,
                    cast(ProviderResult[object], result),
                )
            )
            fresh = {
                evaluate_freshness(s.fetched_at, s.valid_until, self.clock())
                for s in result.source_records
            }
            missing = (
                result.data is None
                or result.status is ProviderResultStatus.UNAVAILABLE
                or DataFreshness.STALE in fresh
            )
            ids = tuple(s.source_id for s in result.source_records)
            used = False
            if operation == "forecast":
                data = result.data
                assert data is None or isinstance(data, WeatherForecastResult)
                if missing:
                    target = None
                else:
                    assert data is not None
                    target = next((d for d in data.days if d.forecast_date == day.local_date), None)
                weather = (
                    None
                    if target is None
                    else WeatherSnapshot(
                        **asdict(target),
                        location_id=lid,
                        source_ids=ids,
                        alerts=old.alerts if old else (),
                    )
                )
                used = weather is not None
            elif weather is not None:
                alert_data = result.data
                assert alert_data is None or isinstance(alert_data, WeatherAlertsResult)
                alerts: tuple[WeatherAlert, ...]
                if missing:
                    alerts = ()
                else:
                    assert alert_data is not None
                    alerts = tuple(
                        WeatherAlert(**asdict(a), source_ids=ids) for a in alert_data.alerts
                    )
                weather = weather.model_copy(update={"alerts": alerts})
                used = not missing and (
                    bool(alerts)
                    or result.status is ProviderResultStatus.PARTIAL
                    or DataFreshness.UNKNOWN_VALIDITY in fresh
                )
            if used:
                sources.extend(_sources((result,), job_id=job_id, evaluated_at=self.clock())[2:])
        return day.model_copy(update={"weather": weather})


class _ModelCalls:
    """Forward unchanged typed requests; retain only the actual repair brief in RAM."""

    def __init__(self, delegate: DeepSeekPort) -> None:
        self.delegate = delegate
        self.repair: PlanRepairBrief | None = None

    async def generate_plan_candidate(
        self, request: PlanningContext
    ) -> ProviderResult[ModelTextOutput]:
        return await self.delegate.generate_plan_candidate(request)

    async def repair_plan_candidate(
        self, request: PlanRepairBrief
    ) -> ProviderResult[ModelTextOutput]:
        self.repair = request
        return await self.delegate.repair_plan_candidate(request)


def _diagnostics(
    result: PlanningJobResult, events: list[EvidenceEvent], at: datetime
) -> PlanningJobResult:
    errors: list[ApiError] = []
    warnings: list[str] = []
    uncertainties: list[Uncertainty] = []
    for event in sorted(
        events, key=lambda e: (e.local_date, e.operation != "forecast", e.operation, e.refs)
    ):
        codes: list[tuple[str, tuple[UUID, ...]]] = []
        if isinstance(event.result, ProviderResult):
            errors.extend(_provider_errors((event.result,)))
            ids = tuple(s.source_id for s in event.result.source_records)
            freshness = {
                evaluate_freshness(s.fetched_at, s.valid_until, at)
                for s in event.result.source_records
            }
            if event.operation in {"forecast", "alerts"}:
                missing = (
                    event.result.data is None
                    or event.result.status is ProviderResultStatus.UNAVAILABLE
                    or DataFreshness.STALE in freshness
                )
                if event.operation == "forecast" and not missing:
                    assert isinstance(event.result.data, WeatherForecastResult)
                    missing = not any(
                        d.forecast_date == event.local_date for d in event.result.data.days
                    )
                if missing:
                    codes.append(("weather_incomplete", ()))
                if missing or not any(
                    s.source_id in {x.source_id for x in result.sources}
                    for s in event.result.source_records
                ):
                    freshness = set()
                    ids = ()
                if DataFreshness.STALE in {
                    evaluate_freshness(s.fetched_at, s.valid_until, at)
                    for s in event.result.source_records
                }:
                    errors.append(
                        ApiError(
                            code=ApiErrorCode.DATA_STALE,
                            message=_PROVIDER_ERROR_MESSAGES[ApiErrorCode.DATA_STALE],
                            provider="qweather",
                            diagnostic_code="weather_forecast_stale"
                            if event.operation == "forecast"
                            else "weather_alert_stale",
                            retryable=False,
                        )
                    )
            if event.result.status is ProviderResultStatus.PARTIAL and ids:
                codes.append(("provider_degraded", ids))
            if DataFreshness.UNKNOWN_VALIDITY in freshness:
                codes.append(("source_validity_unknown", ids))
        elif event.operation == "budget":
            codes.append(("budget_indeterminate", ()))
        elif event.operation == "constraint":
            codes.append(("hard_constraint_unverified", ()))
        for code, ids in sorted(codes):
            message = _ISSUE_MESSAGES[FinalValidationIssueCode(code)].format(trip_day_label="两日")
            uncertainties.append(
                Uncertainty(code=code, message=message, affected_refs=event.refs, source_ids=ids)
            )
            if code in {"provider_degraded", "weather_incomplete"}:
                warnings.append(message)
        if event.operation == "fallback":
            warnings.append(
                _SCHEDULING_WARNING_MESSAGES[SchedulingWarningCode.ROUTE_MODE_FALLBACK_USED]
            )

    return replace(
        result,
        errors=_append_unique(result.errors, errors),
        warnings=_append_unique(result.warnings, warnings),
        uncertainties=_append_unique(result.uncertainties, uncertainties),
    )


def _required_outcome(result: ProviderResult[Any] | None) -> ReplanOutcome:
    if result is not None and result.error is not None:
        code = result.error.code.value
        status = ReplanStatus.NEEDS_INPUT if code == "data_missing" else ReplanStatus.FAILED
        return ReplanOutcome(status, code)
    return ReplanOutcome(ReplanStatus.NEEDS_INPUT, "data_missing")


def _evidence_provider_result(result: ProviderResult[Any]) -> ProviderResult[Any]:
    error = result.error
    if (
        error is None
        or error.reason is None
        or error.reason.value
        not in {
            "retry_budget_exhausted",
            "retry_deadline_exhausted",
        }
    ):
        return result
    return replace(result, error=replace(error, reason=None))


def _append_unique[T](old: tuple[T, ...], new: list[T]) -> tuple[T, ...]:
    return (*old, *(value for index, value in enumerate(new) if value not in new[:index]))


def _candidate_budget(budget: Money, costs: tuple[CostItem, ...]) -> BudgetSummaryResult:
    items = tuple(
        DomainBudgetCostItem(
            cost.cost_id,
            CostCategory(cost.category.value),
            CostConfidence(cost.confidence.value),
            None if cost.amount is None else DomainMoney(cost.amount.amount),
            cost.source_ids,
        )
        for cost in costs
    )
    return summarize_budget(DomainMoney(budget.amount), items)


def _governance_outcome(error: ToolCallGovernanceError) -> ReplanOutcome:
    if error.code in {
        ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING,
        ToolCallGovernanceErrorCode.CALL_TIMEOUT,
        ToolCallGovernanceErrorCode.TASK_TIMEOUT,
    }:
        return ReplanOutcome(ReplanStatus.FAILED, "provider_timeout")
    return ReplanOutcome(ReplanStatus.FAILED, "replan_execution_failed")


def _route_failure_outcome(lookup: _RouteLookup) -> ReplanOutcome:
    if lookup.result is not None and lookup.result.error is not None:
        return _required_outcome(lookup.result)
    diagnostic = None if lookup.diagnostic_code is None else lookup.diagnostic_code.value
    if diagnostic == "route_deadline_exhausted":
        return ReplanOutcome(ReplanStatus.FAILED, "provider_timeout")
    if diagnostic == "route_source_stale":
        return ReplanOutcome(ReplanStatus.FAILED, "data_stale")
    if diagnostic == "route_result_invalid":
        return ReplanOutcome(ReplanStatus.FAILED, "provider_schema_invalid")
    if diagnostic == "route_call_budget_exhausted":
        return ReplanOutcome(ReplanStatus.FAILED, "replan_execution_failed")
    return ReplanOutcome(ReplanStatus.NEEDS_INPUT, "data_missing")
