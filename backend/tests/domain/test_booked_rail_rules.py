"""F-004C pure booked-rail domain rules."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    BookedRailIntercitySegment,
    BookedRailTrip,
    CityStay,
    CostConfidence,
    DomainInvariantError,
    IntercityMode,
    Money,
    build_intercity_cost_item,
    intercity_buffer,
    normalize_service_number,
)

SHANGHAI = timezone(timedelta(hours=8))
HOTEL_A = UUID("a1000000-0000-4000-8000-000000000001")
HOTEL_B = UUID("b1000000-0000-4000-8000-000000000001")
HOTEL_C = UUID("c1000000-0000-4000-8000-000000000001")
SOURCE_ID = UUID("d1000000-0000-4000-8000-000000000001")
COST_ID = UUID("e1000000-0000-4000-8000-000000000001")


def at(day: int, hour: int) -> datetime:
    return datetime(2026, 8, day, hour, tzinfo=SHANGHAI)


def stay(city: str, hotel: UUID) -> CityStay:
    return CityStay(city=city, nights=1, accommodation_location_id=hotel)


def segment(index: int, day: int, service_number: object = " g1234 ") -> BookedRailIntercitySegment:
    return BookedRailIntercitySegment(
        from_city_index=index,
        to_city_index=index + 1,
        service_number=service_number,  # type: ignore[arg-type]
        departure_station=f"城市{index}站",
        arrival_station=f"城市{index + 1}站",
        departure_at=at(day, 10),
        arrival_at=at(day, 12),
        fare=Money(Decimal("120.00")),
    )


def test_booked_rail_segment_normalizes_service_and_derives_duration_and_buffer() -> None:
    value = segment(0, 22)

    assert value.service_number == "G1234"
    assert value.mode is IntercityMode.RAIL
    assert value.duration == timedelta(hours=2)
    assert intercity_buffer(value.mode) == (60, 30)


@pytest.mark.parametrize(
    "value",
    ["", "G 123", "G-123", "车123", "A" * 13, 123, None, True],
)
def test_service_number_rejects_non_string_or_outside_closed_pattern(value: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        normalize_service_number(value)

    assert error.value.code == "intercity_service_number_invalid"


def test_booked_rail_trip_derives_transfer_days_for_two_or_three_cities() -> None:
    two_city = BookedRailTrip(
        start_date=date(2026, 8, 21),
        end_date=date(2026, 8, 23),
        city_stays=(stay("杭州", HOTEL_A), stay("上海", HOTEL_B)),
        intercity_segments=(segment(0, 22),),
    )
    three_city = BookedRailTrip(
        start_date=date(2026, 8, 21),
        end_date=date(2026, 8, 24),
        city_stays=(stay("杭州", HOTEL_A), stay("上海", HOTEL_B), stay("南京", HOTEL_C)),
        intercity_segments=(segment(0, 22), segment(1, 23, "d2281")),
    )

    assert two_city.transfer_dates == (date(2026, 8, 22),)
    assert three_city.transfer_dates == (date(2026, 8, 22), date(2026, 8, 23))
    assert tuple(item.service_number for item in three_city.intercity_segments) == (
        "G1234",
        "D2281",
    )


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"to_city_index": 2}, "intercity_segment_order_invalid"),
        ({"departure_at": at(22, 12), "arrival_at": at(22, 10)}, "intercity_time_invalid"),
        ({"arrival_at": at(23, 12)}, "intercity_time_invalid"),
        (
            {
                "departure_at": datetime(2026, 8, 22, 10, tzinfo=UTC),
                "arrival_at": datetime(2026, 8, 22, 12, tzinfo=UTC),
            },
            "intercity_time_invalid",
        ),
        ({"fare": Money(Decimal("0.00"))}, "intercity_fare_invalid"),
        ({"departure_station": "杭州\n东站"}, "text_invalid"),
    ],
)
def test_booked_rail_segment_fails_closed_on_continuity_time_fare_and_text(
    overrides: dict[str, object], code: str
) -> None:
    values: dict[str, object] = {
        "from_city_index": 0,
        "to_city_index": 1,
        "service_number": "G1234",
        "departure_station": "杭州东站",
        "arrival_station": "上海虹桥站",
        "departure_at": at(22, 10),
        "arrival_at": at(22, 12),
        "fare": Money(Decimal("120.00")),
    }
    values.update(overrides)

    with pytest.raises(DomainInvariantError) as error:
        BookedRailIntercitySegment(**values)  # type: ignore[arg-type]

    assert error.value.code == code


def test_booked_rail_trip_rejects_segment_off_derived_transfer_day() -> None:
    with pytest.raises(DomainInvariantError) as error:
        BookedRailTrip(
            start_date=date(2026, 8, 21),
            end_date=date(2026, 8, 23),
            city_stays=(stay("杭州", HOTEL_A), stay("上海", HOTEL_B)),
            intercity_segments=(segment(0, 21),),
        )

    assert error.value.code == "intercity_time_invalid"


def test_booked_rail_fare_keeps_known_user_value_and_unknown_as_null() -> None:
    known = build_intercity_cost_item(COST_ID, Money(Decimal("120.00")), SOURCE_ID)
    unknown = build_intercity_cost_item(COST_ID, None, SOURCE_ID)

    assert known.confidence is CostConfidence.USER_PROVIDED
    assert known.amount == Money(Decimal("120.00"))
    assert unknown.confidence is CostConfidence.UNKNOWN
    assert unknown.amount is None
