"""Pure deterministic scheduling from proposal, route facts, and frozen rules."""

from dataclasses import replace
from datetime import date, time
from uuid import UUID

import pytest

from intelligent_travel_assistant.application.planning import (
    DurationBasis,
    RouteRequirement,
    ScheduledRoute,
    SchedulingIssueCode,
    SchedulingUncertaintyCode,
    SchedulingWarningCode,
    schedule_plan_proposal,
)
from intelligent_travel_assistant.application.ports import (
    ActivityDurationClass,
    ActivitySelection,
    ActivitySelectionKind,
    PlanningLocation,
    PlanProposal,
    ProposalDay,
)
from intelligent_travel_assistant.domain import DailyAvailability, RouteLeg, RouteMode

HOTEL_ID = UUID("92000000-0000-4000-8000-000000000010")
POI_ONE_ID = UUID("92000000-0000-4000-8000-000000000001")
POI_TWO_ID = UUID("92000000-0000-4000-8000-000000000002")


def test_duration_basis_freezes_the_approved_precedence_vocabulary() -> None:
    assert tuple(DurationBasis) == (
        DurationBasis.USER_PROVIDED,
        DurationBasis.ESTIMATED_MODEL,
        DurationBasis.ESTIMATED_RULE,
        DurationBasis.UNKNOWN,
    )


POI_THREE_ID = UUID("92000000-0000-4000-8000-000000000003")
POI_SOURCE_ID = UUID("42000000-0000-4000-8000-000000000001")
ROUTE_SOURCE_ID = UUID("42000000-0000-4000-8000-000000000002")
START_DATE = date(2026, 8, 16)
WINDOWS = (
    DailyAvailability(0, time(8), time(18)),
    DailyAvailability(1, time(8), time(18)),
)
LOCATIONS = (
    PlanningLocation(POI_ONE_ID, "synthetic scenic", "scenic_area", "330100"),
    PlanningLocation(POI_TWO_ID, "synthetic museum", "museum", "330100"),
    PlanningLocation(POI_THREE_ID, "synthetic other", "other", "330100"),
)


def _selection(
    location_id: UUID,
    day_offset: int,
    priority: int,
    *,
    kind: ActivitySelectionKind = ActivitySelectionKind.REQUIRED,
    duration: ActivityDurationClass = ActivityDurationClass.STANDARD,
) -> ActivitySelection:
    return ActivitySelection(
        location_id=location_id,
        local_date=START_DATE.fromordinal(START_DATE.toordinal() + day_offset),
        title=f"synthetic activity {day_offset}-{priority}",
        priority_rank=priority,
        selection_kind=kind,
        duration_class=duration,
        source_ids=(POI_SOURCE_ID,),
    )


def _proposal(
    day_zero: tuple[ActivitySelection, ...] | None = None,
    day_one: tuple[ActivitySelection, ...] | None = None,
) -> PlanProposal:
    return PlanProposal(
        intent_summary="synthetic proposal",
        days=(
            ProposalDay(START_DATE, day_zero or (_selection(POI_ONE_ID, 0, 1),)),
            ProposalDay(
                START_DATE.fromordinal(START_DATE.toordinal() + 1),
                day_one or (_selection(POI_TWO_ID, 1, 1),),
            ),
        ),
        explanation="synthetic explanation",
        warnings=(),
    )


def _route(requirement: RouteRequirement, minutes: int = 20) -> ScheduledRoute:
    return ScheduledRoute(
        requirement,
        RouteLeg(
            requirement.origin_location_id,
            requirement.destination_location_id,
            RouteMode.WALKING,
            1000,
            minutes,
            (ROUTE_SOURCE_ID,),
        ),
    )


def _with_routes(proposal: PlanProposal, *, minutes: int = 20):  # type: ignore[no-untyped-def]
    first = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    assert first.issue is SchedulingIssueCode.ROUTE_DATA_REQUIRED
    routes = tuple(_route(item, minutes) for item in first.missing_routes)
    return schedule_plan_proposal(
        first.proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=frozenset(first.missing_routes),
    ), routes


