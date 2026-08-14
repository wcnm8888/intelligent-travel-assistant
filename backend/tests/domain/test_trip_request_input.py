"""Deterministic F-001 date and primitive input constraints."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from intelligent_travel_assistant.contracts import TripPlanRequest
from intelligent_travel_assistant.domain import DomainInvariantError, TripRequestInput

FIXED_NOW = datetime.fromisoformat("2026-08-13T10:00:00+08:00")
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def valid_input(**overrides: object) -> TripRequestInput:
    values: dict[str, object] = {
        "city": "杭州",
        "start_date": date(2026, 8, 15),
        "end_date": date(2026, 8, 16),
        "travelers": 2,
        "interests": ("自然", "历史"),
        "free_text": "节奏不要太赶",
        "evaluated_at": FIXED_NOW,
    }
    values.update(overrides)
    return TripRequestInput(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("start_date", "end_date", "travelers"),
    [
        (date(2026, 8, 14), date(2026, 8, 15), 1),
        (date(2026, 8, 18), date(2026, 8, 19), 8),
    ],
)
def test_inclusive_date_and_traveler_boundaries_are_valid(
    start_date: date, end_date: date, travelers: int
) -> None:
    request = valid_input(
        start_date=start_date,
        end_date=end_date,
        travelers=travelers,
        interests=("一", "二", "三", "四", "五"),
        free_text="旅" * 200,
    )

    assert request.start_date == start_date
    assert request.end_date == end_date
    assert request.travelers == travelers
    assert len(request.interests) == 5
    assert len(request.free_text) == 200


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (date(2026, 8, 13), date(2026, 8, 14)),
        (date(2026, 8, 19), date(2026, 8, 20)),
    ],
)
def test_start_date_outside_d_plus_1_to_d_plus_5_is_rejected(
    start_date: date, end_date: date
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(start_date=start_date, end_date=end_date)

    assert error.value.code == "trip_start_date_out_of_window"
    assert error.value.field == "start_date"


def test_shanghai_date_is_used_even_when_clock_is_supplied_in_utc() -> None:
    # 16:30 UTC is already the next calendar day in Shanghai.
    utc_now = datetime(2026, 8, 13, 16, 30, tzinfo=UTC)

    with pytest.raises(DomainInvariantError):
        valid_input(
            start_date=date(2026, 8, 14),
            end_date=date(2026, 8, 15),
            evaluated_at=utc_now,
        )

    request = valid_input(
        start_date=date(2026, 8, 15),
        end_date=date(2026, 8, 16),
        evaluated_at=utc_now,
    )
    assert request.evaluated_at.isoformat() == "2026-08-14T00:30:00+08:00"


def test_evaluation_clock_must_be_timezone_aware() -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(evaluated_at=datetime(2026, 8, 13, 10, 0))

    assert error.value.code == "timezone_required"
    assert error.value.field == "evaluated_at"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_date", "2026-08-15"),
        ("start_date", datetime.fromisoformat("2026-08-15T00:00:00+08:00")),
        ("end_date", "2026-08-16"),
        ("end_date", datetime.fromisoformat("2026-08-16T00:00:00+08:00")),
    ],
)
def test_domain_dates_require_date_values_without_implicit_coercion(
    field: str, value: object
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(**{field: value})

    assert error.value.code == "trip_date_type_invalid"
    assert error.value.field == field


@pytest.mark.parametrize(
    ("start_date", "end_date", "expected_code"),
    [
        (date(2026, 8, 15), date(2026, 8, 15), "trip_date_order_invalid"),
        (date(2026, 8, 16), date(2026, 8, 15), "trip_date_order_invalid"),
        (date(2026, 8, 15), date(2026, 8, 17), "trip_dates_not_consecutive"),
    ],
)
def test_trip_dates_must_be_ordered_and_consecutive(
    start_date: date, end_date: date, expected_code: str
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(start_date=start_date, end_date=end_date)

    assert error.value.code == expected_code
    assert error.value.field == "end_date"


@pytest.mark.parametrize(
    ("evaluated_at", "start_date", "end_date"),
    [
        (
            datetime.fromisoformat("2026-08-30T10:00:00+08:00"),
            date(2026, 8, 31),
            date(2026, 9, 1),
        ),
        (
            datetime.fromisoformat("2026-12-30T10:00:00+08:00"),
            date(2026, 12, 31),
            date(2027, 1, 1),
        ),
    ],
)
def test_consecutive_dates_work_across_month_and_year_boundaries(
    evaluated_at: datetime, start_date: date, end_date: date
) -> None:
    request = valid_input(
        evaluated_at=evaluated_at,
        start_date=start_date,
        end_date=end_date,
    )
    assert request.end_date == end_date


@pytest.mark.parametrize("travelers", [0, 9, True, "2"])
def test_travelers_must_be_a_strict_integer_from_1_to_8(travelers: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(travelers=travelers)

    assert error.value.code == "travelers_invalid"
    assert error.value.field == "travelers"


def test_text_inputs_are_trimmed_without_hiding_duplicate_interests() -> None:
    request = valid_input(
        city="  杭州  ",
        interests=("  自然", "历史  "),
        free_text="  节奏不要太赶  ",
    )
    assert request.city == "杭州"
    assert request.interests == ("自然", "历史")
    assert request.free_text == "节奏不要太赶"

    with pytest.raises(DomainInvariantError) as error:
        valid_input(interests=("自然", " 自然 "))
    assert error.value.code == "duplicate_interest"
    assert error.value.field == "interests"


@pytest.mark.parametrize("city", ["", " ", "杭", "城" * 31, 123])
def test_city_must_be_text_from_2_to_30_characters(city: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(city=city)

    assert error.value.field == "city"


def test_interest_count_and_each_interest_text_are_bounded() -> None:
    invalid_interests = [
        ("一", "二", "三", "四", "五", "六"),
        ("自然", " "),
        ("兴" * 121,),
        ["自然"],
    ]
    for interests in invalid_interests:
        with pytest.raises(DomainInvariantError) as error:
            valid_input(interests=interests)
        assert error.value.field == "interests"


@pytest.mark.parametrize("free_text", ["字" * 201, 123])
def test_free_text_is_optional_text_with_at_most_200_characters(free_text: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        valid_input(free_text=free_text)

    assert error.value.field == "free_text"


def test_frozen_request_contract_maps_to_domain_without_date_or_text_drift() -> None:
    fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    contract = TripPlanRequest.model_validate(fixture["request"])
    domain_request = TripRequestInput(
        city=contract.city,
        start_date=contract.start_date,
        end_date=contract.start_date + timedelta(days=1),
        travelers=contract.travelers,
        interests=contract.preferences.interests,
        free_text=contract.preferences.free_text,
        evaluated_at=datetime.fromisoformat(fixture["fixed_now"]),
    )

    assert domain_request.city == contract.city
    assert domain_request.start_date == contract.start_date
    assert domain_request.end_date == date(2026, 8, 16)
    assert domain_request.interests == contract.preferences.interests
