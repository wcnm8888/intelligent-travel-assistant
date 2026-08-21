"""Pure proposal-to-candidate scheduling from verified route duration facts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.application.ports import (
    ActivityDurationClass,
    ActivitySelectionKind,
    CandidateActivity,
    CandidateDay,
    PlanCandidate,
    PlanningLocation,
    PlanProposal,
    ProposalDay,
)
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    DomainInvariantError,
    RouteLeg,
    RouteMode,
)

_DURATION_MINUTES: Final = MappingProxyType(
    {
        ActivityDurationClass.SHORT: 60,
        ActivityDurationClass.STANDARD: 120,
        ActivityDurationClass.LONG: 180,
    }
)
_CATEGORY_DEFAULT_MINUTES: Final = MappingProxyType(
    {
        "scenic_area": 120,
        "museum": 120,
    }
)
_ROUTE_BUFFER_MINUTES: Final = MappingProxyType(
    {
        RouteMode.WALKING: 10,
        RouteMode.PUBLIC_TRANSIT: 15,
    }
)


class SchedulingIssueCode(StrEnum):
    ROUTE_DATA_REQUIRED = "route_data_required"
    ROUTE_DATA_UNAVAILABLE = "route_data_unavailable"
    ACTIVITY_DURATION_UNKNOWN = "activity_duration_unknown"
    SCHEDULE_CAPACITY_EXCEEDED = "schedule_capacity_exceeded"


class RouteDataDiagnosticCode(StrEnum):
    """Safe, value-free reasons why a required route chain could not be formed."""

    PRIMARY_UNAVAILABLE = "route_primary_unavailable"
    FALLBACK_EXHAUSTED = "route_fallback_exhausted"
    COORDINATES_MISSING = "route_coordinates_missing"
    RESULT_INVALID = "route_result_invalid"
    SOURCE_STALE = "route_source_stale"
    CALL_BUDGET_EXHAUSTED = "route_call_budget_exhausted"
    DEADLINE_EXHAUSTED = "route_deadline_exhausted"


class DurationBasis(StrEnum):
    USER_PROVIDED = "user_provided"
    ESTIMATED_MODEL = "estimated_model"
    ESTIMATED_RULE = "estimated_rule"
    UNKNOWN = "unknown"


class SchedulingWarningCode(StrEnum):
    OPTIONAL_ACTIVITY_OMITTED_FOR_CAPACITY = "optional_activity_omitted_for_capacity"
    ROUTE_MODE_FALLBACK_USED = "route_mode_fallback_used"


class SchedulingUncertaintyCode(StrEnum):
    ACTIVITY_DURATION_ESTIMATED_MODEL = "activity_duration_estimated_model"
    ACTIVITY_DURATION_ESTIMATED_RULE = "activity_duration_estimated_rule"
    TRAVEL_BUFFER_ESTIMATED = "travel_buffer_estimated"


@dataclass(frozen=True, slots=True)
class RouteRequirement:
    day_offset: int
    origin_location_id: UUID
    destination_location_id: UUID


@dataclass(frozen=True, slots=True)
class ScheduledRoute:
    requirement: RouteRequirement
    route: RouteLeg


@dataclass(frozen=True, slots=True)
class SchedulingResult:
    proposal: PlanProposal
    candidate: PlanCandidate | None
    issue: SchedulingIssueCode | None
    missing_routes: tuple[RouteRequirement, ...] = ()
    omitted_days: frozenset[int] = frozenset()
    warnings: tuple[SchedulingWarningCode, ...] = ()
    uncertainties: tuple[SchedulingUncertaintyCode, ...] = ()


@dataclass(frozen=True, slots=True)
class _ResolvedDuration:
    minutes: int | None
    basis: DurationBasis


def derive_route_requirements(
    proposal: PlanProposal,
    accommodation_location_id: UUID,
) -> tuple[RouteRequirement, ...]:
    """Derive the exact endpoint chain without inventing route duration or order."""

    _require_multiday_proposal(proposal)
    requirements: list[RouteRequirement] = []
    for day_offset, day in enumerate(proposal.days):
        previous = accommodation_location_id
        for selection in day.selections:
            if previous != selection.location_id:
                requirements.append(RouteRequirement(day_offset, previous, selection.location_id))
            previous = selection.location_id
        if previous != accommodation_location_id:
            requirements.append(RouteRequirement(day_offset, previous, accommodation_location_id))
    return tuple(requirements)


def schedule_plan_proposal(
    proposal: PlanProposal,
    *,
    accommodation_location_id: UUID,
    day_windows: tuple[DailyAvailability, ...],
    locations: tuple[PlanningLocation, ...],
    route_mode: RouteMode,
    routes: tuple[ScheduledRoute, ...],
    queried_routes: frozenset[RouteRequirement],
    fallback_route_modes: tuple[RouteMode, ...] = (),
    omitted_days: frozenset[int] = frozenset(),
    warnings: tuple[SchedulingWarningCode, ...] = (),
) -> SchedulingResult:
    """Create exact local times or return one stable deterministic decision."""

    _require_multiday_proposal(proposal)
    _require_day_windows(day_windows, len(proposal.days))
    location_categories = {item.location_id: item.category for item in locations}
    resolved = _resolve_durations(proposal, location_categories)
    if resolved is None:
        return SchedulingResult(
            proposal,
            None,
            SchedulingIssueCode.ACTIVITY_DURATION_UNKNOWN,
            omitted_days=omitted_days,
            warnings=warnings,
        )
    durations, duration_uncertainties = resolved

    requirements = derive_route_requirements(proposal, accommodation_location_id)
    route_modes = (route_mode, *fallback_route_modes)
    route_by_requirement = _preferred_routes(routes, route_modes)
    unavailable = tuple(
        item for item in requirements if item in queried_routes and item not in route_by_requirement
    )
    if unavailable:
        return SchedulingResult(
            proposal,
            None,
            SchedulingIssueCode.ROUTE_DATA_UNAVAILABLE,
            omitted_days=omitted_days,
            warnings=warnings,
            uncertainties=duration_uncertainties,
        )
    missing = tuple(
        item
        for item in requirements
        if item not in queried_routes and item not in route_by_requirement
    )
    if missing:
        return SchedulingResult(
            proposal,
            None,
            SchedulingIssueCode.ROUTE_DATA_REQUIRED,
            missing,
            omitted_days,
            warnings,
            duration_uncertainties,
        )

    windows = {item.day_offset: item for item in day_windows}
    candidate_days: list[CandidateDay] = []
    for day_offset, day in enumerate(proposal.days):
        scheduled = _schedule_day(
            day_offset,
            day,
            windows[day_offset],
            accommodation_location_id,
            route_by_requirement,
            durations,
        )
        if scheduled is None:
            adjusted = _omit_lowest_priority_optional(day)
            if adjusted is None or day_offset in omitted_days:
                return SchedulingResult(
                    proposal,
                    None,
                    SchedulingIssueCode.SCHEDULE_CAPACITY_EXCEEDED,
                    omitted_days=omitted_days,
                    warnings=warnings,
                    uncertainties=_with_buffer_uncertainty(
                        duration_uncertainties,
                        requirements,
                    ),
                )
            adjusted_days = list(proposal.days)
            adjusted_days[day_offset] = adjusted
            return schedule_plan_proposal(
                replace(proposal, days=tuple(adjusted_days)),
                accommodation_location_id=accommodation_location_id,
                day_windows=day_windows,
                locations=locations,
                route_mode=route_mode,
                fallback_route_modes=fallback_route_modes,
                routes=routes,
                queried_routes=queried_routes,
                omitted_days=omitted_days | {day_offset},
                warnings=_append_unique(
                    warnings,
                    SchedulingWarningCode.OPTIONAL_ACTIVITY_OMITTED_FOR_CAPACITY,
                ),
            )
        candidate_days.append(scheduled)

    candidate = PlanCandidate(
        proposal.intent_summary,
        tuple(candidate_days),
        proposal.explanation,
        proposal.warnings,
    )
    return SchedulingResult(
        proposal,
        candidate,
        None,
        omitted_days=omitted_days,
        warnings=warnings,
        uncertainties=_with_buffer_uncertainty(duration_uncertainties, requirements),
    )


def _require_multiday_proposal(proposal: PlanProposal) -> None:
    if not isinstance(proposal, PlanProposal) or not isinstance(proposal.days, tuple):
        raise DomainInvariantError("plan_proposal_invalid", field="proposal")
    day_count = len(proposal.days)
    if not 2 <= day_count <= 7:
        raise DomainInvariantError("trip_day_count_invalid", field="days")
    start_date = proposal.days[0].local_date
    if not isinstance(start_date, date) or isinstance(start_date, datetime):
        raise DomainInvariantError("local_date_invalid", field="days")
    for day_offset, day in enumerate(proposal.days):
        expected_date = start_date + timedelta(days=day_offset)
        if day.local_date != expected_date:
            raise DomainInvariantError("proposal_day_dates_invalid", field="days")
        if not isinstance(day.selections, tuple) or not 1 <= len(day.selections) <= 2:
            raise DomainInvariantError("day_activity_count_invalid", field="selections")
        expected_priorities = tuple(range(1, len(day.selections) + 1))
        if tuple(item.priority_rank for item in day.selections) != expected_priorities:
            raise DomainInvariantError("activity_priorities_invalid", field="selections")
        if any(item.local_date != day.local_date for item in day.selections):
            raise DomainInvariantError("selection_date_mismatch", field="selections")


def _require_day_windows(
    day_windows: tuple[DailyAvailability, ...],
    day_count: int,
) -> None:
    if not isinstance(day_windows, tuple) or not all(
        isinstance(item, DailyAvailability) for item in day_windows
    ):
        raise DomainInvariantError("day_windows_invalid", field="day_windows")
    by_offset = {item.day_offset: item for item in day_windows}
    if len(day_windows) != day_count or set(by_offset) != set(range(day_count)):
        raise DomainInvariantError("day_window_offsets_invalid", field="day_windows")


def _resolve_durations(
    proposal: PlanProposal,
    categories: dict[UUID, str],
) -> tuple[dict[tuple[int, int], _ResolvedDuration], tuple[SchedulingUncertaintyCode, ...]] | None:
    values: dict[tuple[int, int], _ResolvedDuration] = {}
    uncertainties: tuple[SchedulingUncertaintyCode, ...] = ()
    for day_offset, day in enumerate(proposal.days):
        for index, selection in enumerate(day.selections):
            if selection.duration_class is not ActivityDurationClass.UNKNOWN:
                values[(day_offset, index)] = _ResolvedDuration(
                    _DURATION_MINUTES[selection.duration_class],
                    DurationBasis.ESTIMATED_MODEL,
                )
                uncertainties = _append_unique(
                    uncertainties,
                    SchedulingUncertaintyCode.ACTIVITY_DURATION_ESTIMATED_MODEL,
                )
                continue
            default = _CATEGORY_DEFAULT_MINUTES.get(categories.get(selection.location_id, ""))
            if default is None:
                return None
            values[(day_offset, index)] = _ResolvedDuration(
                default,
                DurationBasis.ESTIMATED_RULE,
            )
            uncertainties = _append_unique(
                uncertainties,
                SchedulingUncertaintyCode.ACTIVITY_DURATION_ESTIMATED_RULE,
            )
    return values, uncertainties


def _schedule_day(
    day_offset: int,
    day: ProposalDay,
    window: DailyAvailability,
    accommodation_location_id: UUID,
    routes: dict[RouteRequirement, RouteLeg],
    durations: dict[tuple[int, int], _ResolvedDuration],
) -> CandidateDay | None:
    cursor = datetime.combine(day.local_date, window.start_time)
    window_end = datetime.combine(day.local_date, window.end_time)
    previous = accommodation_location_id
    activities: list[CandidateActivity] = []
    for index, selection in enumerate(day.selections):
        cursor = _after_route(
            cursor,
            day_offset,
            previous,
            selection.location_id,
            routes,
        )
        duration = durations[(day_offset, index)]
        if duration.minutes is None:
            raise AssertionError("resolved duration must contain minutes")
        end = cursor + timedelta(minutes=duration.minutes)
        activities.append(
            CandidateActivity(
                selection.location_id,
                selection.local_date,
                selection.title,
                cursor.time(),
                end.time(),
                selection.source_ids,
            )
        )
        cursor = end
        previous = selection.location_id
    cursor = _after_route(
        cursor,
        day_offset,
        previous,
        accommodation_location_id,
        routes,
    )
    if cursor > window_end:
        return None
    return CandidateDay(day.local_date, tuple(activities))


def _after_route(
    cursor: datetime,
    day_offset: int,
    origin: UUID,
    destination: UUID,
    routes: dict[RouteRequirement, RouteLeg],
) -> datetime:
    if origin == destination:
        return cursor
    route = routes[RouteRequirement(day_offset, origin, destination)]
    return cursor + timedelta(minutes=route.duration_minutes + _ROUTE_BUFFER_MINUTES[route.mode])


def _preferred_routes(
    routes: tuple[ScheduledRoute, ...],
    route_modes: tuple[RouteMode, ...],
) -> dict[RouteRequirement, RouteLeg]:
    preference = {mode: index for index, mode in enumerate(route_modes)}
    selected: dict[RouteRequirement, RouteLeg] = {}
    for item in routes:
        route = item.route
        if (
            route.mode not in preference
            or route.origin_location_id != item.requirement.origin_location_id
            or route.destination_location_id != item.requirement.destination_location_id
        ):
            continue
        current = selected.get(item.requirement)
        if current is None or preference[route.mode] < preference[current.mode]:
            selected[item.requirement] = route
    return selected


def _omit_lowest_priority_optional(day: ProposalDay) -> ProposalDay | None:
    if len(day.selections) <= 1:
        return None
    eligible = tuple(
        (selection.priority_rank, index)
        for index, selection in enumerate(day.selections)
        if selection.selection_kind is ActivitySelectionKind.OPTIONAL
    )
    if not eligible:
        return None
    _, remove_index = max(eligible)
    return replace(
        day,
        selections=tuple(
            selection for index, selection in enumerate(day.selections) if index != remove_index
        ),
    )


def _with_buffer_uncertainty(
    values: tuple[SchedulingUncertaintyCode, ...],
    requirements: tuple[RouteRequirement, ...],
) -> tuple[SchedulingUncertaintyCode, ...]:
    if not requirements:
        return values
    return _append_unique(values, SchedulingUncertaintyCode.TRAVEL_BUFFER_ESTIMATED)


def _append_unique[T](values: tuple[T, ...], item: T) -> tuple[T, ...]:
    return values if item in values else (*values, item)
