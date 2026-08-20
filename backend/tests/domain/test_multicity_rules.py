"""F-004B1 pure multi-city continuity, buffer, budget, and terminal rules."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    CityStay,
    DomainInvariantError,
    IntercityMode,
    Money,
    MultiCityActivitySlot,
    MultiCityDaySchedule,
    MultiCityTerminalStatus,
    MultiCityTrip,
    UserProvidedIntercitySegment,
    build_intercity_cost_item,
    calculate_multicity_lodging_costs,
    classify_multicity_terminal,
    intercity_buffer,
)

HOTEL_A = UUID("a1000000-0000-4000-8000-000000000001")
HOTEL_B = UUID("b1000000-0000-4000-8000-000000000001")
HOTEL_C = UUID("c1000000-0000-4000-8000-000000000001")
SOURCE_ID = UUID("d1000000-0000-4000-8000-000000000001")
COST_ID = UUID("e1000000-0000-4000-8000-000000000001")


def stay(city: str, nights: int, accommodation_id: UUID) -> CityStay:
    return CityStay(city, nights, accommodation_id)


def segment(
    index: int,
    departure_at: str,
    arrival_at: str,
    *,
    mode: IntercityMode = IntercityMode.RAIL,
    fare: Money | None = None,
) -> UserProvidedIntercitySegment:
    return UserProvidedIntercitySegment(
        from_city_index=index,
        to_city_index=index + 1,
        mode=mode,
        departure_station=f"出发站 {index}",
        arrival_station=f"到达站 {index + 1}",
        departure_at=datetime.fromisoformat(departure_at),
        arrival_at=datetime.fromisoformat(arrival_at),
        fare=fare,
    )


def two_city_trip() -> MultiCityTrip:
    return MultiCityTrip(
        start_date=date(2026, 8, 21),
        end_date=date(2026, 8, 23),
        city_stays=(stay("杭州", 1, HOTEL_A), stay("上海", 1, HOTEL_B)),
        intercity_segments=(segment(0, "2026-08-22T10:00:00+08:00", "2026-08-22T12:00:00+08:00"),),
    )


def test_trip_derives_transfer_days_from_nights_for_two_and_three_cities() -> None:
    two = two_city_trip()
    assert two.day_count == 3
    assert two.transfer_dates == (date(2026, 8, 22),)

    three = MultiCityTrip(
        start_date=date(2026, 8, 21),
        end_date=date(2026, 8, 24),
        city_stays=(
            stay("杭州", 1, HOTEL_A),
            stay("上海", 1, HOTEL_B),
            stay("南京", 1, HOTEL_C),
        ),
        intercity_segments=(
            segment(0, "2026-08-22T10:00:00+08:00", "2026-08-22T12:00:00+08:00"),
            segment(1, "2026-08-23T09:00:00+08:00", "2026-08-23T11:00:00+08:00"),
        ),
    )
    assert three.day_count == 4
    assert three.transfer_dates == (date(2026, 8, 22), date(2026, 8, 23))


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"city_stays": (stay("杭州", 1, HOTEL_A),)}, "multicity_city_count_invalid"),
        (
            {"city_stays": (stay("杭州", 1, HOTEL_A), stay("杭州", 1, HOTEL_B))},
            "multicity_city_order_invalid",
        ),
        (
            {"city_stays": (stay("杭州", 2, HOTEL_A), stay("上海", 1, HOTEL_B))},
            "multicity_nights_invalid",
        ),
        ({"intercity_segments": ()}, "intercity_segment_order_invalid"),
    ],
)
def test_trip_rejects_invalid_city_night_and_segment_structure(
    overrides: dict[str, object], code: str
) -> None:
    values: dict[str, object] = {
        "start_date": date(2026, 8, 21),
        "end_date": date(2026, 8, 23),
        "city_stays": (stay("杭州", 1, HOTEL_A), stay("上海", 1, HOTEL_B)),
        "intercity_segments": (
            segment(0, "2026-08-22T10:00:00+08:00", "2026-08-22T12:00:00+08:00"),
        ),
    }
    values.update(overrides)
    with pytest.raises(DomainInvariantError) as error:
        MultiCityTrip(**values)  # type: ignore[arg-type]
    assert error.value.code == code


@pytest.mark.parametrize(
    ("departure_at", "arrival_at"),
    [
        ("2026-08-21T10:00:00+08:00", "2026-08-21T12:00:00+08:00"),
        ("2026-08-22T23:00:00+08:00", "2026-08-23T01:00:00+08:00"),
        ("2026-08-22T12:00:00+08:00", "2026-08-22T10:00:00+08:00"),
        ("2026-08-22T10:00:00+00:00", "2026-08-22T12:00:00+00:00"),
    ],
)
def test_trip_rejects_wrong_transfer_day_overnight_reverse_and_timezone(
    departure_at: str, arrival_at: str
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        MultiCityTrip(
            start_date=date(2026, 8, 21),
            end_date=date(2026, 8, 23),
            city_stays=(stay("杭州", 1, HOTEL_A), stay("上海", 1, HOTEL_B)),
            intercity_segments=(segment(0, departure_at, arrival_at),),
        )
    assert error.value.code == "intercity_time_invalid"


def test_mode_buffers_are_frozen() -> None:
    assert intercity_buffer(IntercityMode.RAIL) == (60, 30)
    assert intercity_buffer(IntercityMode.AIR) == (120, 60)
    assert intercity_buffer(IntercityMode.COACH) == (45, 30)


def test_transfer_day_accepts_zero_or_one_buffered_activity_and_rejects_conflicts() -> None:
    trip_segment = two_city_trip().intercity_segments[0]
    empty = MultiCityDaySchedule(
        local_date=date(2026, 8, 22),
        departure_city_index=0,
        arrival_city_index=1,
        overnight_city_index=1,
        intercity_segment=trip_segment,
        activities=(),
        local_route_city_pairs=((0, 0), (1, 1)),
    )
    assert empty.activities == ()

    after_arrival = MultiCityActivitySlot(1, time(12, 30), time(13, 30))
    accepted = MultiCityDaySchedule(
        local_date=date(2026, 8, 22),
        departure_city_index=0,
        arrival_city_index=1,
        overnight_city_index=1,
        intercity_segment=trip_segment,
        activities=(after_arrival,),
    )
    assert accepted.activities == (after_arrival,)

    for activities in (
        (MultiCityActivitySlot(0, time(8, 30), time(9, 30)),),
        (MultiCityActivitySlot(1, time(12, 15), time(13)),),
        (after_arrival, MultiCityActivitySlot(1, time(14), time(15))),
    ):
        with pytest.raises(DomainInvariantError) as error:
            MultiCityDaySchedule(
                local_date=date(2026, 8, 22),
                departure_city_index=0,
                arrival_city_index=1,
                overnight_city_index=1,
                intercity_segment=trip_segment,
                activities=activities,
            )
        assert error.value.code in {"intercity_buffer_conflict", "day_activity_count_invalid"}


def test_non_transfer_day_requires_one_or_two_same_city_activities_and_local_routes() -> None:
    activity = MultiCityActivitySlot(0, time(9), time(10))
    value = MultiCityDaySchedule(
        local_date=date(2026, 8, 21),
        departure_city_index=0,
        arrival_city_index=0,
        overnight_city_index=0,
        intercity_segment=None,
        activities=(activity,),
        local_route_city_pairs=((0, 0),),
    )
    assert value.overnight_city_index == 0

    with pytest.raises(DomainInvariantError) as error:
        MultiCityDaySchedule(
            local_date=date(2026, 8, 21),
            departure_city_index=0,
            arrival_city_index=0,
            overnight_city_index=0,
            intercity_segment=None,
            activities=(activity,),
            local_route_city_pairs=((0, 1),),
        )
    assert error.value.code == "multicity_route_city_invalid"


def test_multicity_budget_preserves_per_city_unknown_and_user_fare_confidence() -> None:
    lodging = calculate_multicity_lodging_costs(
        (Money(Decimal("300.00")), None),
        (2, 1),
    )
    assert lodging == (Money(Decimal("600.00")), None)

    known = build_intercity_cost_item(
        COST_ID,
        Money(Decimal("120.00")),
        SOURCE_ID,
    )
    assert known.confidence.value == "user_provided"
    assert known.amount == Money(Decimal("120.00"))

    unknown = build_intercity_cost_item(COST_ID, None, SOURCE_ID)
    assert unknown.confidence.value == "unknown"
    assert unknown.amount is None


def test_terminal_classification_keeps_unverified_user_segment_out_of_partial_signal() -> None:
    assert classify_multicity_terminal() is MultiCityTerminalStatus.READY
    assert classify_multicity_terminal(unknown_cost_count=1) is MultiCityTerminalStatus.PARTIAL
    assert classify_multicity_terminal(constraint_conflict=True) is MultiCityTerminalStatus.CONFLICT
    assert classify_multicity_terminal(missing_input=True) is MultiCityTerminalStatus.NEEDS_INPUT
    assert classify_multicity_terminal(execution_failed=True) is MultiCityTerminalStatus.FAILED

    with pytest.raises(DomainInvariantError) as error:
        classify_multicity_terminal(missing_input=True, constraint_conflict=True)
    assert error.value.code == "multicity_terminal_facts_invalid"
