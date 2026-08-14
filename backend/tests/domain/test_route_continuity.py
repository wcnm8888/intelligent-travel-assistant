"""F-001 route-chain completeness and travel-time feasibility rules."""

import json
from datetime import time
from enum import StrEnum
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.contracts import TripPlanRequest, TripPlanResponse
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    DailyRoutePlan,
    DomainInvariantError,
    RouteActivity,
    RouteLeg,
    RouteMode,
    RouteValidationStatus,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
SOURCE_ID = UUID("50000000-0000-4000-8000-000000000001")
HOTEL_ID = UUID("90000000-0000-4000-8000-000000000001")
POI_ONE_ID = UUID("90000000-0000-4000-8000-000000000002")
POI_TWO_ID = UUID("90000000-0000-4000-8000-000000000003")
ACTIVITY_ONE_ID = UUID("91000000-0000-4000-8000-000000000001")
ACTIVITY_TWO_ID = UUID("91000000-0000-4000-8000-000000000002")


def activity(
    activity_id: UUID = ACTIVITY_ONE_ID,
    location_id: UUID = POI_ONE_ID,
    start_time: time = time(10),
    end_time: time = time(12),
) -> RouteActivity:
    return RouteActivity(
        activity_id=activity_id,
        location_id=location_id,
        start_time=start_time,
        end_time=end_time,
    )


def route(
    origin: UUID,
    destination: UUID,
    duration_minutes: int = 30,
    mode: RouteMode = RouteMode.PUBLIC_TRANSIT,
) -> RouteLeg:
    return RouteLeg(
        origin_location_id=origin,
        destination_location_id=destination,
        mode=mode,
        distance_meters=1000,
        duration_minutes=duration_minutes,
        source_ids=(SOURCE_ID,),
    )


def route_plan(
    *,
    activities: tuple[RouteActivity, ...] | None = None,
    routes: tuple[RouteLeg, ...] | None = None,
) -> DailyRoutePlan:
    visits = activities if activities is not None else (activity(),)
    legs = (
        routes
        if routes is not None
        else (
            route(HOTEL_ID, POI_ONE_ID),
            route(POI_ONE_ID, HOTEL_ID),
        )
    )
    return DailyRoutePlan(
        accommodation_location_id=HOTEL_ID,
        availability=DailyAvailability(0, time(9), time(20)),
        activities=visits,
        routes=legs,
    )


def test_complete_round_trip_route_chain_is_verified() -> None:
    result = route_plan().validate()

    assert result.status is RouteValidationStatus.VERIFIED
    assert result.missing_legs == ()


def test_walking_and_public_transit_use_the_same_continuity_rules() -> None:
    result = route_plan(
        routes=(
            route(HOTEL_ID, POI_ONE_ID, mode=RouteMode.WALKING),
            route(POI_ONE_ID, HOTEL_ID, mode=RouteMode.PUBLIC_TRANSIT),
        )
    ).validate()

    assert result.status is RouteValidationStatus.VERIFIED


def test_empty_routes_return_structured_missing_result() -> None:
    result = route_plan(routes=()).validate()

    assert result.status is RouteValidationStatus.MISSING
    assert [
        (item.origin_location_id, item.destination_location_id) for item in result.missing_legs
    ] == [(HOTEL_ID, POI_ONE_ID), (POI_ONE_ID, HOTEL_ID)]


def test_single_missing_middle_leg_is_distinguished_from_a_wrong_route() -> None:
    visits = (
        activity(end_time=time(11)),
        activity(
            ACTIVITY_TWO_ID,
            POI_TWO_ID,
            start_time=time(13),
            end_time=time(15),
        ),
    )
    result = route_plan(
        activities=visits,
        routes=(
            route(HOTEL_ID, POI_ONE_ID),
            route(POI_TWO_ID, HOTEL_ID),
        ),
    ).validate()

    assert result.status is RouteValidationStatus.MISSING
    assert len(result.missing_legs) == 1
    assert result.missing_legs[0].origin_location_id == POI_ONE_ID
    assert result.missing_legs[0].destination_location_id == POI_TWO_ID


