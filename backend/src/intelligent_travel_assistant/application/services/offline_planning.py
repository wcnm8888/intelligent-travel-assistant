"""Minimal offline planning flow before final deterministic validation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.application.planning import (
    AccommodationAnchor,
    CandidateResolutionErrorCode,
    CandidateValidationStage,
    DeepSeekProposalResolver,
    FinalValidationResult,
    RouteDataDiagnosticCode,
    RouteEnrichmentResult,
    RouteRequirement,
    ScheduledRoute,
    SchedulingIssueCode,
    SchedulingResult,
    SchedulingUncertaintyCode,
    SchedulingWarningCode,
    derive_route_requirements,
    evaluate_final_plan,
    route_activities,
    schedule_plan_proposal,
)
from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CandidateTimeFailureCode,
    CandidateValidationCode,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    PlanCandidate,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningObservation,
    PlanningToolName,
    PlanProposal,
    PoiCandidate,
    PoiSearchRequest,
    PoiSearchResult,
    QWeatherPort,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
)
from intelligent_travel_assistant.application.tooling import (
    ROUTE_CONCURRENCY_LIMIT,
    ProviderAttemptRuntime,
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
    ToolCallSnapshot,
    provider_result_from_attempt_outcome,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    MAX_ROUTE_DISTANCE_METERS,
    MAX_ROUTE_DURATION_MINUTES,
    BudgetCostItem,
    Coordinates,
    CostCategory,
    CostConfidence,
    DailyAvailability,
    DailyRoutePlan,
    DomainInvariantError,
    FactCriticality,
    FactUse,
    Money,
    MultiDayTripRequestInput,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderOperation,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    TripRequestInput,
    decide_freshness,
    evaluate_freshness,
)
from intelligent_travel_assistant.domain import (
    DataFreshness as DomainDataFreshness,
)


@dataclass(frozen=True, slots=True)
class OfflinePlanningRequest:
    trip: TripRequestInput | MultiDayTripRequestInput
    budget: Money
    hard_constraints: tuple[str, ...]
    weather_location_id: UUID | None
    poi_keywords: tuple[str, ...]
    poi_categories: tuple[str, ...]
    poi_limit: int
    route_mode: RouteMode
    accommodation: AccommodationAnchor | None
    day_windows: tuple[DailyAvailability, ...]
    cost_items: tuple[BudgetCostItem, ...]
    evaluated_at: datetime
    accommodation_query: str | None = None
    derive_local_transport_cost: bool = False
    fallback_route_modes: tuple[RouteMode, ...] = ()

    def __post_init__(self) -> None:
        if self.accommodation is None and (
            not isinstance(self.accommodation_query, str) or not self.accommodation_query.strip()
        ):
            raise DomainInvariantError(
                "accommodation_query_required",
                field="accommodation_query",
            )
        if (
            not isinstance(self.fallback_route_modes, tuple)
            or not all(isinstance(item, RouteMode) for item in self.fallback_route_modes)
            or self.route_mode in self.fallback_route_modes
            or len(set(self.fallback_route_modes)) != len(self.fallback_route_modes)
        ):
            raise DomainInvariantError("fallback_route_modes_invalid", field="fallback_route_modes")

    @property
    def route_modes(self) -> tuple[RouteMode, ...]:
        return (self.route_mode, *self.fallback_route_modes)

    @property
    def day_count(self) -> int:
        return (self.trip.end_date - self.trip.start_date).days + 1


@dataclass(frozen=True, slots=True)
class OfflinePlanningOutcome:
    status: PlanningStatus
    state_history: tuple[PlanningStatus, ...]
    tool_calls: ToolCallSnapshot
    candidate_resolution_error: CandidateResolutionErrorCode | None = None
    candidate_repaired: bool = False
    candidate_validation_stage: CandidateValidationStage | None = None
    candidate_validation_code: CandidateValidationCode | None = None
    candidate_time_failure: CandidateTimeFailureCode | None = None
    city_result: ProviderResult[CityResolution] | None = None
    accommodation_result: ProviderResult[PoiSearchResult] | None = None
    accommodation: AccommodationAnchor | None = None
    poi_result: ProviderResult[PoiSearchResult] | None = None
    weather_result: ProviderResult[WeatherForecastResult] | None = None
    alert_result: ProviderResult[WeatherAlertsResult] | None = None
    proposal_result: ProviderResult[PlanProposal] | None = None
    candidate_result: ProviderResult[PlanCandidate] | None = None
    scheduling_issue: SchedulingIssueCode | None = None
    route_diagnostic_code: RouteDataDiagnosticCode | None = None
    scheduling_warnings: tuple[SchedulingWarningCode, ...] = ()
    scheduling_uncertainties: tuple[SchedulingUncertaintyCode, ...] = ()
    route_results: tuple[ProviderResult[RouteLeg], ...] = ()
    route_enrichments: tuple[RouteEnrichmentResult, ...] = ()
    final_validation: FinalValidationResult | None = None

    @property
    def route_result(self) -> ProviderResult[RouteLeg] | None:
        """Compatibility view; callers should use the complete enrichment tuple."""

        return next(
            (item.result for item in self.route_enrichments if item.result is not None),
            None,
        )


@dataclass(frozen=True, slots=True)
class _RouteLookup:
    requirement: RouteRequirement
    request: RouteCalculationRequest | None
    result: ProviderResult[RouteLeg] | None
    diagnostic_code: RouteDataDiagnosticCode | None = None


@dataclass(frozen=True, slots=True)
class _RouteLookupBatch:
    lookups: tuple[_RouteLookup, ...]
    stopped: bool


class OfflinePlanningOrchestrator:
    """Compose, enrich, and deterministically arbitrate one offline candidate."""

    __slots__ = (
        "_amap",
        "_deepseek",
        "_governor_factory",
        "_qweather",
        "_request_governor_factory",
    )

    def __init__(
        self,
        amap: AmapPort,
        qweather: QWeatherPort,
        deepseek: DeepSeekPort,
        governor_factory: Callable[[], ToolCallGovernor],
        *,
        request_governor_factory: Callable[[OfflinePlanningRequest], ToolCallGovernor]
        | None = None,
    ) -> None:
        self._amap = amap
        self._qweather = qweather
        self._deepseek = deepseek
        self._governor_factory = governor_factory
        self._request_governor_factory = request_governor_factory

    async def plan(
        self,
        request: OfflinePlanningRequest,
        *,
        state_observer: Callable[[PlanningStatus], Awaitable[None]] | None = None,
        attempt_runtime: ProviderAttemptRuntime | None = None,
    ) -> OfflinePlanningOutcome:
        governor = (
            self._request_governor_factory(request)
            if self._request_governor_factory is not None
            else self._governor_factory()
        )
        history = [PlanningStatus.DRAFT]
        await _advance(history, PlanningStatus.NORMALIZING, state_observer)
        await _advance(history, PlanningStatus.COLLECTING, state_observer)

        city_result = await _governed_call(
            governor,
            ToolCallCapability.RESOLVE_CITY,
            history[-1],
            lambda: self._amap.resolve_city(CityResolutionRequest(request.trip.city)),
            attempt_runtime=attempt_runtime,
            provider=Provider.AMAP,
            provider_operation=ProviderOperation.RESOLVE_CITY,
        )
        if city_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(history, governor, city_result=city_result)
        city = _require_data(city_result)

        accommodation = request.accommodation
        accommodation_result: ProviderResult[PoiSearchResult] | None = None
        if accommodation is None:
            accommodation_query = request.accommodation_query
            assert isinstance(accommodation_query, str)
            accommodation_result = await _governed_call(
                governor,
                ToolCallCapability.SEARCH_POIS,
                history[-1],
                lambda: self._amap.search_pois(
                    PoiSearchRequest(
                        city_adcode=city.adcode,
                        keywords=(accommodation_query.strip(),),
                        categories=(),
                        limit=3,
                    )
                ),
                attempt_runtime=attempt_runtime,
                provider=Provider.AMAP,
                provider_operation=ProviderOperation.SEARCH_POIS,
            )
            if accommodation_result.status is ProviderResultStatus.UNAVAILABLE:
                await _advance(history, PlanningStatus.FAILED, state_observer)
                return _outcome(
                    history,
                    governor,
                    city_result=city_result,
                    accommodation_result=accommodation_result,
                )
            accommodation_candidate = next(
                (
                    item
                    for item in _require_data(accommodation_result).candidates
                    if item.city_adcode == city.adcode and item.coordinates is not None
                ),
                None,
            )
            if accommodation_candidate is None:
                await _advance(history, PlanningStatus.FAILED, state_observer)
                return _outcome(
                    history,
                    governor,
                    city_result=city_result,
                    accommodation_result=accommodation_result,
                )
            accommodation = AccommodationAnchor(
                accommodation_candidate.location_id,
                accommodation_candidate.city_adcode,
                accommodation_candidate.coordinates,
            )

        poi_request = PoiSearchRequest(
            city_adcode=city.adcode,
            keywords=request.poi_keywords,
            categories=request.poi_categories,
            limit=request.poi_limit,
        )
        poi_result = await _governed_call(
            governor,
            ToolCallCapability.SEARCH_POIS,
            history[-1],
            lambda: self._amap.search_pois(poi_request),
            attempt_runtime=attempt_runtime,
            provider=Provider.AMAP,
            provider_operation=ProviderOperation.SEARCH_POIS,
        )
        if poi_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(
                history,
                governor,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
            )
        pois = _require_data(poi_result)

        weather_result: ProviderResult[WeatherForecastResult] | None = None
        alert_result: ProviderResult[WeatherAlertsResult] | None = None
        weather_coordinates = (
            accommodation.coordinates if request.weather_location_id is None else city.center
        )
        if weather_coordinates is not None:
            weather_location_id = request.weather_location_id or accommodation.location_id
            forecast_request = WeatherForecastRequest(
                location_id=weather_location_id,
                coordinates=weather_coordinates,
                start_date=request.trip.start_date,
                end_date=request.trip.end_date,
            )
            weather_result = await _governed_call(
                governor,
                ToolCallCapability.GET_WEATHER_FORECAST,
                history[-1],
                lambda: self._qweather.get_weather_forecast(forecast_request),
                attempt_runtime=attempt_runtime,
                provider=Provider.QWEATHER,
                provider_operation=ProviderOperation.GET_WEATHER_FORECAST,
            )
            alerts_request = CurrentWeatherAlertsRequest(
                location_id=weather_location_id,
                coordinates=weather_coordinates,
            )
            alert_result = await _governed_call(
                governor,
                ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
                history[-1],
                lambda: self._qweather.get_current_weather_alerts(alerts_request),
                attempt_runtime=attempt_runtime,
                provider=Provider.QWEATHER,
                provider_operation=ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
            )

        weather_for_use = _provider_result_for_use(
            weather_result,
            operation=ProviderOperation.GET_WEATHER_FORECAST,
            criticality=FactCriticality.OPTIONAL,
            evaluated_at=request.evaluated_at,
        )
        alerts_for_use = _provider_result_for_use(
            alert_result,
            operation=ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
            criticality=FactCriticality.OPTIONAL,
            evaluated_at=request.evaluated_at,
        )

        await _advance(history, PlanningStatus.PLANNING, state_observer)
        planning_context = _planning_context(
            request,
            city,
            accommodation,
            pois,
            city_result,
            poi_result,
            weather_for_use,
            alerts_for_use,
        )
        proposal_resolution = await DeepSeekProposalResolver(self._deepseek).resolve(
            planning_context,
            governor,
            attempt_runtime,
        )
        proposal_result = proposal_resolution.result
        if proposal_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(
                history,
                governor,
                candidate_resolution_error=proposal_resolution.error_code,
                candidate_repaired=proposal_resolution.repaired,
                candidate_validation_stage=proposal_resolution.validation_stage,
                candidate_validation_code=proposal_resolution.validation_code,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
                weather_result=weather_result,
                alert_result=alert_result,
                proposal_result=proposal_result,
            )

        proposal = _require_data(proposal_result)
        scheduling = schedule_plan_proposal(
            proposal,
            accommodation_location_id=accommodation.location_id,
            day_windows=request.day_windows,
            locations=planning_context.locations,
            route_mode=request.route_mode,
            routes=(),
            queried_routes=frozenset(),
            fallback_route_modes=request.fallback_route_modes,
        )
        if scheduling.issue is SchedulingIssueCode.ACTIVITY_DURATION_UNKNOWN:
            await _advance(history, PlanningStatus.NEEDS_INPUT, state_observer)
            return _outcome(
                history,
                governor,
                candidate_repaired=proposal_resolution.repaired,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
                weather_result=weather_result,
                alert_result=alert_result,
                proposal_result=proposal_result,
                scheduling_issue=scheduling.issue,
                scheduling_uncertainties=scheduling.uncertainties,
            )

        await _advance(history, PlanningStatus.ENRICHING_ROUTES, state_observer)
        route_lookups, scheduling = await _schedule_with_routes(
            scheduling,
            request=request,
            accommodation=accommodation,
            pois=pois.candidates,
            citycode=city.citycode,
            amap=self._amap,
            governor=governor,
            status=history[-1],
            locations=planning_context.locations,
            attempt_runtime=attempt_runtime,
        )
        if scheduling.issue is SchedulingIssueCode.ROUTE_DATA_UNAVAILABLE:
            route_diagnostic_code = _route_data_diagnostic(
                scheduling.proposal,
                accommodation.location_id,
                route_lookups,
                request,
            )
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(
                history,
                governor,
                candidate_repaired=proposal_resolution.repaired,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
                weather_result=weather_result,
                alert_result=alert_result,
                proposal_result=proposal_result,
                scheduling_issue=scheduling.issue,
                route_diagnostic_code=route_diagnostic_code,
                scheduling_warnings=scheduling.warnings,
                scheduling_uncertainties=scheduling.uncertainties,
                route_results=_route_results(route_lookups),
                route_enrichments=_route_enrichments_from_lookups(
                    None,
                    request,
                    accommodation,
                    route_lookups,
                ),
            )

        await _advance(history, PlanningStatus.VALIDATING, state_observer)
        if scheduling.issue is SchedulingIssueCode.SCHEDULE_CAPACITY_EXCEEDED:
            await _advance(history, PlanningStatus.CONFLICT, state_observer)
            return _outcome(
                history,
                governor,
                candidate_repaired=proposal_resolution.repaired,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
                weather_result=weather_result,
                alert_result=alert_result,
                proposal_result=proposal_result,
                scheduling_issue=scheduling.issue,
                scheduling_warnings=scheduling.warnings,
                scheduling_uncertainties=scheduling.uncertainties,
                route_results=_route_results(route_lookups),
            )
        if scheduling.issue is not None or scheduling.candidate is None:
            raise AssertionError("deterministic scheduler returned an unsupported result")

        candidate = scheduling.candidate
        candidate_result = _with_scheduled_candidate(proposal_result, candidate)
        route_enrichments = _route_enrichments_from_lookups(
            candidate,
            request,
            accommodation,
            route_lookups,
        )
        provider_results = _provider_results(
            city_result,
            accommodation_result,
            poi_result,
            candidate_result,
            weather_result,
            alert_result,
            route_enrichments,
        )
        final_validation = evaluate_final_plan(
            candidate=candidate,
            city_adcode=city.adcode,
            pois=pois,
            poi_source_ids=_source_ids(poi_result),
            accommodation=accommodation,
            day_windows=request.day_windows,
            budget=request.budget,
            cost_items=_cost_items_with_local_transport(
                request,
                route_enrichments,
            ),
            route_enrichments=route_enrichments,
            weather_result=weather_for_use,
            expected_weather_location_id=(request.weather_location_id or accommodation.location_id),
            provider_results=provider_results,
            evaluated_at=max(
                request.evaluated_at,
                *(
                    record.fetched_at
                    for result in provider_results
                    for record in result.source_records
                ),
            ),
            hard_constraints=request.hard_constraints,
        )
        await _advance(history, final_validation.status, state_observer)
        return _outcome(
            history,
            governor,
            candidate_resolution_error=proposal_resolution.error_code,
            candidate_repaired=proposal_resolution.repaired,
            candidate_validation_stage=proposal_resolution.validation_stage,
            candidate_validation_code=proposal_resolution.validation_code,
            city_result=city_result,
            accommodation_result=accommodation_result,
            accommodation=accommodation,
            poi_result=poi_result,
            weather_result=weather_result,
            alert_result=alert_result,
            proposal_result=proposal_result,
            candidate_result=candidate_result,
            scheduling_warnings=scheduling.warnings,
            scheduling_uncertainties=scheduling.uncertainties,
            route_results=_route_results(route_lookups),
            route_enrichments=route_enrichments,
            final_validation=final_validation,
        )


async def _advance(
    history: list[PlanningStatus],
    target: PlanningStatus,
    state_observer: Callable[[PlanningStatus], Awaitable[None]] | None,
) -> None:
    result = PlanningStateMachine.transition(
        PlanningTransitionCommand(current_status=history[-1], target_status=target)
    )
    history.append(result.current_status)
    if state_observer is not None:
        await state_observer(result.current_status)


def _outcome(
    history: list[PlanningStatus],
    governor: ToolCallGovernor,
    *,
    candidate_resolution_error: CandidateResolutionErrorCode | None = None,
    candidate_repaired: bool = False,
    candidate_validation_stage: CandidateValidationStage | None = None,
    candidate_validation_code: CandidateValidationCode | None = None,
    candidate_time_failure: CandidateTimeFailureCode | None = None,
    city_result: ProviderResult[CityResolution] | None = None,
    accommodation_result: ProviderResult[PoiSearchResult] | None = None,
    accommodation: AccommodationAnchor | None = None,
    poi_result: ProviderResult[PoiSearchResult] | None = None,
    weather_result: ProviderResult[WeatherForecastResult] | None = None,
    alert_result: ProviderResult[WeatherAlertsResult] | None = None,
    proposal_result: ProviderResult[PlanProposal] | None = None,
    candidate_result: ProviderResult[PlanCandidate] | None = None,
    scheduling_issue: SchedulingIssueCode | None = None,
    route_diagnostic_code: RouteDataDiagnosticCode | None = None,
    scheduling_warnings: tuple[SchedulingWarningCode, ...] = (),
    scheduling_uncertainties: tuple[SchedulingUncertaintyCode, ...] = (),
    route_results: tuple[ProviderResult[RouteLeg], ...] = (),
    route_enrichments: tuple[RouteEnrichmentResult, ...] = (),
    final_validation: FinalValidationResult | None = None,
) -> OfflinePlanningOutcome:
    return OfflinePlanningOutcome(
        status=history[-1],
        state_history=tuple(history),
        tool_calls=governor.snapshot(),
        candidate_resolution_error=candidate_resolution_error,
        candidate_repaired=candidate_repaired,
        candidate_validation_stage=candidate_validation_stage,
        candidate_validation_code=candidate_validation_code,
        candidate_time_failure=candidate_time_failure,
        city_result=city_result,
        accommodation_result=accommodation_result,
        accommodation=accommodation,
        poi_result=poi_result,
        weather_result=weather_result,
        alert_result=alert_result,
        proposal_result=proposal_result,
        candidate_result=candidate_result,
        scheduling_issue=scheduling_issue,
        route_diagnostic_code=route_diagnostic_code,
        scheduling_warnings=scheduling_warnings,
        scheduling_uncertainties=scheduling_uncertainties,
        route_results=route_results,
        route_enrichments=route_enrichments,
        final_validation=final_validation,
    )


async def _governed_call[T](
    governor: ToolCallGovernor,
    capability: ToolCallCapability,
    status: PlanningStatus,
    operation: Callable[[], Awaitable[ProviderResult[T]]],
    *,
    attempt_runtime: ProviderAttemptRuntime | None = None,
    provider: Provider | None = None,
    provider_operation: ProviderOperation | None = None,
) -> ProviderResult[T]:
    try:
        permit = governor.reserve(capability, status)
    except ToolCallGovernanceError as error:
        if (
            attempt_runtime is None
            or provider is None
            or error.code
            not in {
                ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING,
                ToolCallGovernanceErrorCode.CALL_TIMEOUT,
                ToolCallGovernanceErrorCode.TASK_TIMEOUT,
            }
        ):
            raise
        return ProviderResult(
            ProviderResultStatus.UNAVAILABLE,
            provider,
            None,
            None,
            None,
            (),
            ProviderError(
                ProviderErrorCategory.TIMEOUT,
                reason=ProviderErrorReason.RETRY_DEADLINE_EXHAUSTED,
            ),
            (),
        )
    result: ProviderResult[T] | None = None

    async def operation_after_pacing_wait() -> ProviderResult[T]:
        governor.start_route_attempt_timeout_after_wait(permit)
        try:
            attempt_result = await operation()
        except BaseException:
            governor.finish_route_attempt(permit)
            raise
        if governor.finish_route_attempt(permit):
            return attempt_result
        assert provider is not None
        return ProviderResult(
            ProviderResultStatus.UNAVAILABLE,
            provider,
            None,
            None,
            None,
            (),
            ProviderError(ProviderErrorCategory.TIMEOUT),
            (),
        )

    try:
        if attempt_runtime is None:
            result = await operation()
        else:
            if provider is None or provider_operation is None:
                raise ValueError("provider_attempt_metadata_required")
            paced_route = (
                provider is Provider.AMAP
                and provider_operation is ProviderOperation.CALCULATE_ROUTES
            )
            outcome = await attempt_runtime.execute(
                provider=provider,
                operation=provider_operation,
                call=operation_after_pacing_wait if paced_route else operation,
            )
            result = provider_result_from_attempt_outcome(outcome)
    finally:
        try:
            governor.complete(permit)
        except ToolCallGovernanceError as error:
            provider_timeout = (
                result is not None
                and result.error is not None
                and result.error.category is ProviderErrorCategory.TIMEOUT
            )
            if error.code is not ToolCallGovernanceErrorCode.CALL_TIMEOUT or not provider_timeout:
                raise
    assert result is not None
    return result


def _provider_result_for_use[T](
    result: ProviderResult[T] | None,
    *,
    operation: ProviderOperation,
    criticality: FactCriticality,
    evaluated_at: datetime,
) -> ProviderResult[T] | None:
    if result is None or result.data is None:
        return None
    freshness_values = tuple(
        evaluate_freshness(
            record.fetched_at,
            record.valid_until,
            max(evaluated_at, record.fetched_at),
        )
        for record in result.source_records
    )
    freshness = (
        DomainDataFreshness.STALE
        if DomainDataFreshness.STALE in freshness_values
        else DomainDataFreshness.UNKNOWN_VALIDITY
        if DomainDataFreshness.UNKNOWN_VALIDITY in freshness_values
        else DomainDataFreshness.FRESH
    )
    decision = decide_freshness(operation, freshness, criticality)
    return result if decision.fact_use is FactUse.USE else None


def _planning_context(
    request: OfflinePlanningRequest,
    city: CityResolution,
    accommodation: AccommodationAnchor,
    pois: PoiSearchResult,
    city_result: ProviderResult[CityResolution],
    poi_result: ProviderResult[PoiSearchResult],
    weather_result: ProviderResult[WeatherForecastResult] | None,
    alert_result: ProviderResult[WeatherAlertsResult] | None,
) -> PlanningContext:
    observations = [
        PlanningObservation("city", "city resolved", _source_ids(city_result)),
        PlanningObservation("pois", "POI candidates collected", _source_ids(poi_result)),
    ]
    if weather_result is not None:
        observations.append(
            PlanningObservation(
                "weather",
                _weather_summary(weather_result),
                _source_ids(weather_result),
            )
        )
    if alert_result is not None:
        observations.append(
            PlanningObservation(
                "weather_alerts",
                _alert_summary(alert_result),
                _source_ids(alert_result),
            )
        )
    expected_dates = tuple(
        request.trip.start_date + timedelta(days=offset) for offset in range(request.day_count)
    )
    return PlanningContext(
        city_name=city.city_name,
        city_adcode=city.adcode,
        start_date=request.trip.start_date,
        end_date=request.trip.end_date,
        travelers=request.trip.travelers,
        budget=request.budget,
        interests=request.trip.interests,
        hard_constraints=request.hard_constraints,
        allowed_tools=tuple(PlanningToolName),
        locations=tuple(
            PlanningLocation(item.location_id, item.name, item.category, item.city_adcode)
            for item in pois.candidates
        ),
        observations=tuple(observations),
        free_text=request.trip.free_text,
        route_mode=request.route_mode,
        day_windows=tuple(
            PlanningDayWindow(item.day_offset, item.start_time, item.end_time)
            for item in request.day_windows
        ),
        accommodation=PlanningLocation(
            accommodation.location_id,
            "accommodation anchor",
            "accommodation_anchor",
            accommodation.city_adcode,
        ),
        activity_source_ids=_source_ids(poi_result),
        request_version=("2" if isinstance(request.trip, MultiDayTripRequestInput) else None),
        expected_dates=(
            expected_dates if isinstance(request.trip, MultiDayTripRequestInput) else ()
        ),
    )


async def _schedule_with_routes(
    scheduling: SchedulingResult,
    *,
    request: OfflinePlanningRequest,
    accommodation: AccommodationAnchor,
    pois: tuple[PoiCandidate, ...],
    citycode: str,
    amap: AmapPort,
    governor: ToolCallGovernor,
    status: PlanningStatus,
    locations: tuple[PlanningLocation, ...],
    attempt_runtime: ProviderAttemptRuntime | None,
) -> tuple[tuple[_RouteLookup, ...], SchedulingResult]:
    coordinates = {item.location_id: item.coordinates for item in pois}
    coordinates[accommodation.location_id] = accommodation.coordinates
    lookups: list[_RouteLookup] = []
    for _ in range(3):
        if scheduling.issue is not SchedulingIssueCode.ROUTE_DATA_REQUIRED:
            return tuple(lookups), _with_route_fallback_warning(
                scheduling,
                accommodation.location_id,
                lookups,
                request,
            )
        primary_batch = await _lookup_route_batch(
            scheduling.missing_routes,
            mode=request.route_mode,
            coordinates=coordinates,
            citycode=citycode,
            amap=amap,
            governor=governor,
            status=status,
            attempt_runtime=attempt_runtime,
            evaluated_at=request.evaluated_at,
        )
        primary_lookups = primary_batch.lookups
        lookups.extend(primary_lookups)
        fallback_pending = (
            []
            if primary_batch.stopped
            else [item for item in primary_lookups if _lookup_allows_fallback(item)]
        )
        for fallback_mode in request.fallback_route_modes:
            if not fallback_pending:
                break
            fallback_batch = await _lookup_route_batch(
                tuple(item.requirement for item in fallback_pending),
                mode=fallback_mode,
                coordinates=coordinates,
                citycode=citycode,
                amap=amap,
                governor=governor,
                status=status,
                attempt_runtime=attempt_runtime,
                evaluated_at=request.evaluated_at,
            )
            fallback_lookups = fallback_batch.lookups
            lookups.extend(fallback_lookups)
            if fallback_batch.stopped:
                fallback_pending = []
                break
            fallback_pending = [item for item in fallback_lookups if _lookup_allows_fallback(item)]
        scheduling = schedule_plan_proposal(
            scheduling.proposal,
            accommodation_location_id=accommodation.location_id,
            day_windows=request.day_windows,
            locations=locations,
            route_mode=request.route_mode,
            routes=_scheduled_routes(lookups, request.route_modes),
            queried_routes=frozenset(item.requirement for item in lookups),
            fallback_route_modes=request.fallback_route_modes,
            omitted_days=scheduling.omitted_days,
            warnings=scheduling.warnings,
        )
        if scheduling.issue is not SchedulingIssueCode.ROUTE_DATA_REQUIRED:
            return tuple(lookups), _with_route_fallback_warning(
                scheduling,
                accommodation.location_id,
                lookups,
                request,
            )
    raise AssertionError("deterministic scheduler exceeded the bounded enrichment passes")


async def _lookup_route_batch(
    requirements: tuple[RouteRequirement, ...],
    *,
    mode: RouteMode,
    coordinates: dict[UUID, Coordinates | None],
    citycode: str,
    amap: AmapPort,
    governor: ToolCallGovernor,
    status: PlanningStatus,
    attempt_runtime: ProviderAttemptRuntime | None,
    evaluated_at: datetime,
) -> _RouteLookupBatch:
    values: list[_RouteLookup] = []
    stopped = False
    for start in range(0, len(requirements), ROUTE_CONCURRENCY_LIMIT):
        batch = requirements[start : start + ROUTE_CONCURRENCY_LIMIT]
        tasks = tuple(
            asyncio.create_task(
                _lookup_route(
                    requirement,
                    mode=mode,
                    coordinates=coordinates,
                    citycode=citycode,
                    amap=amap,
                    governor=governor,
                    status=status,
                    attempt_runtime=attempt_runtime,
                    evaluated_at=evaluated_at,
                )
            )
            for requirement in batch
        )
        try:
            resolved = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        values.extend(resolved)
        if any(_lookup_stops_route_enrichment(item) for item in resolved):
            stopped = True
            break
    return _RouteLookupBatch(tuple(values), stopped)


async def _lookup_route(
    requirement: RouteRequirement,
    *,
    mode: RouteMode,
    coordinates: dict[UUID, Coordinates | None],
    citycode: str,
    amap: AmapPort,
    governor: ToolCallGovernor,
    status: PlanningStatus,
    attempt_runtime: ProviderAttemptRuntime | None,
    evaluated_at: datetime,
) -> _RouteLookup:
    origin = coordinates.get(requirement.origin_location_id)
    destination = coordinates.get(requirement.destination_location_id)
    if origin is None or destination is None:
        return _RouteLookup(
            requirement,
            None,
            None,
            RouteDataDiagnosticCode.COORDINATES_MISSING,
        )
    route_request = RouteCalculationRequest(
        requirement.origin_location_id,
        requirement.destination_location_id,
        origin,
        destination,
        citycode,
        citycode,
        mode,
    )
    try:
        route_result = await _governed_call(
            governor,
            ToolCallCapability.CALCULATE_ROUTES,
            status,
            _route_operation(amap, route_request),
            attempt_runtime=attempt_runtime,
            provider=Provider.AMAP,
            provider_operation=ProviderOperation.CALCULATE_ROUTES,
        )
    except ToolCallGovernanceError as error:
        if error.code is ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED:
            governance_diagnostic = RouteDataDiagnosticCode.CALL_BUDGET_EXHAUSTED
        elif error.code in {
            ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING,
            ToolCallGovernanceErrorCode.CALL_TIMEOUT,
            ToolCallGovernanceErrorCode.TASK_TIMEOUT,
        }:
            governance_diagnostic = RouteDataDiagnosticCode.DEADLINE_EXHAUSTED
        else:
            raise
        return _RouteLookup(requirement, route_request, None, governance_diagnostic)
    diagnostic_code: RouteDataDiagnosticCode | None = None
    if route_result.provider is not Provider.AMAP or (
        route_result.data is not None
        and not _route_result_is_usable(requirement, route_request, route_result)
    ):
        diagnostic_code = RouteDataDiagnosticCode.RESULT_INVALID
    elif (
        route_result.data is not None
        and _provider_result_for_use(
            route_result,
            operation=ProviderOperation.CALCULATE_ROUTES,
            criticality=FactCriticality.REQUIRED,
            evaluated_at=evaluated_at,
        )
        is None
    ):
        diagnostic_code = RouteDataDiagnosticCode.SOURCE_STALE
    return _RouteLookup(requirement, route_request, route_result, diagnostic_code)


def _scheduled_routes(
    lookups: list[_RouteLookup],
    route_modes: tuple[RouteMode, ...],
) -> tuple[ScheduledRoute, ...]:
    values: list[ScheduledRoute] = []
    for item in lookups:
        if not _lookup_has_usable_route(item):
            continue
        if item.request is None or item.request.mode not in route_modes:
            continue
        if item.result is None or item.result.data is None:
            raise AssertionError("usable route lookup must contain route data")
        route = item.result.data
        values.append(ScheduledRoute(item.requirement, route))
    return tuple(values)


def _lookup_has_usable_route(lookup: _RouteLookup) -> bool:
    return (
        lookup.request is not None
        and lookup.result is not None
        and lookup.diagnostic_code is None
        and _route_result_is_usable(lookup.requirement, lookup.request, lookup.result)
    )


def _lookup_allows_fallback(lookup: _RouteLookup) -> bool:
    if _lookup_has_usable_route(lookup) or lookup.result is None:
        return False
    if lookup.result.provider is not Provider.AMAP:
        return False
    if lookup.result.data is not None:
        return (
            lookup.result.error is None
            and lookup.diagnostic_code is RouteDataDiagnosticCode.RESULT_INVALID
        )
    return (
        lookup.result.error is not None
        and lookup.result.error.category is ProviderErrorCategory.EMPTY_RESULT
    )


def _lookup_stops_route_enrichment(lookup: _RouteLookup) -> bool:
    return not _lookup_has_usable_route(lookup) and not _lookup_allows_fallback(lookup)


def _route_result_is_usable(
    requirement: RouteRequirement,
    request: RouteCalculationRequest,
    result: ProviderResult[RouteLeg],
) -> bool:
    route = result.data
    if result.provider is not Provider.AMAP or route is None:
        return False
    source_ids = {item.source_id for item in result.source_records}
    return (
        route.origin_location_id == requirement.origin_location_id
        and route.destination_location_id == requirement.destination_location_id
        and route.mode is request.mode
        and bool(route.source_ids)
        and set(route.source_ids) == source_ids
        and route.distance_meters <= MAX_ROUTE_DISTANCE_METERS
        and route.duration_minutes <= MAX_ROUTE_DURATION_MINUTES
    )


def _selected_route_lookups(
    lookups: tuple[_RouteLookup, ...] | list[_RouteLookup],
    route_modes: tuple[RouteMode, ...],
) -> dict[RouteRequirement, _RouteLookup]:
    preference = {mode: index for index, mode in enumerate(route_modes)}
    selected: dict[RouteRequirement, _RouteLookup] = {}
    for lookup in lookups:
        if (
            not _lookup_has_usable_route(lookup)
            or lookup.request is None
            or lookup.request.mode not in preference
        ):
            continue
        current = selected.get(lookup.requirement)
        if (
            current is None
            or current.request is None
            or (preference[lookup.request.mode] < preference[current.request.mode])
        ):
            selected[lookup.requirement] = lookup
    return selected


def _with_route_fallback_warning(
    scheduling: SchedulingResult,
    accommodation_location_id: UUID,
    lookups: list[_RouteLookup],
    request: OfflinePlanningRequest,
) -> SchedulingResult:
    if scheduling.candidate is None or not request.fallback_route_modes:
        return scheduling
    requirements = set(derive_route_requirements(scheduling.proposal, accommodation_location_id))
    selected = _selected_route_lookups(lookups, request.route_modes)
    used_fallback = any(
        lookup.requirement in requirements
        and lookup.request is not None
        and lookup.request.mode is not request.route_mode
        for lookup in selected.values()
    )
    if not used_fallback or SchedulingWarningCode.ROUTE_MODE_FALLBACK_USED in scheduling.warnings:
        return scheduling
    return replace(
        scheduling,
        warnings=(*scheduling.warnings, SchedulingWarningCode.ROUTE_MODE_FALLBACK_USED),
    )


def _route_data_diagnostic(
    proposal: PlanProposal,
    accommodation_location_id: UUID,
    lookups: tuple[_RouteLookup, ...],
    request: OfflinePlanningRequest,
) -> RouteDataDiagnosticCode:
    selected = _selected_route_lookups(lookups, request.route_modes)
    missing = tuple(
        requirement
        for requirement in derive_route_requirements(proposal, accommodation_location_id)
        if requirement not in selected
    )
    related = tuple(item for item in lookups if item.requirement in missing)
    if any(_lookup_has_provider_wide_failure(item) for item in related):
        return RouteDataDiagnosticCode.PRIMARY_UNAVAILABLE
    for code in (
        RouteDataDiagnosticCode.SOURCE_STALE,
        RouteDataDiagnosticCode.DEADLINE_EXHAUSTED,
        RouteDataDiagnosticCode.COORDINATES_MISSING,
        RouteDataDiagnosticCode.RESULT_INVALID,
        RouteDataDiagnosticCode.CALL_BUDGET_EXHAUSTED,
    ):
        if any(item.diagnostic_code is code for item in related):
            return code
    if any(
        item.request is not None and item.request.mode is not request.route_mode for item in related
    ):
        return RouteDataDiagnosticCode.FALLBACK_EXHAUSTED
    return RouteDataDiagnosticCode.PRIMARY_UNAVAILABLE


def _lookup_has_provider_wide_failure(lookup: _RouteLookup) -> bool:
    return (
        lookup.result is not None
        and lookup.result.provider is Provider.AMAP
        and lookup.result.data is None
        and lookup.result.error is not None
        and lookup.result.error.category
        in {
            ProviderErrorCategory.AUTH,
            ProviderErrorCategory.SCHEMA,
            ProviderErrorCategory.TIMEOUT,
            ProviderErrorCategory.RATE_LIMITED,
            ProviderErrorCategory.SERVER,
            ProviderErrorCategory.UNKNOWN,
        }
    )


def _route_enrichments_from_lookups(
    candidate: PlanCandidate | None,
    request: OfflinePlanningRequest,
    accommodation: AccommodationAnchor,
    lookups: tuple[_RouteLookup, ...],
) -> tuple[RouteEnrichmentResult, ...]:
    if candidate is None:
        return ()
    by_requirement = _selected_route_lookups(lookups, request.route_modes)
    windows = {item.day_offset: item for item in request.day_windows}
    enrichments: list[RouteEnrichmentResult] = []
    for day_offset in range(len(candidate.days)):
        expected_legs = DailyRoutePlan(
            accommodation.location_id,
            windows[day_offset],
            route_activities(candidate, day_offset),
            (),
        ).expected_legs()
        for expected in expected_legs:
            lookup = by_requirement.get(
                RouteRequirement(
                    day_offset,
                    expected.origin_location_id,
                    expected.destination_location_id,
                )
            )
            enrichments.append(
                RouteEnrichmentResult(
                    day_offset,
                    expected,
                    lookup.request if lookup is not None else None,
                    lookup.result if lookup is not None else None,
                )
            )
    return tuple(enrichments)


def _route_results(
    lookups: tuple[_RouteLookup, ...],
) -> tuple[ProviderResult[RouteLeg], ...]:
    return tuple(
        item.result
        for item in lookups
        if item.result is not None
        and item.result.provider is Provider.AMAP
        and (
            item.result.data is None
            or (
                item.request is not None
                and _route_result_is_usable(item.requirement, item.request, item.result)
            )
        )
    )


def _with_scheduled_candidate(
    source: ProviderResult[PlanProposal],
    candidate: PlanCandidate,
) -> ProviderResult[PlanCandidate]:
    return ProviderResult(
        source.status,
        source.provider,
        candidate,
        source.fetched_at,
        source.valid_until,
        source.warnings,
        source.error,
        source.source_records,
    )


def _route_operation(
    amap: AmapPort,
    request: RouteCalculationRequest,
) -> Callable[[], Awaitable[ProviderResult[RouteLeg]]]:
    async def calculate() -> ProviderResult[RouteLeg]:
        return await amap.calculate_routes(request)

    return calculate


def _cost_items_with_local_transport(
    request: OfflinePlanningRequest,
    routes: tuple[RouteEnrichmentResult, ...],
) -> tuple[BudgetCostItem, ...]:
    if not request.derive_local_transport_cost:
        return request.cost_items
    if any(item.category is CostCategory.LOCAL_TRANSPORT for item in request.cost_items):
        return request.cost_items
    public_transit_legs = sum(
        1
        for item in routes
        if item.result is not None
        and item.result.data is not None
        and item.result.data.mode is RouteMode.PUBLIC_TRANSIT
    )
    amount = Decimal(10 * request.trip.travelers * public_transit_legs).quantize(Decimal("0.01"))
    selected_modes = ",".join(
        item.result.data.mode.value
        for item in routes
        if item.result is not None and item.result.data is not None
    )
    local_transport = BudgetCostItem(
        uuid5(
            NAMESPACE_URL,
            (
                f"f-001:local-transport:{request.trip.city}:"
                f"{request.trip.start_date.isoformat()}:{request.trip.travelers}:"
                f"{selected_modes}:{len(routes)}"
            ),
        ),
        CostCategory.LOCAL_TRANSPORT,
        CostConfidence.ESTIMATED,
        Money(amount),
    )
    return (*request.cost_items, local_transport)


def _source_ids[T](result: ProviderResult[T]) -> tuple[UUID, ...]:
    return tuple(record.source_id for record in result.source_records)


def _weather_summary(result: ProviderResult[WeatherForecastResult]) -> str:
    if result.data is None:
        return f"weather {result.status.value}"
    return "; ".join(
        (
            f"{item.forecast_date.isoformat()} day={item.condition_day} "
            f"night={item.condition_night} min_c={item.temperature_min_celsius} "
            f"max_c={item.temperature_max_celsius}"
        )
        for item in result.data.days
    )


def _alert_summary(result: ProviderResult[WeatherAlertsResult]) -> str:
    if result.data is None:
        return f"weather alerts {result.status.value}"
    if not result.data.alerts:
        return "no current weather alerts"
    return "; ".join(
        f"title={item.title} severity={item.severity or 'unknown'}" for item in result.data.alerts
    )


def _require_data[T](result: ProviderResult[T]) -> T:
    if result.data is None:
        raise AssertionError("available ProviderResult must contain data")
    return result.data


def _provider_results(
    city: ProviderResult[CityResolution],
    accommodation: ProviderResult[PoiSearchResult] | None,
    pois: ProviderResult[PoiSearchResult],
    candidate: ProviderResult[PlanCandidate],
    weather: ProviderResult[WeatherForecastResult] | None,
    alerts: ProviderResult[WeatherAlertsResult] | None,
    routes: tuple[RouteEnrichmentResult, ...],
) -> tuple[ProviderResult[object], ...]:
    values: list[ProviderResult[object]] = [
        cast(ProviderResult[object], city),
        cast(ProviderResult[object], pois),
        cast(ProviderResult[object], candidate),
    ]
    if accommodation is not None:
        values.append(cast(ProviderResult[object], accommodation))
    if weather is not None:
        values.append(cast(ProviderResult[object], weather))
    if alerts is not None:
        values.append(cast(ProviderResult[object], alerts))
    values.extend(
        cast(ProviderResult[object], item.result) for item in routes if item.result is not None
    )
    return tuple(values)
