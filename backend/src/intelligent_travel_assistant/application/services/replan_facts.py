"""D-028 complete typed facts. No I/O, implicit clock, persistence or global cache."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from math import isfinite
from typing import Any, cast
from uuid import UUID, uuid5

from pydantic import AnyUrl, BaseModel

from intelligent_travel_assistant.application.planning.candidate_resolution import (
    _repair_brief,
    parse_plan_proposal,
)
from intelligent_travel_assistant.application.planning.final_validation import (
    FinalValidationIssue,
    FinalValidationIssueCode,
    FinalValidationSeverity,
)
from intelligent_travel_assistant.application.planning.scheduling import (
    RouteDataDiagnosticCode,
    RouteRequirement,
    SchedulingWarningCode,
)
from intelligent_travel_assistant.application.ports import (
    CandidateValidationCode,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningToolName,
    PlanProposal,
    PlanRepairBrief,
    PoiSearchRequest,
    PoiSearchResult,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    request_fingerprint,
)
from intelligent_travel_assistant.application.services.offline_planning import (
    RouteLookupStage,
    _alert_summary,
    _lookup_allows_fallback,
    _route_result_is_usable,
    _RouteLookup,
    _weather_summary,
)
from intelligent_travel_assistant.application.services.provider_planning_jobs import (
    _ISSUE_MESSAGES,
    _PROVIDER_ERROR_MESSAGES,
    _SCHEDULING_WARNING_MESSAGES,
    _provider_errors,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    CostItem,
    PlanDay,
    PlanningStatus,
    SourceRecord,
    TripPlan,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanV2,
    Uncertainty,
    WeatherAlert,
    WeatherSnapshot,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    BudgetAssessment,
    BudgetCostItem,
    BudgetSummaryResult,
    ChangeEntityKind,
    CostCategory,
    CostConfidence,
    DailyAvailability,
    DailyRoutePlan,
    DataFreshness,
    DeleteActivity,
    DomainInvariantError,
    ImpactActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    ImpactRoute,
    Money,
    PlanChangeSet,
    PlanEntitySnapshot,
    Provider,
    ProviderResult,
    ProviderResultStatus,
    ReorderActivities,
    ReplaceActivity,
    ReplanBudgetResult,
    ReplanCommand,
    ReplanImpactContext,
    ReplanSourceState,
    RouteActivity,
    RouteLeg,
    RouteMode,
    RouteValidationStatus,
    SourceAction,
    SourceActionReason,
    SourceActionRecord,
    build_plan_change_set,
    classify_replan_impact,
    evaluate_freshness,
    plan_source_actions,
    recalculate_replan_budget,
    summarize_budget,
    validate_change_set_scope,
)

_NAMESPACE = UUID("7c14a005-0b22-5056-91cb-0f38e50d73e0")
type Owner = tuple[str, UUID | None]


def _require(condition: bool) -> None:
    if not condition:
        raise DomainInvariantError("replan_facts_invalid", field="facts")


def _ids(values: Iterable[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=lambda value: value.hex))


def _retain_live_uncertainty_refs(
    uncertainties: tuple[Uncertainty, ...], removed_refs: set[UUID]
) -> tuple[Uncertainty, ...]:
    retained: list[Uncertainty] = []
    for uncertainty in uncertainties:
        if not uncertainty.affected_refs:
            retained.append(uncertainty)
            continue
        affected_refs = tuple(ref for ref in uncertainty.affected_refs if ref not in removed_refs)
        if not affected_refs:
            continue
        retained.append(
            uncertainty
            if affected_refs == uncertainty.affected_refs
            else uncertainty.model_copy(update={"affected_refs": affected_refs})
        )
    return tuple(retained)


def _index[T](values: Iterable[T], key: Callable[[T], UUID]) -> dict[UUID, T]:
    items = tuple(values)
    result = {key(value): value for value in items}
    _require(len(result) == len(items) and all(isinstance(k, UUID) for k in result))
    return result


def _stable(label: str) -> UUID:
    return uuid5(_NAMESPACE, label)


def _normal(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _normal(asdict(value))
    if isinstance(value, BaseModel):
        return _normal(value.model_dump(mode="python", warnings=False))
    if isinstance(value, datetime):
        _require(value.utcoffset() is not None)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        _require(value.is_finite())
        return format(value.normalize(), "f")
    if isinstance(value, UUID | AnyUrl):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        # Reference collections are sets; activity/route sequence order is not.
        return {
            k: _normal(sorted(v, key=str) if k in {"source_ids", "affected_refs"} else v)
            for k, v in value.items()
        }
    if isinstance(value, tuple | list):
        return [_normal(item) for item in value]
    if isinstance(value, float):
        _require(isfinite(value))
        return value
    _require(value is None or isinstance(value, str | int | bool))
    return value


def _fingerprint(value: Any) -> str:
    payload = json.dumps(_normal(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _money(value: Any) -> Money:
    return Money(value.amount, value.currency)


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    """Closed internal inputs, not caller-granted scope or public diagnostics."""

    operation: str
    local_date: date
    refs: tuple[UUID, ...]
    request: (
        WeatherForecastRequest
        | CurrentWeatherAlertsRequest
        | RouteCalculationRequest
        | PoiSearchRequest
        | PlanningContext
        | PlanRepairBrief
        | CityResolutionRequest
        | None
    )
    result: ProviderResult[object] | BudgetSummaryResult | FinalValidationIssue
    primary: ProviderResult[object] | None = None
    city: CityResolution | None = None
    model_context: PlanningContext | None = None


@dataclass(frozen=True, slots=True)
class ReplanEvidence:
    job_id: UUID
    replan_id: UUID
    baseline_plan_id: UUID
    job_version: int
    command_fingerprint: str
    candidate_fingerprint: str
    events: tuple[EvidenceEvent, ...]
    events_fingerprint: str

    @classmethod
    def bind(
        cls,
        job: PlanningJob,
        replan_id: UUID,
        command: ReplanCommand,
        candidate: PlanningJobResult,
        events: tuple[EvidenceEvent, ...],
    ) -> ReplanEvidence:
        _require(isinstance(job.result, PlanningJobResult) and job.result.plan is not None)
        assert job.result is not None and job.result.plan is not None
        _require(isinstance(events, tuple) and all(type(e) is EvidenceEvent for e in events))
        return cls(
            job.job_id,
            replan_id,
            job.result.plan.plan_id,
            job.version,
            _fingerprint(command),
            _fingerprint(candidate),
            deepcopy(events),
            _fingerprint(events),
        )


@dataclass(frozen=True, slots=True)
class EvidencedReplanResult:
    result: PlanningJobResult
    evidence: ReplanEvidence

    def __post_init__(self) -> None:
        _require(type(self.result) is PlanningJobResult and type(self.evidence) is ReplanEvidence)
        object.__setattr__(self, "result", deepcopy(self.result))
        object.__setattr__(self, "evidence", deepcopy(self.evidence))


def _envelope(
    event: EvidenceEvent, evaluated_at: datetime
) -> tuple[ProviderResult[object], set[DataFreshness]]:
    _require(type(event.result) is ProviderResult)
    assert isinstance(event.result, ProviderResult)
    result = replace(event.result)  # Revalidate even deliberately corrupted frozen objects.
    if result.error is not None:
        replace(result.error)
        _require(result.error.category.value != "unknown")
        _require(
            result.error.reason is None
            or result.error.reason.value
            not in {
                "retry_budget_exhausted",
                "retry_deadline_exhausted",
            }
        )
    freshness = set()
    if result.fetched_at is not None:
        freshness.add(evaluate_freshness(result.fetched_at, result.valid_until, evaluated_at))
    for source in result.source_records:
        replace(source)
        _require(
            source.provider is result.provider
            and source.fetched_at == result.fetched_at
            and source.valid_until == result.valid_until
        )
        freshness.add(evaluate_freshness(source.fetched_at, source.valid_until, evaluated_at))
    return result, freshness


def _public_sources(
    result: ProviderResult[object], after: ReplanFacts, before: ReplanFacts, evaluated_at: datetime
) -> tuple[UUID, ...]:
    ids = tuple(s.source_id for s in result.source_records)
    for source in result.source_records:
        expected = SourceRecord.model_validate(
            dict(
                asdict(source),
                warnings=result.warnings,
                freshness=evaluate_freshness(
                    source.fetched_at, source.valid_until, evaluated_at
                ).value,
            )
        )
        _require(
            source.source_id not in before.sources
            and after.sources.get(source.source_id) == expected
        )
    return ids


class ReplanFacts:
    """One call-owned catalog. Inputs are copied, never updated or retained globally."""

    def __init__(
        self,
        result: PlanningJobResult,
        evaluated_at: datetime,
        *,
        retained_uncertainties: tuple[Uncertainty, ...] = (),
        allowed_missing_uncertainty_refs: frozenset[UUID] = frozenset(),
    ) -> None:
        _require(type(result.plan) in {TripPlan, TripPlanV2})
        assert isinstance(result.plan, TripPlan)
        self.plan = type(result.plan).model_validate(
            result.plan.model_dump(mode="python", warnings=False)
        )
        self.result = result
        self._retained_uncertainties = retained_uncertainties
        self._allowed_missing_uncertainty_refs = allowed_missing_uncertainty_refs
        self.retained_missing_uncertainty_refs: frozenset[UUID] = frozenset()
        self.sources = _index(
            (
                SourceRecord.model_validate(s.model_dump(mode="python", warnings=False))
                for s in result.sources
            ),
            lambda s: s.source_id,
        )
        self.freshness = {
            sid: evaluate_freshness(s.fetched_at, s.valid_until, evaluated_at)
            for sid, s in self.sources.items()
        }
        plan = self.plan
        _require(len(plan.days) == 2 and plan.end_date == plan.start_date + timedelta(days=1))
        _require(tuple(d.local_date for d in plan.days) == (plan.start_date, plan.end_date))
        _require(
            result.resolved_destination is not None
            and result.resolved_destination.adcode == plan.city_adcode
        )
        self.locations = _index(plan.locations, lambda loc: loc.location_id)
        _require(all(loc.city_adcode == plan.city_adcode for loc in plan.locations))
        self.activities = _index((a for d in plan.days for a in d.activities), lambda a: a.item_id)
        self.routes = _index((r for d in plan.days for r in d.routes), lambda r: r.route_id)
        self.costs = _index(plan.budget_summary.cost_items, lambda c: c.cost_id)
        self.owners: dict[UUID, Owner] = {cid: ("plan", None) for cid in self.costs}
        self.consumers: dict[UUID, set[Owner]] = {sid: set() for sid in self.sources}
        self.location_users: dict[UUID, set[UUID | None]] = {loc: set() for loc in self.locations}
        self.activity_days: dict[UUID, PlanDay] = {}
        self.route_parents: dict[UUID, tuple[UUID, ...]] = {}
        self.route_days: dict[UUID, PlanDay] = {}
        self.day_ids = {
            d.local_date: _stable(
                f"day-schedule:{plan.city_adcode}:{d.local_date}:{d.accommodation_location_id}"
            )
            for d in plan.days
        }
        self.schedule_ids = {aid: _stable(f"activity-schedule:{aid}") for aid in self.activities}
        self._catalog()
        self._budget_items = tuple(
            BudgetCostItem(
                c.cost_id,
                CostCategory(c.category),
                CostConfidence(c.confidence),
                _money(c.amount) if c.amount is not None else None,
                c.source_ids,
            )
            for c in self.costs.values()
        )
        summary = recalculate_replan_budget(
            _money(plan.budget_summary.budget), self._budget_items
        ).before
        _require(
            summary.known_total.amount == plan.budget_summary.known_total.amount
            and summary.unknown_count == plan.budget_summary.unknown_count
            and summary.assessment.value == plan.budget_summary.assessment.value
        )
        _require(
            all(
                self.owners[c.cost_id][0] != "plan" or c.category.value != "other"
                for c in self.costs.values()
            )
        )
        self.context = ReplanImpactContext(
            plan.plan_id,
            plan.city_adcode,
            (plan.start_date, plan.end_date),
            _ids(d.accommodation_location_id for d in plan.days),
            tuple(
                ImpactActivity(
                    aid, self.activity_days[aid].local_date, plan.city_adcode, a.source_ids
                )
                for aid, a in self.activities.items()
            ),
            tuple(
                ImpactRoute(
                    rid,
                    self.route_days[rid].local_date,
                    self.route_parents[rid],
                    r.source_ids,
                    self.route_days[rid].accommodation_location_id
                    in {r.origin_location_id, r.destination_location_id},
                )
                for rid, r in self.routes.items()
            ),
            # Required here means retained typed evidence, not provider criticality.
            tuple(ReplanSourceState(sid, self.freshness[sid], True) for sid in self.sources),
        )
        self.snapshots = self._snapshots()

    def _cite(self, ids: tuple[UUID, ...], owner: Owner) -> None:
        _require(len(set(ids)) == len(ids) and not (set(ids) - self.sources.keys()))
        for sid in ids:
            self.consumers[sid].add(owner)

    def _loc(self, location: UUID, user: UUID | None) -> None:
        _require(location in self.locations)
        self.location_users[location].add(user)

    def _own(self, cost: CostItem, kind: str, ref: UUID) -> None:
        _require(cost.cost_id in self.costs and cost == self.costs[cost.cost_id])
        _require(self.owners[cost.cost_id] == ("plan", None))
        self.owners[cost.cost_id] = (kind, ref)

    def _catalog(self) -> None:
        for day in self.plan.days:
            self._loc(day.accommodation_location_id, None)
            nodes = [
                day.accommodation_location_id,
                *(a.location_id for a in day.activities),
                day.accommodation_location_id,
            ]
            expected_edges = len(day.activities) + 1 if day.activities else 0
            _require(len(day.routes) == expected_edges)
            for activity in day.activities:
                self._loc(activity.location_id, activity.item_id)
                self.activity_days[activity.item_id] = day
                self._cite(activity.source_ids, ("activity", activity.item_id))
                _require(activity.end_time > activity.start_time)
                for cost in activity.cost_items:
                    self._own(cost, "activity", activity.item_id)
            for i, route in enumerate(day.routes):
                _require(
                    (route.origin_location_id, route.destination_location_id)
                    == (nodes[i], nodes[i + 1])
                )
                self._loc(route.origin_location_id, route.route_id)
                self._loc(route.destination_location_id, route.route_id)
                self.route_days[route.route_id] = day
                self.route_parents[route.route_id] = tuple(
                    a.item_id for a in day.activities[max(0, i - 1) : i + 1]
                )
                self._cite(route.source_ids, ("route", route.route_id))
                if route.fare is not None:
                    self._own(route.fare, "route", route.route_id)
            if day.weather is not None:
                _require(day.weather.forecast_date == day.local_date)
                self._loc(day.weather.location_id, self.day_ids[day.local_date])
                self._cite(day.weather.source_ids, ("weather", self.day_ids[day.local_date]))
                for alert in day.weather.alerts:
                    self._cite(alert.source_ids, ("weather", self.day_ids[day.local_date]))
        for loc in self.locations.values():
            self._cite(loc.source_ids, ("location", loc.location_id))
        for cost in self.costs.values():
            self._cite(cost.source_ids, ("cost", cost.cost_id))
        assert self.result.resolved_destination is not None
        self._cite(self.result.resolved_destination.source_ids, ("destination", None))
        references = {*self.activities, *self.routes, *self.locations, *self.costs, *self.sources}
        self.reference_ids = frozenset(references)
        retained_missing: set[UUID] = set()
        for index, uncertainty in enumerate(self.result.uncertainties):
            missing = set(uncertainty.affected_refs) - references
            if missing:
                _require(
                    index < len(self._retained_uncertainties)
                    and uncertainty == self._retained_uncertainties[index]
                    and missing <= self._allowed_missing_uncertainty_refs
                )
                retained_missing.update(missing)
            self._cite(uncertainty.source_ids, ("uncertainty", None))
        self.retained_missing_uncertainty_refs = frozenset(retained_missing)
        for violation in self.result.violations:
            _require(set(violation.affected_refs) <= references)
        for sid, source in self.sources.items():
            if not self.consumers[sid] or source.provider.value in {"deepseek", "system"}:
                self.consumers[sid].add(("provenance", None))

    def _snapshots(self) -> tuple[PlanEntitySnapshot, ...]:
        entries: list[PlanEntitySnapshot] = []

        def add(ref: UUID, kind: ChangeEntityKind, value: Any) -> None:
            entries.append(PlanEntitySnapshot(ref, kind, _fingerprint(value)))

        for aid, a in self.activities.items():
            add(
                aid,
                ChangeEntityKind.ACTIVITY,
                (
                    a.model_dump(exclude={"start_time", "end_time", "cost_items"}),
                    self.locations[a.location_id],
                    _ids(c.cost_id for c in a.cost_items),
                ),
            )
            add(
                self.schedule_ids[aid],
                ChangeEntityKind.SCHEDULE,
                (self.activity_days[aid].local_date, a.start_time, a.end_time),
            )
        for rid, r in self.routes.items():
            add(
                rid,
                ChangeEntityKind.ROUTE,
                (
                    r.model_dump(exclude={"fare"}),
                    self.locations[r.origin_location_id],
                    self.locations[r.destination_location_id],
                    r.fare.cost_id if r.fare else None,
                    self.route_days[rid].local_date,
                ),
            )
        for cid, c in self.costs.items():
            add(cid, ChangeEntityKind.COST, (c, self.owners[cid]))
        for sid, source in self.sources.items():
            payload = source.model_dump(exclude={"freshness"})
            payload["freshness"] = self.freshness[sid].value
            add(sid, ChangeEntityKind.SOURCE, payload)
        for day in self.plan.days:
            add(
                self.day_ids[day.local_date],
                ChangeEntityKind.SCHEDULE,
                (
                    day.local_date,
                    day.accommodation_location_id,
                    day.weather,
                    tuple(a.item_id for a in day.activities),
                ),
            )
        _index(entries, lambda s: s.ref_id)
        return tuple(sorted(entries, key=lambda s: s.ref_id.hex))

    def roots(self, command: ReplanCommand) -> tuple[set[UUID], set[UUID]]:
        impact = classify_replan_impact(self.context, command)
        return set(impact.direct_refs), set(impact.route_refs)

    def scoped_costs(self, command: ReplanCommand) -> set[UUID]:
        acts, routes = self.roots(command)
        if isinstance(command, AdjustActivityTime):
            return set()
        result = {
            cid
            for cid, (kind, ref) in self.owners.items()
            if (kind == "route" and ref in routes)
            or (kind == "activity" and ref in acts and not isinstance(command, ReorderActivities))
        }
        for cid, cost in self.costs.items():
            if self.owners[cid][0] == "plan" and (
                cost.category.value == "local_transport"
                or (cost.category.value == "ticket" and not isinstance(command, ReorderActivities))
            ):
                result.add(cid)
        return result

    def budget_effect(self, command: ReplanCommand) -> ReplanBudgetResult:
        affected = self.scoped_costs(command)
        replacements = tuple(
            replace(c, confidence=CostConfidence.UNKNOWN, amount=None)
            for c in self._budget_items
            if c.cost_id in affected
            and not (
                isinstance(command, DeleteActivity)
                and self.owners[c.cost_id] == ("activity", command.target_activity_id)
            )
        )
        if isinstance(command, ReplaceActivity) and not any(
            self.owners[cid] == ("activity", command.target_activity_id) for cid in affected
        ):
            replacements += (
                BudgetCostItem(
                    _stable(f"pending-cost:{command.target_activity_id}:{command.operation}"),
                    CostCategory.TICKET,
                    CostConfidence.UNKNOWN,
                    None,
                ),
            )
        return recalculate_replan_budget(
            _money(self.plan.budget_summary.budget),
            self._budget_items,
            remove_cost_ids=_ids(affected),
            replacement_items=replacements,
        )

    def source_actions(self, command: ReplanCommand) -> tuple[SourceActionRecord, ...]:
        acts, routes = self.roots(command)
        affected = acts | routes | self.scoped_costs(command)
        affected.update(self.day_ids[self.activity_days[aid].local_date] for aid in acts)
        removed: set[Owner] = set()
        if isinstance(command, DeleteActivity):
            removed.add(("activity", command.target_activity_id))
            removed.update(
                ("cost", cid)
                for cid, owner in self.owners.items()
                if owner == ("activity", command.target_activity_id)
            )
        drops = {sid for sid, users in self.consumers.items() if users <= removed}
        refreshed = {
            sid for sid, users in self.consumers.items() if any(ref in affected for _, ref in users)
        } - drops
        proposed = plan_source_actions(
            self.context.sources,
            affected_source_ids=_ids(refreshed),
            dropped_source_ids=_ids(drops),
        )
        return tuple(
            replace(
                a,
                action=SourceAction.REUSE,
                reason=SourceActionReason.UNKNOWN_VALIDITY
                if a.freshness is DataFreshness.UNKNOWN_VALIDITY
                else SourceActionReason.UNAFFECTED_FRESH,
            )
            if self.sources[a.source_id].provider.value in {"user", "system"}
            and a.action is not SourceAction.DROP
            else a
            for a in proposed
        )

    def allowed(self, command: ReplanCommand) -> set[UUID]:
        acts, routes = self.roots(command)
        allowed = acts | routes | self.scoped_costs(command)
        allowed.update(self.schedule_ids[aid] for aid in acts)
        allowed.update(self.day_ids[self.activity_days[aid].local_date] for aid in acts)
        allowed.update(
            loc for loc, users in self.location_users.items() if users and users <= allowed
        )
        for action in self.source_actions(command):
            if action.action is not SourceAction.REUSE and all(
                ref in allowed for _, ref in self.consumers[action.source_id]
            ):
                allowed.add(action.source_id)
        return allowed


class ReplanFactProjector:
    def project(self, result: object, *, evaluated_at: datetime) -> ReplanFacts:
        try:
            _require(isinstance(result, PlanningJobResult))
            _require(isinstance(evaluated_at, datetime) and evaluated_at.utcoffset() is not None)
            assert isinstance(result, PlanningJobResult)
            return ReplanFacts(result, evaluated_at)
        except (ValueError, TypeError, AttributeError, KeyError, IndexError):
            raise DomainInvariantError("replan_facts_invalid", field="facts") from None

    def _job(self, job: PlanningJob, evaluated_at: datetime) -> ReplanFacts:
        facts = self.project(job.result, evaluated_at=evaluated_at)
        _require(type(job.request) in {TripPlanRequest, TripPlanRequestV2})
        assert isinstance(job.request, TripPlanRequest)
        request = job.request
        _require(isinstance(request, TripPlanRequestV2) == isinstance(facts.plan, TripPlanV2))
        _require(
            request.start_date == facts.plan.start_date
            and request.total_budget == facts.plan.budget_summary.budget
            and request_fingerprint(request) == job.request_fingerprint
        )
        if isinstance(request, TripPlanRequestV2):
            _require(request.end_date == facts.plan.end_date)
        return facts

    def _candidate(
        self,
        before: ReplanFacts,
        command: ReplanCommand,
        result: PlanningJobResult,
        allowed: set[UUID],
        evaluated_at: datetime,
    ) -> ReplanFacts:
        historical = before.result.uncertainties
        if result.uncertainties[: len(historical)] != historical:
            after = ReplanFacts(result, evaluated_at)
            normalized = self._retained_uncertainties(before, after, command)
            _require(result.uncertainties[: len(normalized)] == normalized)
            return after
        missing_refs = frozenset(
            ref
            for uncertainty in historical
            for ref in uncertainty.affected_refs
            if ref in before.reference_ids and ref in allowed
        )
        return ReplanFacts(
            result,
            evaluated_at,
            retained_uncertainties=historical,
            allowed_missing_uncertainty_refs=missing_refs,
        )

    def _retained_uncertainties(
        self, before: ReplanFacts, after: ReplanFacts, command: ReplanCommand
    ) -> tuple[Uncertainty, ...]:
        if after.retained_missing_uncertainty_refs:
            return before.result.uncertainties
        removed_refs = before.reference_ids - after.reference_ids
        return _retain_live_uncertainty_refs(before.result.uncertainties, set(removed_refs))

    def normalize_delete_result(
        self,
        job: PlanningJob,
        command: DeleteActivity,
        impact: ImpactAnalysis,
        result: PlanningJobResult,
        *,
        evaluated_at: datetime,
        evidence: ReplanEvidence | None = None,
    ) -> PlanningJobResult:
        """Compatibility entry for callers requiring a delete-only operation."""
        _require(isinstance(command, DeleteActivity))
        return self.normalize_result(
            job, command, impact, result, evaluated_at=evaluated_at, evidence=evidence
        )

    def normalize_result(
        self,
        job: PlanningJob,
        command: ReplanCommand,
        impact: ImpactAnalysis,
        result: PlanningJobResult,
        *,
        evaluated_at: datetime,
        evidence: ReplanEvidence | None = None,
    ) -> PlanningJobResult:
        """Keep history live after strictly validating the candidate and removals."""
        before = self._job(job, evaluated_at)
        allowed = before.allowed(command)
        after = self._candidate(before, command, result, allowed, evaluated_at)
        changes = self.changes(
            job,
            command,
            impact,
            result,
            evaluated_at=evaluated_at,
            evidence=evidence,
        )
        removed_refs = set(changes.removed_refs)
        _require(before.reference_ids - after.reference_ids <= removed_refs <= allowed)
        historical = before.result.uncertainties
        normalized_history = _retain_live_uncertainty_refs(historical, removed_refs)
        normalized = replace(
            result,
            uncertainties=(*normalized_history, *result.uncertainties[len(historical) :]),
        )
        normalized_after = ReplanFacts(normalized, evaluated_at)
        _require(
            normalized_history == self._retained_uncertainties(before, normalized_after, command)
        )
        return normalized

    def analyze(
        self, job: PlanningJob, command: ReplanCommand, *, evaluated_at: datetime
    ) -> ImpactAnalysis:
        facts = self._job(job, evaluated_at)
        budget = facts.budget_effect(command)
        original = classify_replan_impact(facts.context, command, budget_effect=budget)
        actions = facts.source_actions(command)
        categories = set(original.categories) - {ImpactCategory.SAME_DAY_LOW}
        if any(a.action is SourceAction.REFRESH for a in actions):
            categories.add(ImpactCategory.SOURCE_REFRESH)
        if budget.after.unknown_count:
            categories.add(ImpactCategory.BUDGET_RISK)
        if any(a.freshness is DataFreshness.UNKNOWN_VALIDITY for a in actions):
            categories.add(ImpactCategory.UNKNOWN_IMPACT)
        disposition = original.disposition
        if disposition is not ImpactDisposition.REJECT and categories:
            disposition = ImpactDisposition.CONFIRM
        validations = set(original.required_validations)
        if ImpactCategory.BUDGET_RISK in categories:
            validations.add("budget")
        return replace(
            original,
            categories=tuple(c for c in ImpactCategory if c in categories)
            or (ImpactCategory.SAME_DAY_LOW,),
            disposition=disposition,
            source_actions=actions,
            required_validations=tuple(sorted(validations)),
            confirmation_required=disposition is ImpactDisposition.CONFIRM,
            transitive_refs=_ids(facts.allowed(command) - set(original.direct_refs)),
        )

    def changes(
        self,
        job: PlanningJob,
        command: ReplanCommand,
        impact: ImpactAnalysis,
        result: PlanningJobResult,
        *,
        evaluated_at: datetime,
        evidence: ReplanEvidence | None = None,
    ) -> PlanChangeSet:
        before = self._job(job, evaluated_at)
        allowed = before.allowed(command)
        after = self._candidate(before, command, result, allowed, evaluated_at)
        current = self.analyze(job, command, evaluated_at=evaluated_at)
        # Re-evaluation may strengthen protection, never silently extend approved scope.
        _require(
            current.direct_refs == impact.direct_refs and current.route_refs == impact.route_refs
        )
        _require(
            set(current.transitive_refs) <= set(impact.transitive_refs)
            and set(current.required_validations) <= set(impact.required_validations)
            and set(current.categories) <= set(impact.categories)
        )
        roots = set(current.direct_refs) | set(current.route_refs)
        if evidence is not None:
            _require(type(evidence) is ReplanEvidence)
            _require(
                (evidence.job_id, evidence.job_version, evidence.baseline_plan_id)
                == (job.job_id, job.version, before.plan.plan_id)
            )
            _require(
                evidence.command_fingerprint == _fingerprint(command)
                and evidence.candidate_fingerprint == _fingerprint(result)
                and evidence.events_fingerprint == _fingerprint(evidence.events)
            )
            parents = self._origins(before, after, command, allowed, roots, include_sources=False)
            self._evidence(
                job,
                before,
                after,
                command,
                evidence.events,
                allowed,
                roots,
                parents,
                evaluated_at,
            )
        parents = self._origins(before, after, command, allowed, roots)
        self._guards(before, after, command, allowed, evidenced=evidence is not None)
        existing = {s.ref_id for s in before.snapshots}
        snapshots = []
        for snapshot in after.snapshots:
            if snapshot.ref_id not in existing:
                ancestry = parents.get(snapshot.ref_id, set())
                _require(bool(ancestry) and ancestry <= roots)
                snapshot = replace(snapshot, origin_ref_id=_ids(ancestry)[0])
            snapshots.append(snapshot)
        changes = build_plan_change_set(
            before.plan.plan_id, after.plan.plan_id, before.snapshots, tuple(snapshots)
        )
        validate_change_set_scope(changes, allowed_refs=_ids(allowed))
        _require(after.retained_missing_uncertainty_refs <= set(changes.removed_refs))
        return changes

    def _origins(
        self,
        before: ReplanFacts,
        after: ReplanFacts,
        command: ReplanCommand,
        allowed: set[UUID],
        roots: set[UUID],
        *,
        include_sources: bool = True,
    ) -> dict[UUID, set[UUID]]:
        parents: dict[UUID, set[UUID]] = {}
        for old, new in zip(before.plan.days, after.plan.days, strict=True):
            old_ids = tuple(a.item_id for a in old.activities)
            new_ids = tuple(a.item_id for a in new.activities)
            target = (
                command.target_activity_id if not isinstance(command, ReorderActivities) else None
            )
            expected = old_ids
            if isinstance(command, DeleteActivity):
                expected = tuple(aid for aid in old_ids if aid != target)
            elif isinstance(command, ReorderActivities) and old.local_date == command.local_date:
                expected = command.ordered_activity_ids
            elif isinstance(command, ReplaceActivity) and target in old_ids:
                _require(len(new_ids) == len(old_ids))
                replacement = new_ids[old_ids.index(target)]
                _require(replacement == target or replacement not in before.activities)
                expected = tuple(replacement if aid == target else aid for aid in old_ids)
                parents[replacement] = {command.target_activity_id}
            _require(new_ids == expected)
            for aid in new_ids:
                parents.setdefault(aid, {aid})
                parents[after.schedule_ids[aid]] = parents[aid]
            old_nodes: tuple[UUID | None, ...] = (None, *old_ids, None)
            new_nodes: tuple[UUID | None, ...] = (None, *new_ids, None)
            for i, route in enumerate(new.routes):
                left, right = new_nodes[i : i + 2]
                left = next(iter(parents[left])) if left is not None else None
                right = next(iter(parents[right])) if right is not None else None
                start = 0 if i == 0 else old_nodes.index(left)
                end = len(old_nodes) - 1 if i == len(new.routes) - 1 else old_nodes.index(right)
                if isinstance(command, ReorderActivities) and old.local_date == command.local_date:
                    indices = {
                        j
                        for j in range(len(old.routes))
                        if old_nodes[j] in {left, right} or old_nodes[j + 1] in {left, right}
                    }
                else:
                    _require(start < end)
                    indices = set(range(start, end))
                ancestry = {old.routes[j].route_id for j in indices}
                if route.route_id in before.routes:
                    _require(route.route_id in ancestry)
                parents[route.route_id] = ancestry
            day_roots = {aid for aid in old_ids if aid in roots}
            parents[after.day_ids[new.local_date]] = day_roots
        for cid, (kind, ref) in after.owners.items():
            if kind != "plan":
                assert ref is not None
                parents[cid] = parents[ref]
            elif after.costs[cid].category.value == "ticket":
                parents[cid] = set(before.roots(command)[0])
            elif after.costs[cid].category.value == "local_transport":
                parents[cid] = set(before.roots(command)[1])
        for loc, users in after.location_users.items():
            parents[loc] = set().union(
                *(parents.get(ref, set()) for ref in users if ref is not None)
            )
            if None in users or not users or any(ref not in parents for ref in users):
                parents[loc] = set()
        for sid, consumers in after.consumers.items() if include_sources else ():
            if sid in before.sources:
                continue
            source_ancestry: set[UUID] = set()
            for _, ref in consumers:
                _require(ref is not None and bool(parents.get(ref)) and parents[ref] <= roots)
                assert ref is not None
                source_ancestry.update(parents[ref])
            parents[sid] = source_ancestry
        # Same-ID costs cannot migrate from an unrelated owner into a permitted root.
        for cid in before.costs.keys() & after.costs.keys():
            if before.owners[cid] != after.owners[cid]:
                _require(cid in allowed and bool(parents.get(cid)) and parents[cid] <= roots)
        return parents

    def _evidence(
        self,
        job: PlanningJob,
        before: ReplanFacts,
        after: ReplanFacts,
        command: ReplanCommand,
        events: tuple[EvidenceEvent, ...],
        allowed: set[UUID],
        roots: set[UUID],
        parents: dict[UUID, set[UUID]],
        evaluated_at: datetime,
    ) -> None:
        errors: list[ApiError] = []
        warnings: list[str] = []
        uncertainties: list[Uncertainty] = []

        def issue(
            code: str, refs: tuple[UUID, ...], sources: tuple[UUID, ...] = (), *, warn: bool = False
        ) -> None:
            message = _ISSUE_MESSAGES[FinalValidationIssueCode(code)].format(trip_day_label="两日")
            uncertainties.append(
                Uncertainty(code=code, message=message, affected_refs=refs, source_ids=sources)
            )
            if warn:
                warnings.append(message)

        _require(isinstance(events, tuple) and all(type(e) is EvidenceEvent for e in events))
        _require(
            all(
                before.sources[sid] == after.sources[sid]
                for sid in before.sources.keys() & after.sources.keys()
            )
        )
        ordered = sorted(
            events, key=lambda e: (e.local_date, e.operation, _ids(e.refs), _fingerprint(e))
        )
        unique = list({_fingerprint(e): e for e in ordered}.values())
        scoped_unknown_cost_refs = _ids(
            cost_id
            for cost_id, cost in after.costs.items()
            if cost.confidence.value == "unknown"
            and (
                cost_id in allowed
                or cost_id not in before.costs
                and bool(parents.get(cost_id))
                and parents[cost_id] <= roots
            )
        )
        _require(
            len([event for event in unique if event.operation == "budget"])
            == (1 if scoped_unknown_cost_refs else 0)
        )
        self._context_sources(job, before, after, unique, parents, roots, evaluated_at)
        handled: set[tuple[date, str, tuple[UUID, ...]]] = set()
        _require(after.plan.budget_summary.assessment.value != "over_budget")
        for old, new in zip(before.plan.days, after.plan.days, strict=True):
            window = next(
                w
                for w in job.request.day_windows
                if w.day_offset == (new.local_date - after.plan.start_date).days
            )
            chain = DailyRoutePlan(
                new.accommodation_location_id,
                DailyAvailability(window.day_offset, window.start_time, window.end_time),
                tuple(
                    RouteActivity(a.item_id, a.location_id, a.start_time, a.end_time)
                    for a in new.activities
                ),
                tuple(
                    RouteLeg(
                        r.origin_location_id,
                        r.destination_location_id,
                        RouteMode(r.mode),
                        r.distance_meters,
                        r.duration_minutes,
                        r.source_ids,
                    )
                    for r in new.routes
                ),
            )
            _require(chain.validate().status is RouteValidationStatus.VERIFIED)
            expected = old.weather
            refs = _ids(
                a.item_id
                for a in new.activities
                if parents.get(a.item_id) and parents[a.item_id] <= roots
            )
            if not refs:
                refs = _ids(
                    r.route_id
                    for r in new.routes
                    if parents.get(r.route_id) and parents[r.route_id] <= roots
                )
            day_events = [e for e in unique if e.local_date == old.local_date]
            # Forecast determines whether the existing DTO can carry any alerts.
            for event in sorted(day_events, key=lambda e: e.operation != "forecast"):
                key = (event.local_date, event.operation, event.refs)
                _require(key not in handled and bool(event.refs) and event.refs == _ids(event.refs))
                _require(
                    all(
                        r not in after.sources and parents.get(r) and parents[r] <= roots
                        for r in event.refs
                    )
                )
                handled.add(key)
                if event.operation not in {"forecast", "alerts"}:
                    for code, source_ids in self._nonweather(
                        job,
                        before,
                        after,
                        event,
                        refs,
                        scoped_unknown_cost_refs,
                        evaluated_at,
                        errors,
                    ):
                        if code == "route_mode_fallback_used":
                            warnings.append(
                                _SCHEDULING_WARNING_MESSAGES[
                                    SchedulingWarningCode.ROUTE_MODE_FALLBACK_USED
                                ]
                            )
                        else:
                            issue(code, event.refs, source_ids, warn=code == "provider_degraded")
                    continue
                _require(event.primary is None and event.city is None)
                _require(
                    before.day_ids[old.local_date] in allowed and bool(refs) and event.refs == refs
                )
                request = event.request
                forecast = event.operation == "forecast"
                _require(
                    type(request)
                    is (WeatherForecastRequest if forecast else CurrentWeatherAlertsRequest)
                )
                assert isinstance(request, WeatherForecastRequest | CurrentWeatherAlertsRequest)
                location_id = (
                    old.weather.location_id
                    if old.weather is not None
                    else old.accommodation_location_id
                )
                location = before.locations[location_id]
                _require(
                    request.location_id == location_id
                    and location_id in after.locations
                    and after.locations[location_id].model_dump(exclude={"source_ids"})
                    == location.model_dump(exclude={"source_ids"})
                    and _normal(request.coordinates) == _normal(location.coordinates)
                )
                if isinstance(request, WeatherForecastRequest):
                    _require(
                        before.plan.start_date
                        <= request.start_date
                        <= old.local_date
                        <= request.end_date
                        <= before.plan.end_date
                    )
                result, freshness = _envelope(event, evaluated_at)
                _require(result.provider is Provider.QWEATHER)
                source_type = "qweather_daily_forecast" if forecast else "qweather_current_alerts"
                _require(all(s.source_type == source_type for s in result.source_records))
                data = result.data
                if data is not None:
                    _require(
                        type(data) is (WeatherForecastResult if forecast else WeatherAlertsResult)
                    )
                    assert isinstance(data, WeatherForecastResult | WeatherAlertsResult)
                    _require(data.location_id == request.location_id)
                stale = DataFreshness.STALE in freshness
                missing = result.status is ProviderResultStatus.UNAVAILABLE or stale
                used = False
                source_ids = tuple(s.source_id for s in result.source_records)
                if forecast:
                    assert data is None or isinstance(data, WeatherForecastResult)
                    days = () if data is None else data.days
                    _require(len({d.forecast_date for d in days}) == len(days))
                    target = next((d for d in days if d.forecast_date == old.local_date), None)
                    missing = missing or target is None
                    if missing:
                        expected = None
                    else:
                        assert target is not None
                        expected = WeatherSnapshot(
                            **asdict(target),
                            location_id=location_id,
                            source_ids=source_ids,
                            alerts=old.weather.alerts if old.weather else (),
                        )
                        used = True
                else:
                    assert data is None or isinstance(data, WeatherAlertsResult)
                    alerts = (
                        ()
                        if data is None or missing
                        else tuple(
                            WeatherAlert(**asdict(a), source_ids=source_ids) for a in data.alerts
                        )
                    )
                    _require(len({a.alert_id for a in alerts}) == len(alerts))
                    _require(
                        all(a.issued_at is None or a.issued_at <= evaluated_at for a in alerts)
                    )
                    if expected is not None:
                        expected = expected.model_copy(update={"alerts": alerts})
                        used = not missing and (
                            bool(alerts)
                            or result.status is ProviderResultStatus.PARTIAL
                            or DataFreshness.UNKNOWN_VALIDITY in freshness
                        )
                errors.extend(_provider_errors((result,)))
                if stale:
                    errors.append(
                        ApiError(
                            code=ApiErrorCode.DATA_STALE,
                            message=_PROVIDER_ERROR_MESSAGES[ApiErrorCode.DATA_STALE],
                            provider="qweather",
                            diagnostic_code="weather_forecast_stale"
                            if forecast
                            else "weather_alert_stale",
                            retryable=False,
                        )
                    )
                if missing:
                    issue("weather_incomplete", refs, warn=True)
                if used:
                    _public_sources(result, after, before, evaluated_at)
                    if result.status is ProviderResultStatus.PARTIAL:
                        issue("provider_degraded", refs, source_ids, warn=True)
                    if DataFreshness.UNKNOWN_VALIDITY in freshness:
                        issue("source_validity_unknown", refs, source_ids)
            _require(new.weather == expected)
            if expected is not None:
                ids = (*expected.source_ids, *(s for a in expected.alerts for s in a.source_ids))
                _require(all(after.freshness[s] is not DataFreshness.STALE for s in ids))
        _require(len(handled) == len(unique))  # Wrong-date/unrecognized evidence never disappears.
        for name, additions, capacity in (
            ("errors", errors, 20),
            ("warnings", warnings, 50),
            ("uncertainties", uncertainties, 50),
        ):
            old_values = (
                self._retained_uncertainties(before, after, command)
                if name == "uncertainties"
                else getattr(before.result, name)
            )
            expected_values = (
                *old_values,
                *(v for i, v in enumerate(additions) if v not in additions[:i]),
            )
            _require(
                len(expected_values) <= capacity and getattr(after.result, name) == expected_values
            )
        if errors or warnings or uncertainties or before.result.status is PlanningStatus.PARTIAL:
            _require(after.result.status is PlanningStatus.PARTIAL)
        # Only newly proved diagnostics get local ownership; all historical consumers stay global.
        historical = {s for u in before.result.uncertainties for s in u.source_ids}
        for uncertainty in uncertainties:
            for sid in uncertainty.source_ids:
                if sid not in historical:
                    after.consumers[sid].discard(("uncertainty", None))
                for ref in uncertainty.affected_refs:
                    _require(
                        ref not in after.sources
                        and bool(parents.get(ref))
                        and parents[ref] <= roots
                    )
                    after.consumers[sid].add(("diagnostic", ref))

    def _context_sources(
        self,
        job: PlanningJob,
        before: ReplanFacts,
        after: ReplanFacts,
        events: list[EvidenceEvent],
        parents: dict[UUID, set[UUID]],
        roots: set[UUID],
        at: datetime,
    ) -> None:
        """Prove context consumers before replacing only new unowned placeholders."""
        context_ops = {"model_generate", "model_repair", "city"}
        assert isinstance(job.request, TripPlanRequest | TripPlanRequestV2)
        uses: dict[str, tuple[UUID, ...]] = {}
        calls: dict[UUID, str] = {}
        for event in events:
            _require(event.operation == "model_repair" or event.model_context is None)
            if isinstance(event.result, ProviderResult):
                signature = _fingerprint(
                    (
                        event.operation,
                        event.request,
                        event.result,
                        event.primary,
                        event.city,
                        event.model_context,
                    )
                )
                for source in event.result.source_records:
                    _require(calls.setdefault(source.source_id, signature) == signature)
        # Model selections establish consumers independently; city then follows real dependencies.
        selected = sorted(
            (e for e in events if e.operation in context_ops), key=lambda e: e.operation == "city"
        )
        for event in selected:
            model = event.operation != "city"
            _require(event.primary is None and event.city is None)
            result, freshness = _envelope(event, at)
            _require(
                result.status is not ProviderResultStatus.UNAVAILABLE and result.data is not None
            )
            _require(result.provider is (Provider.DEEPSEEK if model else Provider.AMAP))
            expected_type = {
                "city": "amap_geocode",
                "model_generate": "model_plan_proposal",
                "model_repair": "model_plan_proposal_repair",
            }[event.operation]
            _require(
                bool(result.source_records)
                and all(s.source_type == expected_type for s in result.source_records)
            )
            ids = _public_sources(result, after, before, at)
            day = next((d for d in after.plan.days if d.local_date == event.local_date), None)
            _require(day is not None)
            assert day is not None
            eligible = {ref for ref, origin in parents.items() if origin and origin <= roots}
            local = [e for e in events if e.local_date == event.local_date]
            if model:
                _require(DataFreshness.STALE not in freshness and type(result.data) is PlanProposal)
                context = (
                    event.model_context if event.operation == "model_repair" else event.request
                )
                _require(type(context) is PlanningContext)
                assert isinstance(context, PlanningContext)
                if event.operation == "model_repair":
                    _require(type(event.request) is PlanRepairBrief)
                    assert isinstance(event.request, PlanRepairBrief)
                    _require(
                        isinstance(event.request.validation_code, CandidateValidationCode)
                        and event.request.validation_code is not CandidateValidationCode.UNSAFE_TEXT
                        and event.request == _repair_brief(context, event.request.validation_code)
                    )
                self._model_context(job, before, after, context, events)
                proposal = cast(PlanProposal, result.data)
                payload = _normal(proposal)
                for item in payload["days"]:
                    for field in (
                        "departure_city_index",
                        "arrival_city_index",
                        "overnight_city_index",
                    ):
                        _require(item.pop(field) is None)
                _require(parse_plan_proposal(json.dumps(payload), context) == proposal)
                choices = next(
                    d.selections for d in proposal.days if d.local_date == day.local_date
                )
                ordered_locations = tuple(a.location_id for a in day.activities)
                # A proposed chain must actually be adopted in order, not merely mention a POI.
                _require(tuple(s.location_id for s in choices) == ordered_locations)
                consumers = {a.item_id for a in day.activities if a.item_id in eligible}
                for activity in day.activities:
                    previous = before.activities.get(activity.item_id)
                    if previous is None or activity.title != previous.title:
                        _require(activity.title == after.locations[activity.location_id].name)
                nodes = (
                    day.accommodation_location_id,
                    *ordered_locations,
                    day.accommodation_location_id,
                )
                edges = set(zip(nodes, nodes[1:], strict=False))
                for downstream in local:
                    if downstream.operation in {"route", "fallback"}:
                        for ref in downstream.refs:
                            route = after.routes.get(ref)
                            if (
                                route is not None
                                and ref in eligible
                                and (route.origin_location_id, route.destination_location_id)
                                in edges
                            ):
                                consumers.add(ref)
            else:
                _require(
                    type(event.request) is CityResolutionRequest
                    and event.request == CityResolutionRequest(job.request.city)
                    and type(result.data) is CityResolution
                )
                city = cast(CityResolution, result.data)
                _require(
                    city.adcode == before.plan.city_adcode
                    and city.citycode.isdigit()
                    and 2 <= len(city.citycode) <= 4
                    and bool(city.city_name)
                )
                consumers = set()
                for downstream in local:
                    if downstream.operation in {"route", "fallback"}:
                        _require(
                            downstream.city == city
                            and isinstance(downstream.request, RouteCalculationRequest)
                            and downstream.request.origin_citycode == city.citycode
                            and downstream.request.destination_citycode == city.citycode
                        )
                        consumers.update(downstream.refs)
                    elif downstream.operation == "location":
                        _require(
                            isinstance(downstream.request, PoiSearchRequest)
                            and downstream.request.city_adcode == city.adcode
                        )
                        consumers.update(downstream.refs)
                    elif downstream.operation in {"model_generate", "model_repair"}:
                        context = downstream.model_context or downstream.request
                        _require(
                            isinstance(context, PlanningContext)
                            and context.city_name == city.city_name
                            and context.city_adcode == city.adcode
                        )
                        consumers.update(uses[_fingerprint(downstream)])
            _require(bool(consumers) and consumers <= eligible and event.refs == _ids(consumers))
            uses[_fingerprint(event)] = event.refs
            for sid in ids:
                # No factual/global ownership may hide behind one valid decision consumer.
                _require(
                    after.consumers[sid]
                    <= {
                        ("provenance", None),
                        ("uncertainty", None),
                        *(("context", ref) for ref in eligible),
                    }
                )
                _require(not any(sid in u.source_ids for u in before.result.uncertainties))
                after.consumers[sid].discard(("provenance", None))
                after.consumers[sid].update(("context", ref) for ref in consumers)

    def _model_context(
        self,
        job: PlanningJob,
        before: ReplanFacts,
        after: ReplanFacts,
        context: PlanningContext,
        events: list[EvidenceEvent],
    ) -> None:
        request = job.request
        assert isinstance(request, TripPlanRequest | TripPlanRequestV2)
        anchors = {d.accommodation_location_id for d in before.plan.days}
        _require(len(anchors) == 1)
        anchor = before.locations[next(iter(anchors))]
        catalog = _index(context.locations, lambda loc: loc.location_id)
        _require(bool(catalog) and not catalog.keys() & anchors)
        scope = context.replan_selection_scope
        if scope is None:
            for ref, loc in catalog.items():
                actual = after.locations.get(ref)
                _require(
                    actual is not None
                    and loc
                    == PlanningLocation(
                        actual.location_id, actual.name, actual.category, actual.city_adcode
                    )
                )
                _require(
                    actual == before.locations.get(ref)
                    or any(e.operation == "location" and e.refs == (ref,) for e in events)
                )
            source_ids = _ids(sid for ref in catalog for sid in after.locations[ref].source_ids)
        else:
            baseline = tuple(
                tuple(activity.location_id for activity in day.activities)
                for day in before.plan.days
            )
            baseline_ids = {ref for day in baseline for ref in day}
            allowed_ids = set(scope.allowed_candidate_location_ids)
            _require(
                scope.baseline_location_ids_by_day == baseline
                and len(allowed_ids) == len(scope.allowed_candidate_location_ids)
                and 1 <= len(allowed_ids) <= 5
                and not baseline_ids & allowed_ids
                and set(catalog) == baseline_ids | allowed_ids
            )
            target_day_index = next(
                (
                    index
                    for index, day in enumerate(before.plan.days)
                    if day.local_date == scope.target_local_date
                ),
                -1,
            )
            _require(
                target_day_index >= 0
                and 0
                <= scope.target_selection_index
                < len(before.plan.days[target_day_index].activities)
                and before.plan.days[target_day_index]
                .activities[scope.target_selection_index]
                .item_id
                == scope.target_activity_id
            )
            location_events = [e for e in events if e.operation == "location"]
            _require(len(location_events) == 1)
            location_event = location_events[0]
            _require(
                isinstance(location_event.request, PoiSearchRequest)
                and type(location_event.result) is ProviderResult
                and type(location_event.result.data) is PoiSearchResult
                and location_event.request.city_adcode == before.plan.city_adcode
            )
            assert isinstance(location_event.result, ProviderResult)
            assert isinstance(location_event.result.data, PoiSearchResult)
            eligible = tuple(
                candidate
                for candidate in location_event.result.data.candidates
                if candidate.location_id not in before.locations
                and candidate.coordinates is not None
                and candidate.city_adcode == before.plan.city_adcode
            )[:5]
            _require(
                tuple(candidate.location_id for candidate in eligible)
                == scope.allowed_candidate_location_ids
            )
            offered = {candidate.location_id: candidate for candidate in eligible}
            for ref in baseline_ids:
                actual = before.locations[ref]
                _require(
                    catalog[ref]
                    == PlanningLocation(
                        actual.location_id, actual.name, actual.category, actual.city_adcode
                    )
                )
            for ref in allowed_ids:
                candidate = offered[ref]
                _require(
                    catalog[ref]
                    == PlanningLocation(
                        candidate.location_id,
                        candidate.name,
                        candidate.category,
                        candidate.city_adcode,
                    )
                )
            selected_id = (
                after.plan.days[target_day_index]
                .activities[scope.target_selection_index]
                .location_id
            )
            _require(
                selected_id in allowed_ids
                and location_event.refs == (selected_id,)
                and all(ref not in after.locations for ref in allowed_ids - {selected_id})
            )
            baseline_sources = (
                sid for ref in baseline_ids for sid in before.locations[ref].source_ids
            )
            candidate_sources = (
                source.source_id for source in location_event.result.source_records
            )
            source_ids = _ids((*baseline_sources, *candidate_sources))
        _require(
            bool(source_ids)
            and _ids(context.activity_source_ids) == source_ids
            and len(context.activity_source_ids) == len(source_ids)
        )
        city_events = [e for e in events if e.operation == "city"]
        city_names = {
            e.result.data.city_name
            for e in city_events
            if isinstance(e.result, ProviderResult) and type(e.result.data) is CityResolution
        }
        if not city_events:
            assert before.result.resolved_destination is not None
            city_names = {before.result.resolved_destination.city_name}
        expected = replace(
            context,
            city_adcode=before.plan.city_adcode,
            start_date=before.plan.start_date,
            end_date=before.plan.end_date,
            travelers=request.travelers,
            budget=_money(request.total_budget),
            interests=request.preferences.interests,
            hard_constraints=request.preferences.hard_constraints,
            free_text=request.preferences.free_text,
            allowed_tools=tuple(PlanningToolName),
            day_windows=tuple(
                PlanningDayWindow(w.day_offset, w.start_time, w.end_time)
                for w in request.day_windows
            ),
            accommodation=PlanningLocation(
                anchor.location_id,
                "accommodation anchor",
                "accommodation_anchor",
                anchor.city_adcode,
            ),
            request_version="2" if isinstance(request, TripPlanRequestV2) else None,
            expected_dates=tuple(d.local_date for d in before.plan.days)
            if isinstance(request, TripPlanRequestV2)
            else (),
            city_adcodes=(),
            day_city_indices=(),
            accommodations=(),
        )
        _require(
            context == expected
            and context.city_name in city_names
            and context.route_mode.value in {m.value for m in request.transport_modes}
        )
        observations = {
            ("pois", "POI candidates collected", source_ids),
        }
        for e in events:
            if not isinstance(e.result, ProviderResult):
                continue
            sids = _ids(s.source_id for s in e.result.source_records)
            if e.operation == "city":
                observations.add(("city", "city resolved", sids))
            elif e.operation == "forecast" and isinstance(e.result.data, WeatherForecastResult):
                observations.add(("weather", _weather_summary(cast(Any, e.result)), sids))
            elif e.operation == "alerts" and isinstance(e.result.data, WeatherAlertsResult):
                observations.add(("weather_alerts", _alert_summary(cast(Any, e.result)), sids))
        _require(
            all(
                (o.kind, o.summary, _ids(o.source_ids)) in observations
                for o in context.observations
            )
        )

    def _nonweather(
        self,
        job: PlanningJob,
        before: ReplanFacts,
        after: ReplanFacts,
        event: EvidenceEvent,
        day_refs: tuple[UUID, ...],
        scoped_unknown_cost_refs: tuple[UUID, ...],
        at: datetime,
        errors: list[ApiError],
    ) -> list[tuple[str, tuple[UUID, ...]]]:
        if event.operation in {"budget", "constraint"}:
            _require(event.request is None and event.primary is None and event.city is None)
            if event.operation == "budget":
                summary = summarize_budget(_money(job.request.total_budget), after._budget_items)
                _require(
                    type(event.result) is BudgetSummaryResult
                    and event.result == summary
                    and summary.assessment is BudgetAssessment.INDETERMINATE
                )
                _require(event.refs == scoped_unknown_cost_refs)
                return [("budget_indeterminate", ())]
            _require(isinstance(job.request, TripPlanRequest))
            assert isinstance(job.request, TripPlanRequest)
            _require(bool(job.request.preferences.hard_constraints) and event.refs == day_refs)
            _require(
                event.result
                == FinalValidationIssue(
                    FinalValidationIssueCode.HARD_CONSTRAINT_UNVERIFIED,
                    FinalValidationSeverity.PARTIAL,
                )
            )
            return [("hard_constraint_unverified", ())]
        if event.operation in {"model_generate", "model_repair", "city"}:
            result, freshness = _envelope(event, at)
            ids = _public_sources(result, after, before, at)
            return self._quality_issues(event, result, freshness, ids, errors)
        _require(event.operation in {"route", "fallback", "location"} and len(event.refs) == 1)
        result, freshness = _envelope(event, at)
        _require(
            result.provider is Provider.AMAP
            and result.status is not ProviderResultStatus.UNAVAILABLE
        )
        ids = _public_sources(result, after, before, at)
        _require(bool(ids))
        request, ref = event.request, event.refs[0]
        if event.operation == "location":
            _require(
                type(request) is PoiSearchRequest
                and type(result.data) is PoiSearchResult
                and event.primary is None
                and event.city is None
            )
            assert isinstance(request, PoiSearchRequest) and isinstance(
                result.data, PoiSearchResult
            )
            location = after.locations.get(ref)
            _require(location is not None and request.city_adcode == after.plan.city_adcode)
            assert location is not None
            matches = [p for p in result.data.candidates if p.location_id == ref]
            _require(len(matches) == 1 and location.source_ids == ids)
            previous = before.locations.get(ref)
            _require(
                location.provider.value == "amap"
                and location.provider_place_id == (previous.provider_place_id if previous else None)
            )
            _require(
                _normal(matches[0])
                == _normal(
                    location.model_dump(exclude={"source_ids", "provider", "provider_place_id"})
                )
            )
            source_type = "amap_poi_search"
        else:
            _require(
                type(request) is RouteCalculationRequest
                and type(result.data) is RouteLeg
                and type(event.city) is CityResolution
            )
            assert isinstance(request, RouteCalculationRequest) and isinstance(
                event.city, CityResolution
            )
            _require(
                event.city.adcode == after.plan.city_adcode
                and bool(event.city.citycode)
                and event.city.citycode.isdigit()
                and request.origin_citycode == request.destination_citycode == event.city.citycode
            )
            route = after.routes.get(ref)
            _require(route is not None and after.route_days[ref].local_date == event.local_date)
            assert route is not None
            requirement = RouteRequirement(
                (event.local_date - after.plan.start_date).days,
                route.origin_location_id,
                route.destination_location_id,
            )
            selected = cast(ProviderResult[RouteLeg], result)
            _require(
                _route_result_is_usable(requirement, request, selected)
                and DataFreshness.STALE not in freshness
            )
            _require(
                _normal(result.data) == _normal(route.model_dump(exclude={"route_id", "fare"}))
            )
            for ref_id, coordinates in (
                (request.origin_location_id, request.origin),
                (request.destination_location_id, request.destination),
            ):
                _require(
                    ref_id in after.locations
                    and _normal(after.locations[ref_id].coordinates) == _normal(coordinates)
                )
            _require(
                request.origin_location_id == route.origin_location_id
                and request.destination_location_id == route.destination_location_id
            )
            modes = tuple(m.value for m in job.request.transport_modes)
            _require(request.mode.value in modes)
            source_type = "amap_route_" + request.mode.value
            if event.operation == "fallback":
                _require(
                    "public_transit" in modes
                    and request.mode is RouteMode.WALKING
                    and event.primary is not None
                )
                primary, _ = _envelope(
                    replace(event, result=cast(ProviderResult[object], event.primary)), at
                )
                _require(
                    primary.provider is Provider.AMAP
                    and (primary.data is None or type(primary.data) is RouteLeg)
                )
                primary_route = cast(ProviderResult[RouteLeg], primary)
                primary_request = replace(request, mode=RouteMode.PUBLIC_TRANSIT)
                invalid = primary.data is not None and not _route_result_is_usable(
                    requirement, primary_request, primary_route
                )
                lookup = _RouteLookup(
                    requirement=requirement,
                    request=primary_request,
                    result=primary_route,
                    requirement_index=1,
                    stage=RouteLookupStage.PRIMARY,
                    diagnostic_code=RouteDataDiagnosticCode.RESULT_INVALID if invalid else None,
                )
                _require(_lookup_allows_fallback(lookup))
            else:
                _require(event.primary is None)
        _require(all(s.source_type == source_type for s in result.source_records))
        return self._quality_issues(event, result, freshness, ids, errors)

    def _quality_issues(
        self,
        event: EvidenceEvent,
        result: ProviderResult[object],
        freshness: set[DataFreshness],
        ids: tuple[UUID, ...],
        errors: list[ApiError],
    ) -> list[tuple[str, tuple[UUID, ...]]]:
        errors.extend(_provider_errors((result,)))
        issues: list[tuple[str, tuple[UUID, ...]]] = []
        if event.operation == "fallback":
            issues.append(("route_mode_fallback_used", ()))
        if result.status is ProviderResultStatus.PARTIAL:
            issues.append(("provider_degraded", ids))
        if DataFreshness.UNKNOWN_VALIDITY in freshness:
            issues.append(("source_validity_unknown", ids))
        if DataFreshness.STALE in freshness:
            errors.append(
                ApiError(
                    code=ApiErrorCode.DATA_STALE,
                    message=_PROVIDER_ERROR_MESSAGES[ApiErrorCode.DATA_STALE],
                    provider="amap",
                    diagnostic_code="location_source_stale",
                    retryable=False,
                )
            )
            issues.append(("source_stale", ids))
        return sorted(issues)

    def _guards(
        self,
        before: ReplanFacts,
        after: ReplanFacts,
        command: ReplanCommand,
        allowed: set[UUID],
        *,
        evidenced: bool = False,
    ) -> None:
        _require(type(before.plan) is type(after.plan))
        _require(
            (before.plan.city_adcode, before.plan.start_date, before.plan.end_date)
            == (after.plan.city_adcode, after.plan.start_date, after.plan.end_date)
        )
        _require(before.plan.budget_summary.budget == after.plan.budget_summary.budget)
        names = ("resolved_destination", "violations", "retryable")
        for name in names if evidenced else (*names, "errors", "warnings"):
            _require(getattr(before.result, name) == getattr(after.result, name))
        retained_uncertainties = self._retained_uncertainties(before, after, command)
        _require(
            after.result.uncertainties[: len(retained_uncertainties)] == retained_uncertainties
        )
        for u in after.result.uncertainties[len(retained_uncertainties) :]:
            if not evidenced:
                _require(bool(u.affected_refs) and set(u.affected_refs) <= allowed)
        _require(after.result.status in {PlanningStatus.READY, PlanningStatus.PARTIAL})
        if after.plan.budget_summary.unknown_count or any(
            f is DataFreshness.UNKNOWN_VALIDITY for f in after.freshness.values()
        ):
            _require(after.result.status is PlanningStatus.PARTIAL)
        for sid, freshness in after.freshness.items():
            if freshness is DataFreshness.STALE:
                source = after.sources[sid]
                if source.provider.value not in {"user", "system"}:
                    _require(
                        not any(kind in {"route", "provenance"} for kind, _ in after.consumers[sid])
                    )
                    _require(after.result.status is PlanningStatus.PARTIAL)
        for old, new in zip(before.plan.days, after.plan.days, strict=True):
            _require(
                old.local_date == new.local_date
                and old.accommodation_location_id == new.accommodation_location_id
            )
            if old.weather != new.weather and not evidenced:
                _require(
                    before.day_ids[old.local_date] in allowed
                    and old.weather is not None
                    and new.weather is not None
                )
                assert old.weather is not None and new.weather is not None
                # A refresh may change source/time evidence, not weather facts outside R1 scope.
                _require(
                    old.weather.model_dump(exclude={"source_ids", "alerts"})
                    == new.weather.model_dump(exclude={"source_ids", "alerts"})
                )
                _require(
                    tuple(
                        a.model_dump(exclude={"source_ids", "issued_at"})
                        for a in old.weather.alerts
                    )
                    == tuple(
                        a.model_dump(exclude={"source_ids", "issued_at"})
                        for a in new.weather.alerts
                    )
                )
        for loc in before.locations.keys() | after.locations.keys():
            if before.locations.get(loc) == after.locations.get(loc):
                continue
            _require(
                isinstance(command, ReplaceActivity | DeleteActivity)
                and loc in allowed
                or isinstance(command, ReplaceActivity)
                and loc not in before.locations
                and bool(after.location_users[loc])
                and None not in after.location_users[loc]
            )
        if isinstance(command, AdjustActivityTime):
            activity = after.activities[command.target_activity_id]
            _require(
                (activity.start_time, activity.end_time) == (command.start_time, command.end_time)
            )
            _require(
                before.activities[command.target_activity_id].model_dump(
                    exclude={"start_time", "end_time", "source_ids"}
                )
                == activity.model_dump(exclude={"start_time", "end_time", "source_ids"})
            )