@pytest.mark.parametrize(
    ("routes", "expected_code"),
    [
        (
            (
                route(HOTEL_ID, POI_TWO_ID),
                route(POI_ONE_ID, HOTEL_ID),
            ),
            "route_chain_mismatch",
        ),
        (
            (
                route(POI_ONE_ID, HOTEL_ID),
                route(HOTEL_ID, POI_ONE_ID),
            ),
            "route_chain_mismatch",
        ),
        (
            (
                route(HOTEL_ID, POI_ONE_ID),
                route(POI_ONE_ID, HOTEL_ID),
                route(HOTEL_ID, POI_TWO_ID),
            ),
            "route_chain_extra_leg",
        ),
    ],
)
def test_wrong_reversed_or_extra_routes_are_conflicts(
    routes: tuple[RouteLeg, ...], expected_code: str
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        route_plan(routes=routes).validate()

    assert error.value.code == expected_code
    assert error.value.field == "routes"


@pytest.mark.parametrize(
    ("duration_minutes", "expected_valid"),
    [(60, True), (61, False)],
)
def test_route_to_first_activity_may_exactly_fill_but_not_exceed_gap(
    duration_minutes: int, expected_valid: bool
) -> None:
    candidate = route_plan(
        routes=(
            route(HOTEL_ID, POI_ONE_ID, duration_minutes),
            route(POI_ONE_ID, HOTEL_ID),
        )
    )

    if expected_valid:
        assert candidate.validate().status is RouteValidationStatus.VERIFIED
    else:
        with pytest.raises(DomainInvariantError) as error:
            candidate.validate()
        assert error.value.code == "route_duration_exceeds_gap"


def test_between_activity_and_return_gaps_are_both_checked() -> None:
    visits = (
        activity(end_time=time(11)),
        activity(
            ACTIVITY_TWO_ID,
            POI_TWO_ID,
            start_time=time(12),
            end_time=time(19),
        ),
    )

    exact = route_plan(
        activities=visits,
        routes=(
            route(HOTEL_ID, POI_ONE_ID),
            route(POI_ONE_ID, POI_TWO_ID, 60),
            route(POI_TWO_ID, HOTEL_ID, 60),
        ),
    )
    assert exact.validate().status is RouteValidationStatus.VERIFIED

    for index in (1, 2):
        invalid_routes = list(exact.routes)
        leg = invalid_routes[index]
        invalid_routes[index] = route(
            leg.origin_location_id,
            leg.destination_location_id,
            61,
        )
        with pytest.raises(DomainInvariantError) as error:
            route_plan(activities=visits, routes=tuple(invalid_routes)).validate()
        assert error.value.code == "route_duration_exceeds_gap"


def test_different_locations_with_no_positive_travel_gap_are_a_conflict() -> None:
    visits = (
        activity(end_time=time(12)),
        activity(
            ACTIVITY_TWO_ID,
            POI_TWO_ID,
            start_time=time(12),
            end_time=time(14),
        ),
    )

    with pytest.raises(DomainInvariantError) as error:
        route_plan(activities=visits, routes=()).validate()

    assert error.value.code == "route_gap_not_positive"
    assert error.value.field == "activities"


def test_touching_activities_at_the_same_location_need_no_route() -> None:
    visits = (
        activity(end_time=time(12)),
        activity(
            ACTIVITY_TWO_ID,
            POI_ONE_ID,
            start_time=time(12),
            end_time=time(14),
        ),
    )
    result = route_plan(
        activities=visits,
        routes=(route(HOTEL_ID, POI_ONE_ID), route(POI_ONE_ID, HOTEL_ID)),
    ).validate()
    assert result.status is RouteValidationStatus.VERIFIED


def test_activity_visit_order_must_follow_time_order() -> None:
    visits = (
        activity(
            ACTIVITY_TWO_ID,
            POI_TWO_ID,
            start_time=time(13),
            end_time=time(15),
        ),
        activity(end_time=time(11)),
    )

    with pytest.raises(DomainInvariantError) as error:
        route_plan(activities=visits, routes=()).validate()

    assert error.value.code == "activity_visit_order_invalid"
    assert error.value.field == "activities"


def test_no_activities_require_no_routes_and_are_vacuously_verified() -> None:
    result = route_plan(activities=(), routes=()).validate()
    assert result.status is RouteValidationStatus.VERIFIED

    with pytest.raises(DomainInvariantError) as error:
        route_plan(
            activities=(),
            routes=(route(HOTEL_ID, POI_ONE_ID),),
        ).validate()
    assert error.value.code == "route_chain_extra_leg"


def route_mode_from_contract(value: StrEnum) -> RouteMode:
    return RouteMode(value.value)


def test_ready_fixture_routes_verify_and_partial_fixture_routes_remain_missing() -> None:
    request_fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    request = TripPlanRequest.model_validate(request_fixture["request"])
    windows_by_offset = {int(item.day_offset): item for item in request.day_windows}
    ready = TripPlanResponse.model_validate(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
    )
    partial = TripPlanResponse.model_validate(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_partial.json").read_text(encoding="utf-8"))[
            "response"
        ]
    )
    assert ready.plan is not None
    assert partial.plan is not None

    ready_results = []
    for day_offset, day in enumerate(ready.plan.days):
        request_window = windows_by_offset[day_offset]
        ready_results.append(
            DailyRoutePlan(
                accommodation_location_id=day.accommodation_location_id,
                availability=DailyAvailability(
                    request_window.day_offset,
                    request_window.start_time,
                    request_window.end_time,
                ),
                activities=tuple(
                    RouteActivity(
                        item.item_id,
                        item.location_id,
                        item.start_time,
                        item.end_time,
                    )
                    for item in day.activities
                ),
                routes=tuple(
                    RouteLeg(
                        item.origin_location_id,
                        item.destination_location_id,
                        route_mode_from_contract(item.mode),
                        item.distance_meters,
                        item.duration_minutes,
                        item.source_ids,
                    )
                    for item in day.routes
                ),
            ).validate()
        )
    assert all(item.status is RouteValidationStatus.VERIFIED for item in ready_results)

    partial_results = [
        DailyRoutePlan(
            accommodation_location_id=day.accommodation_location_id,
            availability=DailyAvailability(
                windows_by_offset[day_offset].day_offset,
                windows_by_offset[day_offset].start_time,
                windows_by_offset[day_offset].end_time,
            ),
            activities=tuple(
                RouteActivity(
                    item.item_id,
                    item.location_id,
                    item.start_time,
                    item.end_time,
                )
                for item in day.activities
            ),
            routes=(),
        ).validate()
        for day_offset, day in enumerate(partial.plan.days)
    ]
    assert all(item.status is RouteValidationStatus.MISSING for item in partial_results)
