"""Contract tests for the F-001 public schemas and state vocabulary."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from intelligent_travel_assistant.contracts import (
    ALLOWED_PLANNING_TRANSITIONS,
    ApiError,
    ApiErrorCode,
    ApiErrorResponse,
    CostCategory,
    CostConfidence,
    CostItem,
    DataFreshness,
    Money,
    PlanningStatus,
    ProviderName,
    SourceRecord,
    TripPlanRequest,
)

REQUEST_ID = UUID("11111111-1111-4111-8111-111111111111")
SOURCE_ID = UUID("22222222-2222-4222-8222-222222222222")
COST_ID = UUID("33333333-3333-4333-8333-333333333333")


def valid_request_payload() -> dict[str, object]:
    return {
        "client_request_id": str(REQUEST_ID),
        "city": "杭州",
        "start_date": "2026-08-15",
        "travelers": 2,
        "total_budget": {"amount": "4000.00", "currency": "CNY"},
        "preferences": {
            "interests": ["自然", "历史"],
            "free_text": "节奏不要太赶",
            "hard_constraints": [],
        },
        "pace": "balanced",
        "transport_modes": ["walking", "public_transit"],
        "accommodation": {
            "area_or_poi": "西湖附近",
            "one_night_cost": {"amount": "700.00", "currency": "CNY"},
        },
        "day_windows": [
            {"day_offset": 0, "start_time": "09:00:00", "end_time": "20:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
        ],
        "intercity_transport_cost": {"amount": "1000.00", "currency": "CNY"},
    }


def test_request_contract_uses_the_approved_meal_default() -> None:
    request = TripPlanRequest.model_validate(valid_request_payload())

    assert request.city == "杭州"
    assert request.start_date == date(2026, 8, 15)
    assert request.travelers == 2
    assert request.meal_budget_per_person_per_day.amount == Decimal("100.00")
    assert request.day_windows[0].start_time == time(9, 0)
    assert request.model_dump(mode="json")["meal_budget_per_person_per_day"] == {
        "amount": "100.00",
        "currency": "CNY",
    }


def test_request_contract_rejects_unknown_fields_and_numeric_strings() -> None:
    payload = valid_request_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        TripPlanRequest.model_validate(payload)

    payload = valid_request_payload()
    payload["travelers"] = "2"
    with pytest.raises(ValidationError):
        TripPlanRequest.model_validate(payload)


@pytest.mark.parametrize(
    "windows",
    [
        [
            {"day_offset": 0, "start_time": "09:00:00", "end_time": "09:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
        ],
        [
            {"day_offset": 0, "start_time": "18:00:00", "end_time": "09:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
        ],
        [
            {"day_offset": 0, "start_time": "09:00:00", "end_time": "18:00:00"},
            {"day_offset": 0, "start_time": "10:00:00", "end_time": "19:00:00"},
        ],
    ],
)
def test_request_rejects_invalid_or_duplicate_day_windows(
    windows: list[dict[str, object]],
) -> None:
    payload = valid_request_payload()
    payload["day_windows"] = windows

    with pytest.raises(ValidationError):
        TripPlanRequest.model_validate(payload)


def test_money_rejects_binary_numbers_and_more_than_two_decimal_places() -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": 100.0, "currency": "CNY"})

    with pytest.raises(ValidationError):
        Money.model_validate({"amount": "100.001", "currency": "CNY"})

    amount_schema = Money.model_json_schema()["properties"]["amount"]
    assert amount_schema["type"] == "string"
    assert amount_schema["pattern"] == r"^(0|[1-9]\d*)(\.\d{1,2})?$"


def test_unknown_cost_never_uses_zero_and_known_cost_requires_an_amount() -> None:
    unknown = CostItem(
        cost_id=COST_ID,
        category=CostCategory.TICKET,
        confidence=CostConfidence.UNKNOWN,
        amount=None,
        description="门票价格未知",
    )
    assert unknown.amount is None

    with pytest.raises(ValidationError):
        CostItem(
            cost_id=COST_ID,
            category=CostCategory.TICKET,
            confidence=CostConfidence.UNKNOWN,
            amount=Money(amount=Decimal("0.00")),
            description="错误地把未知门票当成零元",
        )

    with pytest.raises(ValidationError):
        CostItem(
            cost_id=COST_ID,
            category=CostCategory.MEAL,
            confidence=CostConfidence.ESTIMATED,
            amount=None,
            description="缺少估算金额",
        )


def test_source_timestamps_require_an_explicit_timezone() -> None:
    with pytest.raises(ValidationError):
        SourceRecord(
            source_id=SOURCE_ID,
            provider=ProviderName.QWEATHER,
            source_type="weather_forecast",
            fetched_at=datetime(2026, 8, 13, 12, 0),
            freshness=DataFreshness.FRESH,
        )

    source = SourceRecord(
        source_id=SOURCE_ID,
        provider=ProviderName.QWEATHER,
        source_type="weather_forecast",
        fetched_at=datetime(2026, 8, 13, 12, 0, tzinfo=UTC),
        freshness=DataFreshness.FRESH,
    )
    assert source.fetched_at.utcoffset() is not None


def test_state_contract_has_no_unapproved_shortcuts() -> None:
    assert ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.DRAFT] == frozenset(
        {PlanningStatus.NORMALIZING}
    )
    assert PlanningStatus.READY not in ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.PLANNING]
    assert ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.READY] == frozenset()
    assert ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.NEEDS_INPUT] == frozenset()
    assert ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.CONFLICT] == frozenset()
    assert ALLOWED_PLANNING_TRANSITIONS[PlanningStatus.FAILED] == frozenset(
        {PlanningStatus.NORMALIZING}
    )


def test_verified_cost_requires_a_source() -> None:
    with pytest.raises(ValidationError):
        CostItem(
            cost_id=COST_ID,
            category=CostCategory.TICKET,
            confidence=CostConfidence.VERIFIED,
            amount=Money(amount=Decimal("80.00")),
            description="缺少来源的已验证门票",
        )


def test_error_contract_rejects_raw_extra_details() -> None:
    response = ApiErrorResponse(
        trace_id=None,
        error=ApiError(
            code=ApiErrorCode.CONFIGURATION_MISSING,
            message="缺少和风天气本地配置",
            provider="qweather",
            retryable=False,
        ),
    )
    assert response.error.code is ApiErrorCode.CONFIGURATION_MISSING

    with pytest.raises(ValidationError):
        ApiErrorResponse.model_validate(
            {
                "trace_id": None,
                "error": {
                    "code": "provider_unauthorized",
                    "message": "鉴权失败",
                    "retryable": False,
                    "raw_provider_response": "must not cross the boundary",
                },
            }
        )
