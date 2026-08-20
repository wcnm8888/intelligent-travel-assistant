"""Route enrichment values and deterministic terminal-status arbitration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.application.ports import (
    PlanCandidate,
    PoiSearchResult,
    RouteCalculationRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    ActivityTimeSlot,
    BudgetAssessment,
    BudgetCostItem,
    BudgetSummaryResult,
    Coordinates,
    DailyAvailability,
    DailyRoutePlan,
    DataFreshness,
    DomainInvariantError,
    ExpectedRouteLeg,
    Money,
    MultiDayTimePlan,
    ProviderResult,
    ProviderResultStatus,
    RouteActivity,
    RouteLeg,
    RouteValidationResult,
    RouteValidationStatus,
    SourceCatalog,
    evaluate_freshness,
    summarize_budget,
)

_ADCODE: Final = re.compile(r"^\d{6}$")


class FinalValidationSeverity(StrEnum):
    PARTIAL = "partial"
    CONFLICT = "conflict"


class FinalValidationIssueCode(StrEnum):
    SCHEDULE_CONFLICT = "schedule_conflict"
    ROUTE_INCOMPLETE = "route_incomplete"
    ROUTE_RESULT_INVALID = "route_result_invalid"
    ROUTE_CONFLICT = "route_conflict"
    WEATHER_INCOMPLETE = "weather_incomplete"
    BUDGET_INDETERMINATE = "budget_indeterminate"
    BUDGET_EXCEEDED = "budget_exceeded"
    SOURCE_REFERENCE_INVALID = "source_reference_invalid"
    SOURCE_STALE = "source_stale"
    SOURCE_VALIDITY_UNKNOWN = "source_validity_unknown"
    PROVIDER_DEGRADED = "provider_degraded"
    HARD_CONSTRAINT_UNVERIFIED = "hard_constraint_unverified"


@dataclass(frozen=True, slots=True)
class AccommodationAnchor:
    location_id: UUID
    city_adcode: str
    coordinates: Coordinates | None

    def __post_init__(self) -> None:
        if not isinstance(self.location_id, UUID):
            raise DomainInvariantError("accommodation_location_id_invalid", field="location_id")
        if not isinstance(self.city_adcode, str) or _ADCODE.fullmatch(self.city_adcode) is None:
            raise DomainInvariantError("adcode_invalid", field="city_adcode")
        if self.coordinates is not None and not isinstance(self.coordinates, Coordinates):
            raise DomainInvariantError("coordinates_invalid", field="coordinates")


@dataclass(frozen=True, slots=True)
class RouteEnrichmentResult:
    day_offset: int
    expected: ExpectedRouteLeg
    request: RouteCalculationRequest | None
    result: ProviderResult[RouteLeg] | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.day_offset, int)
            or isinstance(self.day_offset, bool)
            or not 0 <= self.day_offset < 7
        ):
            raise DomainInvariantError("day_offset_invalid", field="day_offset")
        if not isinstance(self.expected, ExpectedRouteLeg):
            raise DomainInvariantError("expected_route_leg_invalid", field="expected")
        if self.request is None and self.result is not None:
            raise DomainInvariantError("route_result_without_request", field="result")
        if self.request is not None and not isinstance(self.request, RouteCalculationRequest):
            raise DomainInvariantError("route_request_invalid", field="request")
        if self.result is not None and not isinstance(self.result, ProviderResult):
            raise DomainInvariantError("route_result_invalid", field="result")


@dataclass(frozen=True, slots=True)
class FinalValidationIssue:
    code: FinalValidationIssueCode
    severity: FinalValidationSeverity
    day_offset: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, FinalValidationIssueCode):
            raise DomainInvariantError("validation_issue_code_invalid", field="code")
        if not isinstance(self.severity, FinalValidationSeverity):
            raise DomainInvariantError("validation_issue_severity_invalid", field="severity")
        if self.day_offset is not None and (
            not isinstance(self.day_offset, int)
            or isinstance(self.day_offset, bool)
            or not 0 <= self.day_offset < 7
        ):
            raise DomainInvariantError("day_offset_invalid", field="day_offset")


@dataclass(frozen=True, slots=True)
class FinalValidationResult:
    status: PlanningStatus
    issues: tuple[FinalValidationIssue, ...]
    budget: BudgetSummaryResult
    route_validations: tuple[RouteValidationResult, ...]

    def __post_init__(self) -> None:
        if self.status not in {
            PlanningStatus.READY,
            PlanningStatus.PARTIAL,
            PlanningStatus.CONFLICT,
        }:
            raise DomainInvariantError("final_status_invalid", field="status")
        if not isinstance(self.issues, tuple) or not all(
            isinstance(item, FinalValidationIssue) for item in self.issues
        ):
            raise DomainInvariantError("validation_issues_invalid", field="issues")
        if not isinstance(self.budget, BudgetSummaryResult):
            raise DomainInvariantError("budget_summary_invalid", field="budget")
        if not isinstance(self.route_validations, tuple) or not all(
            isinstance(item, RouteValidationResult) for item in self.route_validations
        ):
            raise DomainInvariantError("route_validations_invalid", field="route_validations")
        severities = {item.severity for item in self.issues}
        if self.status is PlanningStatus.READY and self.issues:
            raise DomainInvariantError("ready_has_validation_issues", field="issues")
        if self.status is PlanningStatus.PARTIAL and (
            not self.issues or FinalValidationSeverity.CONFLICT in severities
        ):
            raise DomainInvariantError("partial_issue_mismatch", field="issues")
        if (
            self.status is PlanningStatus.CONFLICT
            and FinalValidationSeverity.CONFLICT not in severities
        ):
            raise DomainInvariantError("conflict_issue_missing", field="issues")


def route_activities(candidate: PlanCandidate, day_offset: int) -> tuple[RouteActivity, ...]:
    day = candidate.days[day_offset]
    return tuple(
        RouteActivity(
            _activity_id(day_offset, index, activity.location_id),
            activity.location_id,
            activity.start_time,
            activity.end_time,
        )
        for index, activity in enumerate(day.activities)
    )


def evaluate_final_plan(
    *,
    candidate: PlanCandidate,
    city_adcode: str,
    pois: PoiSearchResult,
    poi_source_ids: tuple[UUID, ...],
    accommodation: AccommodationAnchor,
    day_windows: tuple[DailyAvailability, ...],
    budget: Money,
    cost_items: tuple[BudgetCostItem, ...],
    route_enrichments: tuple[RouteEnrichmentResult, ...],
    weather_result: ProviderResult[WeatherForecastResult] | None,
    expected_weather_location_id: UUID,
    provider_results: tuple[ProviderResult[object], ...],
    evaluated_at: datetime,
    hard_constraints: tuple[str, ...],
) -> FinalValidationResult:
    issues: list[FinalValidationIssue] = []
    budget_result = summarize_budget(budget, cost_items)
    _validate_budget(budget_result, issues)
    _validate_schedule(candidate, day_windows, issues)
    route_validations = _validate_routes(
        candidate,
        accommodation,
        day_windows,
        route_enrichments,
        issues,
    )
    _validate_locations(
        candidate,
        city_adcode,
        pois,
        poi_source_ids,
        accommodation,
        issues,
    )
    _validate_weather(candidate, weather_result, expected_weather_location_id, issues)
    _validate_sources(candidate, route_enrichments, provider_results, evaluated_at, issues)
    if hard_constraints:
        _add_issue(
            issues,
            FinalValidationIssueCode.HARD_CONSTRAINT_UNVERIFIED,
            FinalValidationSeverity.PARTIAL,
        )
    if any(result.status is not ProviderResultStatus.OK for result in provider_results):
        _add_issue(
            issues,
            FinalValidationIssueCode.PROVIDER_DEGRADED,
            FinalValidationSeverity.PARTIAL,
        )

    status = _terminal_status(issues)
    return FinalValidationResult(status, tuple(issues), budget_result, route_validations)


def _validate_budget(
    result: BudgetSummaryResult,
    issues: list[FinalValidationIssue],
) -> None:
    if result.assessment is BudgetAssessment.OVER_BUDGET:
        _add_issue(
            issues,
            FinalValidationIssueCode.BUDGET_EXCEEDED,
            FinalValidationSeverity.CONFLICT,
        )
    elif result.assessment is BudgetAssessment.INDETERMINATE:
        _add_issue(
            issues,
            FinalValidationIssueCode.BUDGET_INDETERMINATE,
            FinalValidationSeverity.PARTIAL,
        )


def _validate_schedule(
    candidate: PlanCandidate,
    day_windows: tuple[DailyAvailability, ...],
    issues: list[FinalValidationIssue],
) -> None:
    activities = tuple(
        ActivityTimeSlot(
            _activity_id(day_offset, index, activity.location_id),
            activity.local_date,
            activity.start_time,
            activity.end_time,
        )
        for day_offset, day in enumerate(candidate.days)
        for index, activity in enumerate(day.activities)
    )
    try:
        MultiDayTimePlan(
            candidate.days[0].local_date,
            candidate.days[-1].local_date,
            day_windows,
            activities,
        )
    except (DomainInvariantError, IndexError):
        _add_issue(
            issues,
            FinalValidationIssueCode.SCHEDULE_CONFLICT,
            FinalValidationSeverity.CONFLICT,
        )


def _validate_routes(
    candidate: PlanCandidate,
    accommodation: AccommodationAnchor,
    day_windows: tuple[DailyAvailability, ...],
    enrichments: tuple[RouteEnrichmentResult, ...],
    issues: list[FinalValidationIssue],
) -> tuple[RouteValidationResult, ...]:
    windows = {item.day_offset: item for item in day_windows}
    validations: list[RouteValidationResult] = []
    for day_offset in range(len(candidate.days)):
        accepted: list[RouteLeg] = []
        day_enrichments = tuple(item for item in enrichments if item.day_offset == day_offset)
        for item in day_enrichments:
            if item.request is None or item.result is None:
                _add_issue(
                    issues,
                    FinalValidationIssueCode.ROUTE_INCOMPLETE,
                    FinalValidationSeverity.PARTIAL,
                    day_offset,
                )
                continue
            if item.result.status is ProviderResultStatus.UNAVAILABLE or item.result.data is None:
                _add_issue(
                    issues,
                    FinalValidationIssueCode.ROUTE_INCOMPLETE,
                    FinalValidationSeverity.PARTIAL,
                    day_offset,
                )
                continue
            route = item.result.data
            source_ids = {record.source_id for record in item.result.source_records}
            if (
                route.origin_location_id != item.expected.origin_location_id
                or route.destination_location_id != item.expected.destination_location_id
                or route.mode is not item.request.mode
                or any(source_id not in source_ids for source_id in route.source_ids)
            ):
                _add_issue(
                    issues,
                    FinalValidationIssueCode.ROUTE_RESULT_INVALID,
                    FinalValidationSeverity.PARTIAL,
                    day_offset,
                )
                continue
            accepted.append(route)
        try:
            validation = DailyRoutePlan(
                accommodation.location_id,
                windows[day_offset],
                route_activities(candidate, day_offset),
                tuple(accepted),
            ).validate()
        except (DomainInvariantError, KeyError):
            _add_issue(
                issues,
                FinalValidationIssueCode.ROUTE_CONFLICT,
                FinalValidationSeverity.CONFLICT,
                day_offset,
            )
            continue
        validations.append(validation)
        if validation.status is RouteValidationStatus.MISSING:
            _add_issue(
                issues,
                FinalValidationIssueCode.ROUTE_INCOMPLETE,
                FinalValidationSeverity.PARTIAL,
                day_offset,
            )
    return tuple(validations)


def _validate_locations(
    candidate: PlanCandidate,
    city_adcode: str,
    pois: PoiSearchResult,
    poi_source_ids: tuple[UUID, ...],
    accommodation: AccommodationAnchor,
    issues: list[FinalValidationIssue],
) -> None:
    selected = {activity.location_id for day in candidate.days for activity in day.activities}
    by_id = {item.location_id: item for item in pois.candidates}
    allowed_poi_sources = set(poi_source_ids)
    if (
        accommodation.city_adcode != city_adcode
        or any(
            location_id not in by_id or by_id[location_id].city_adcode != city_adcode
            for location_id in selected
        )
        or any(
            not set(activity.source_ids).issubset(allowed_poi_sources)
            for day in candidate.days
            for activity in day.activities
        )
    ):
        _add_issue(
            issues,
            FinalValidationIssueCode.SOURCE_REFERENCE_INVALID,
            FinalValidationSeverity.CONFLICT,
        )


def _validate_weather(
    candidate: PlanCandidate,
    result: ProviderResult[WeatherForecastResult] | None,
    expected_location_id: UUID,
    issues: list[FinalValidationIssue],
) -> None:
    expected_dates = {day.local_date for day in candidate.days}
    if (
        result is None
        or result.status is ProviderResultStatus.UNAVAILABLE
        or result.data is None
        or result.data.location_id != expected_location_id
        or {item.forecast_date for item in result.data.days} != expected_dates
    ):
        _add_issue(
            issues,
            FinalValidationIssueCode.WEATHER_INCOMPLETE,
            FinalValidationSeverity.PARTIAL,
        )


def _validate_sources(
    candidate: PlanCandidate,
    route_enrichments: tuple[RouteEnrichmentResult, ...],
    results: tuple[ProviderResult[object], ...],
    evaluated_at: datetime,
    issues: list[FinalValidationIssue],
) -> None:
    records = tuple(record for result in results for record in result.source_records)
    records_by_id = {record.source_id: record for record in records}
    if any(records_by_id[record.source_id] != record for record in records):
        _add_issue(
            issues,
            FinalValidationIssueCode.SOURCE_REFERENCE_INVALID,
            FinalValidationSeverity.CONFLICT,
        )
    catalog = SourceCatalog(tuple(records_by_id.values()))
    referenced = tuple(
        source_id
        for day in candidate.days
        for activity in day.activities
        for source_id in activity.source_ids
    ) + tuple(
        source_id
        for enrichment in route_enrichments
        if enrichment.result is not None and enrichment.result.data is not None
        for source_id in enrichment.result.data.source_ids
    )
    try:
        catalog.require_all(referenced)
    except DomainInvariantError:
        _add_issue(
            issues,
            FinalValidationIssueCode.SOURCE_REFERENCE_INVALID,
            FinalValidationSeverity.CONFLICT,
        )
    for record in catalog.records:
        try:
            freshness = evaluate_freshness(record.fetched_at, record.valid_until, evaluated_at)
        except DomainInvariantError:
            _add_issue(
                issues,
                FinalValidationIssueCode.SOURCE_REFERENCE_INVALID,
                FinalValidationSeverity.CONFLICT,
            )
            continue
        if freshness is DataFreshness.STALE:
            _add_issue(
                issues,
                FinalValidationIssueCode.SOURCE_STALE,
                FinalValidationSeverity.PARTIAL,
            )
        elif freshness is DataFreshness.UNKNOWN_VALIDITY:
            _add_issue(
                issues,
                FinalValidationIssueCode.SOURCE_VALIDITY_UNKNOWN,
                FinalValidationSeverity.PARTIAL,
            )


def _terminal_status(issues: list[FinalValidationIssue]) -> PlanningStatus:
    if any(item.severity is FinalValidationSeverity.CONFLICT for item in issues):
        return PlanningStatus.CONFLICT
    if issues:
        return PlanningStatus.PARTIAL
    return PlanningStatus.READY


def _add_issue(
    issues: list[FinalValidationIssue],
    code: FinalValidationIssueCode,
    severity: FinalValidationSeverity,
    day_offset: int | None = None,
) -> None:
    issue = FinalValidationIssue(code, severity, day_offset)
    if issue not in issues:
        issues.append(issue)


def _activity_id(day_offset: int, index: int, location_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"f-001:{day_offset}:{index}:{location_id}")
