"""F-004A deterministic scheduling across every day in a 2-7 day proposal."""

from datetime import date, time, timedelta
from uuid import UUID

import pytest

from intelligent_travel_assistant.application.planning import (
    ScheduledRoute,
    SchedulingIssueCode,
    derive_route_requirements,
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
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    DomainInvariantError,
    RouteLeg,
    RouteMode,
)

START_DATE = date(2026, 8, 14)
HOTEL_ID = UUID("92000000-0000-4000-8000-000000000010")
POI_ONE_ID = UUID("92000000-0000-4000-8000-000000000001")
POI_TWO_ID = UUID("92000000-0000-4000-8000-000000000002")
SOURCE_ID = UUID("42000000-0000-4000-8000-000000000001")
LOCATIONS = (
    PlanningLocation(POI_ONE_ID, "synthetic scenic", "scenic_area", "330100"),
    PlanningLocation(POI_TWO_ID, "synthetic museum", "museum", "330100"),
)


def proposal(day_count: int, *, activities_per_day: int = 1) -> PlanProposal:
    days = []
    for day_offset in range(day_count):
        local_date = START_DATE + timedelta(days=day_offset)
        selections = tuple(
            ActivitySelection(
                POI_ONE_ID if index == 0 else POI_TWO_ID,
                local_date,
                f"synthetic {day_offset}-{index}",
                index + 1,
                ActivitySelectionKind.REQUIRED,
                ActivityDurationClass.SHORT,
                (SOURCE_ID,),
            )
            for index in range(activities_per_day)
        )
        days.append(ProposalDay(local_date, selections))
    return PlanProposal("synthetic", tuple(days), "synthetic", ())


def schedule(value: PlanProposal):  # type: ignore[no-untyped-def]
    day_windows = tuple(
        DailyAvailability(offset, time(8), time(18)) for offset in range(len(value.days))
    )
    first = schedule_plan_proposal(
        value,
        accommodation_location_id=HOTEL_ID,
        day_windows=day_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=(),
        queried_routes=frozenset(),
    )
    assert first.issue is SchedulingIssueCode.ROUTE_DATA_REQUIRED
    routes = tuple(
        ScheduledRoute(
            requirement,
            RouteLeg(
                requirement.origin_location_id,
                requirement.destination_location_id,
                RouteMode.WALKING,
                1000,
                10,
                (SOURCE_ID,),
            ),
        )
        for requirement in first.missing_routes
    )
    return schedule_plan_proposal(
        value,
        accommodation_location_id=HOTEL_ID,
        day_windows=day_windows,
        locations=LOCATIONS,
        route_mode=RouteMode.WALKING,
        routes=routes,
        queried_routes=frozenset(first.missing_routes),
    )


@pytest.mark.parametrize("day_count", [2, 3, 7])
def test_scheduler_visits_every_day_deterministically(day_count: int) -> None:
    value = proposal(day_count)
    first = schedule(value)
    second = schedule(value)

    assert first == second
    assert first.candidate is not None
    assert tuple(day.local_date for day in first.candidate.days) == tuple(
        START_DATE + timedelta(days=offset) for offset in range(day_count)
    )


@pytest.mark.parametrize("day_count", [3, 7])
def test_two_daily_activities_produce_at_most_three_accommodation_route_legs(
    day_count: int,
) -> None:
    requirements = derive_route_requirements(proposal(day_count, activities_per_day=2), HOTEL_ID)

    assert len(requirements) == 3 * day_count
    assert all(0 <= item.day_offset < day_count for item in requirements)


def test_scheduler_rejects_missing_window_and_three_activities_per_day() -> None:
    value = proposal(3)
    with pytest.raises(DomainInvariantError) as error:
        schedule_plan_proposal(
            value,
            accommodation_location_id=HOTEL_ID,
            day_windows=(
                DailyAvailability(0, time(8), time(18)),
                DailyAvailability(2, time(8), time(18)),
            ),
            locations=LOCATIONS,
            route_mode=RouteMode.WALKING,
            routes=(),
            queried_routes=frozenset(),
        )
    assert error.value.code == "day_window_offsets_invalid"

    with pytest.raises(DomainInvariantError) as error:
        derive_route_requirements(proposal(3, activities_per_day=3), HOTEL_ID)
    assert error.value.code == "day_activity_count_invalid"