def test_normal_two_day_plan_uses_route_duration_and_walking_buffer() -> None:
    result, _ = _with_routes(_proposal())

    assert result.issue is None
    assert result.candidate is not None
    first = result.candidate.days[0].activities[0]
    assert first.start_time == time(8, 30)
    assert first.end_time == time(10, 30)
    assert SchedulingUncertaintyCode.ACTIVITY_DURATION_ESTIMATED_MODEL in result.uncertainties
    assert SchedulingUncertaintyCode.TRAVEL_BUFFER_ESTIMATED in result.uncertainties


@pytest.mark.parametrize(
    ("duration", "expected_end"),
    (
        (ActivityDurationClass.SHORT, time(9, 30)),
        (ActivityDurationClass.STANDARD, time(10, 30)),
        (ActivityDurationClass.LONG, time(11, 30)),
    ),
)
def test_duration_classes_map_to_exact_minutes(
    duration: ActivityDurationClass, expected_end: time
) -> None:
    result, _ = _with_routes(_proposal(day_zero=(_selection(POI_ONE_ID, 0, 1, duration=duration),)))

    assert result.candidate is not None
    activity = result.candidate.days[0].activities[0]
    assert activity.start_time == time(8, 30)
    assert activity.end_time == expected_end


@pytest.mark.parametrize("location_id", (POI_ONE_ID, POI_TWO_ID))
def test_scenic_and_museum_unknown_duration_default_to_120_minutes(location_id: UUID) -> None:
    result, _ = _with_routes(
        _proposal(day_zero=(_selection(location_id, 0, 1, duration=ActivityDurationClass.UNKNOWN),))
    )

    assert result.candidate is not None
    activity = result.candidate.days[0].activities[0]
    assert activity.start_time == time(8, 30)
    assert activity.end_time == time(10, 30)
    assert SchedulingUncertaintyCode.ACTIVITY_DURATION_ESTIMATED_RULE in result.uncertainties


def test_same_inputs_produce_identical_schedule() -> None:
    proposal = _proposal()
    first, routes = _with_routes(proposal)
    second = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=frozenset(item.requirement for item in routes),
    )

    assert first == second


def test_public_transit_adds_fifteen_minutes_per_route() -> None:
    proposal = _proposal()
    missing = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.PUBLIC_TRANSIT,
        routes=(),
        queried_routes=frozenset(),
    )
    routes = tuple(
        ScheduledRoute(
            item,
            RouteLeg(
                item.origin_location_id,
                item.destination_location_id,
                RouteMode.PUBLIC_TRANSIT,
                1000,
                20,
                (ROUTE_SOURCE_ID,),
            ),
        )
        for item in missing.missing_routes
    )

    result = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.PUBLIC_TRANSIT,
        routes=routes,
        queried_routes=frozenset(item.requirement for item in routes),
    )

    assert result.candidate is not None
    assert result.candidate.days[0].activities[0].start_time == time(8, 35)


def test_unknown_duration_uses_category_rule_or_needs_input() -> None:
    rule_proposal = _proposal(
        day_zero=(
            _selection(
                POI_ONE_ID,
                0,
                1,
                duration=ActivityDurationClass.UNKNOWN,
            ),
        )
    )
    rule_result, _ = _with_routes(rule_proposal)
    assert rule_result.candidate is not None
    assert rule_result.candidate.days[0].activities[0].end_time == time(10, 30)
    assert SchedulingUncertaintyCode.ACTIVITY_DURATION_ESTIMATED_RULE in (rule_result.uncertainties)

    unknown = _proposal(
        day_zero=(
            _selection(
                POI_THREE_ID,
                0,
                1,
                duration=ActivityDurationClass.UNKNOWN,
            ),
        )
    )
    unknown_result = schedule_plan_proposal(
        unknown,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    assert unknown_result.issue is SchedulingIssueCode.ACTIVITY_DURATION_UNKNOWN
    assert unknown_result.candidate is None
    assert unknown_result.missing_routes == ()


def test_same_location_consecutive_activities_do_not_request_self_route() -> None:
    proposal = _proposal(
        day_zero=(
            _selection(POI_ONE_ID, 0, 1, duration=ActivityDurationClass.SHORT),
            _selection(POI_ONE_ID, 0, 2, duration=ActivityDurationClass.SHORT),
        )
    )
    missing = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )

    day_zero = tuple(item for item in missing.missing_routes if item.day_offset == 0)
    assert [(item.origin_location_id, item.destination_location_id) for item in day_zero] == [
        (HOTEL_ID, POI_ONE_ID),
        (POI_ONE_ID, HOTEL_ID),
    ]


