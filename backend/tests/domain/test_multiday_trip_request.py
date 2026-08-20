"""F-004A variable 2-7 day request rules without legacy contract drift."""

from datetime import date, datetime

import pytest

from intelligent_travel_assistant.domain import (
    DomainInvariantError,
    MultiDayTripRequestInput,
    TripRequestInput,
)

FIXED_NOW = datetime.fromisoformat("2026-08-13T10:00:00+08:00")


def request(**overrides: object) -> MultiDayTripRequestInput:
    values: dict[str, object] = {
        "city": "杭州",
        "start_date": date(2026, 8, 14),
        "end_date": date(2026, 8, 16),
        "travelers": 2,
        "interests": ("自然",),
        "free_text": "节奏舒缓",
        "evaluated_at": FIXED_NOW,
    }
    values.update(overrides)
    return MultiDayTripRequestInput(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("start_date", "end_date", "expected_days"),
    [
        (date(2026, 8, 14), date(2026, 8, 15), 2),
        (date(2026, 8, 14), date(2026, 8, 16), 3),
        (date(2026, 8, 18), date(2026, 8, 24), 7),
    ],
)
def test_multiday_request_accepts_two_three_and_seven_days(
    start_date: date, end_date: date, expected_days: int
) -> None:
    value = request(start_date=start_date, end_date=end_date)

    assert value.day_count == expected_days
    assert value.start_date == start_date
    assert value.end_date == end_date


@pytest.mark.parametrize(
    ("start_date", "end_date", "expected_code"),
    [
        (date(2026, 8, 14), date(2026, 8, 14), "trip_date_order_invalid"),
        (date(2026, 8, 15), date(2026, 8, 14), "trip_date_order_invalid"),
        (date(2026, 8, 14), date(2026, 8, 21), "trip_day_count_invalid"),
    ],
)
def test_multiday_request_rejects_one_eight_and_reverse_spans(
    start_date: date, end_date: date, expected_code: str
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        request(start_date=start_date, end_date=end_date)

    assert error.value.code == expected_code
    assert error.value.field == "end_date"


def test_multiday_request_keeps_start_window_and_strict_date_types() -> None:
    with pytest.raises(DomainInvariantError) as error:
        request(start_date=date(2026, 8, 19), end_date=date(2026, 8, 21))
    assert error.value.code == "trip_start_date_out_of_window"

    with pytest.raises(DomainInvariantError) as error:
        request(end_date=datetime.fromisoformat("2026-08-16T00:00:00+08:00"))
    assert error.value.code == "trip_date_type_invalid"
    assert error.value.field == "end_date"


def test_legacy_request_still_rejects_more_than_two_days() -> None:
    with pytest.raises(DomainInvariantError) as error:
        TripRequestInput(
            city="杭州",
            start_date=date(2026, 8, 14),
            end_date=date(2026, 8, 16),
            travelers=2,
            interests=("自然",),
            free_text="",
            evaluated_at=FIXED_NOW,
        )

    assert error.value.code == "trip_dates_not_consecutive"