def test_lowest_priority_optional_is_removed_once_and_requires_bridge_route() -> None:
    proposal = _proposal(
        day_zero=(
            _selection(POI_ONE_ID, 0, 1, duration=ActivityDurationClass.LONG),
            _selection(
                POI_TWO_ID,
                0,
                2,
                kind=ActivitySelectionKind.OPTIONAL,
                duration=ActivityDurationClass.LONG,
            ),
        )
    )
    short_windows = (replace(WINDOWS[0], end_time=time(13)), WINDOWS[1])
    initial = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=short_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    initial_routes = tuple(_route(item) for item in initial.missing_routes)
    adjusted = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=short_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=initial_routes,
        queried_routes=frozenset(initial.missing_routes),
    )

    assert adjusted.issue is SchedulingIssueCode.ROUTE_DATA_REQUIRED
    assert adjusted.omitted_days == frozenset({0})
    assert adjusted.warnings == (SchedulingWarningCode.OPTIONAL_ACTIVITY_OMITTED_FOR_CAPACITY,)
    assert len(adjusted.proposal.days[0].selections) == 1
    assert adjusted.missing_routes == (RouteRequirement(0, POI_ONE_ID, HOTEL_ID),)

    bridge = _route(adjusted.missing_routes[0])
    finished = schedule_plan_proposal(
        adjusted.proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=short_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(*initial_routes, bridge),
        queried_routes=frozenset((*initial.missing_routes, *adjusted.missing_routes)),
        omitted_days=adjusted.omitted_days,
        warnings=adjusted.warnings,
    )
    assert finished.issue is None
    assert finished.candidate is not None
    assert len(finished.candidate.days[0].activities) == 1


def test_required_capacity_overflow_is_conflict_without_removal() -> None:
    proposal = _proposal(
        day_zero=(
            _selection(POI_ONE_ID, 0, 1, duration=ActivityDurationClass.LONG),
            _selection(POI_TWO_ID, 0, 2, duration=ActivityDurationClass.LONG),
        )
    )
    short_windows = (replace(WINDOWS[0], end_time=time(13)), WINDOWS[1])
    missing = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=short_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    routes = tuple(_route(item) for item in missing.missing_routes)

    result = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=short_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=frozenset(missing.missing_routes),
    )

    assert result.issue is SchedulingIssueCode.SCHEDULE_CAPACITY_EXCEEDED
    assert result.candidate is None
    assert result.omitted_days == frozenset()


def test_queried_route_without_usable_data_is_failed_not_zero() -> None:
    proposal = _proposal()
    missing = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )

    result = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=WINDOWS,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(missing.missing_routes),
    )

    assert result.issue is SchedulingIssueCode.ROUTE_DATA_UNAVAILABLE
    assert result.candidate is None


def test_exact_capacity_is_allowed_but_one_minute_less_conflicts() -> None:
    proposal = _proposal(
        day_zero=(_selection(POI_ONE_ID, 0, 1, duration=ActivityDurationClass.LONG),)
    )
    exact_windows = (replace(WINDOWS[0], end_time=time(12)), WINDOWS[1])
    missing = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=exact_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    routes = tuple(_route(item) for item in missing.missing_routes)
    queried = frozenset(missing.missing_routes)

    exact = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=exact_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=queried,
    )
    too_short = schedule_plan_proposal(
        proposal,
        accommodation_location_id=HOTEL_ID,
        day_windows=(replace(WINDOWS[0], end_time=time(11, 59)), WINDOWS[1]),
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=queried,
    )

    assert exact.candidate is not None
    assert too_short.issue is SchedulingIssueCode.SCHEDULE_CAPACITY_EXCEEDED
