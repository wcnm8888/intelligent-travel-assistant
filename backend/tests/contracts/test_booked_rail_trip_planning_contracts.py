"""F-004C standalone V4 booked-rail strict contracts."""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequestV3,
    TripPlanRequestV4,
    TripPlanResponseV4,
    TripPlanV4,
)

SOURCE_ID = "d1000000-0000-4000-8000-000000000001"
HOTEL_A = "a1000000-0000-4000-8000-000000000001"
HOTEL_B = "b1000000-0000-4000-8000-000000000001"
STATION_A = "a2000000-0000-4000-8000-000000000001"
STATION_B = "b2000000-0000-4000-8000-000000000001"
ACTIVITY_A = "a3000000-0000-4000-8000-000000000001"
ACTIVITY_B = "b3000000-0000-4000-8000-000000000001"
ITEM_A = "a4000000-0000-4000-8000-000000000001"
ITEM_B = "b4000000-0000-4000-8000-000000000001"
SEGMENT_ID = "e1000000-0000-4000-8000-000000000001"
COST_ID = "e2000000-0000-4000-8000-000000000001"
PLAN_ID = "f1000000-0000-4000-8000-000000000001"


def money(amount: str) -> dict[str, str]:
    return {"amount": amount, "currency": "CNY"}


def request_payload(*, version: str = "4", city_count: int = 2) -> dict[str, object]:
    start = date(2026, 8, 21)
    day_count = city_count + 1
    cities = ["杭州", "上海", "南京"][:city_count]
    preferences: dict[str, object] = {"interests": ["自然"]}
    if version != "4":
        preferences.update(free_text="", hard_constraints=[])
    return {
        "request_version": version,
        "client_request_id": "11111111-1111-4111-8111-111111111111",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=day_count - 1)).isoformat(),
        "travelers": 2,
        "total_budget": money("5000.00"),
        "preferences": preferences,
        "pace": "balanced",
        "transport_modes": ["walking", "public_transit"],
        "city_stays": [
            {
                "city": city,
                "nights": 1,
                "accommodation": {"area_or_poi": f"{city}住宿", "one_night_cost": None},
            }
            for city in cities
        ],
        "intercity_segments": [
            {
                "from_city_index": index,
                "to_city_index": index + 1,
                "mode": "rail",
                "service_number": " g1234 " if index == 0 else "d2281",
                "departure_station": f"{cities[index]}站",
                "arrival_station": f"{cities[index + 1]}站",
                "departure_at": f"2026-08-{22 + index:02d}T10:00:00+08:00",
                "arrival_at": f"2026-08-{22 + index:02d}T12:00:00+08:00",
                "fare": money("120.00"),
            }
            for index in range(city_count - 1)
        ],
        "day_windows": [
            {"day_offset": offset, "start_time": "08:00:00", "end_time": "20:00:00"}
            for offset in range(day_count)
        ],
        "meal_budget_per_person_per_day": money("100.00"),
    }


def source() -> dict[str, object]:
    return {
        "source_id": SOURCE_ID,
        "provider": "user",
        "source_type": "user_provided_intercity_segment",
        "provider_record_id": None,
        "fetched_at": "2026-08-20T12:00:00+08:00",
        "valid_until": None,
        "freshness": "unknown_validity",
        "reference_url": None,
        "attributions": ["用户提供"],
        "warnings": ["未核验班次、票价、余票或库存"],
    }


def location(location_id: str, name: str, category: str, adcode: str) -> dict[str, object]:
    return {
        "location_id": location_id,
        "provider": "user",
        "provider_place_id": None,
        "name": name,
        "category": category,
        "address": None,
        "city_adcode": adcode,
        "coordinates": None,
        "source_ids": [SOURCE_ID],
    }


def activity(item_id: str, location_id: str, title: str) -> dict[str, object]:
    return {
        "item_id": item_id,
        "location_id": location_id,
        "title": title,
        "start_time": "14:00:00",
        "end_time": "15:00:00",
        "cost_items": [],
        "source_ids": [SOURCE_ID],
    }


def response_payload(*, unknown_fare: bool = False) -> dict[str, object]:
    fare = {
        "cost_id": COST_ID,
        "category": "intercity_transport",
        "confidence": "unknown" if unknown_fare else "user_provided",
        "amount": None if unknown_fare else money("120.00"),
        "description": "用户提供城际费用",
        "source_ids": [SOURCE_ID],
    }
    return {
        "response_version": "4",
        "job_id": "22222222-2222-4222-8222-222222222222",
        "trace_id": "33333333-3333-4333-8333-333333333333",
        "client_request_id": "11111111-1111-4111-8111-111111111111",
        "status": "partial" if unknown_fare else "ready",
        "attempt": 1,
        "request_summary": {
            "request_version": "4",
            "city_stays": [{"city": "杭州", "nights": 1}, {"city": "上海", "nights": 1}],
            "start_date": "2026-08-21",
            "end_date": "2026-08-23",
            "travelers": 2,
            "budget": money("5000.00"),
        },
        "resolved_destinations": [
            {"city_name": "杭州市", "adcode": "330100", "center": None, "source_ids": [SOURCE_ID]},
            {"city_name": "上海市", "adcode": "310000", "center": None, "source_ids": [SOURCE_ID]},
        ],
        "plan": {
            "plan_id": PLAN_ID,
            "plan_format_version": "4",
            "city_adcodes": ["330100", "310000"],
            "start_date": "2026-08-21",
            "end_date": "2026-08-23",
            "locations": [
                location(HOTEL_A, "杭州住宿", "accommodation_anchor", "330100"),
                location(STATION_A, "杭州站", "rail_station", "330100"),
                location(STATION_B, "上海站", "rail_station", "310000"),
                location(HOTEL_B, "上海住宿", "accommodation_anchor", "310000"),
                location(ACTIVITY_A, "西湖", "attraction", "330100"),
                location(ACTIVITY_B, "外滩", "attraction", "310000"),
            ],
            "intercity_segments": [
                {
                    "segment_id": SEGMENT_ID,
                    "from_city_index": 0,
                    "to_city_index": 1,
                    "mode": "rail",
                    "service_number": "G1234",
                    "departure_station_location_id": STATION_A,
                    "arrival_station_location_id": STATION_B,
                    "departure_at": "2026-08-22T10:00:00+08:00",
                    "arrival_at": "2026-08-22T12:00:00+08:00",
                    "fare": fare,
                    "source_ids": [SOURCE_ID],
                }
            ],
            "days": [
                {
                    "local_date": "2026-08-21",
                    "departure_city_index": 0,
                    "arrival_city_index": 0,
                    "overnight_city_index": 0,
                    "intercity_segment_id": None,
                    "accommodation_location_id": HOTEL_A,
                    "activities": [activity(ITEM_A, ACTIVITY_A, "西湖")],
                    "routes": [],
                    "weather": None,
                },
                {
                    "local_date": "2026-08-22",
                    "departure_city_index": 0,
                    "arrival_city_index": 1,
                    "overnight_city_index": 1,
                    "intercity_segment_id": SEGMENT_ID,
                    "accommodation_location_id": HOTEL_B,
                    "activities": [],
                    "routes": [],
                    "weather": None,
                },
                {
                    "local_date": "2026-08-23",
                    "departure_city_index": 1,
                    "arrival_city_index": 1,
                    "overnight_city_index": 1,
                    "intercity_segment_id": None,
                    "accommodation_location_id": HOTEL_B,
                    "activities": [activity(ITEM_B, ACTIVITY_B, "外滩")],
                    "routes": [],
                    "weather": None,
                },
            ],
            "budget_summary": {
                "budget": money("5000.00"),
                "known_total": money("0.00" if unknown_fare else "120.00"),
                "unknown_count": 1 if unknown_fare else 0,
                "assessment": "budget_indeterminate" if unknown_fare else "within_budget",
                "cost_items": [fare],
            },
        },
        "violations": [],
        "warnings": ["城际段由用户提供，未核验班次、票价、余票或库存"],
        "uncertainties": (
            [
                {
                    "code": "intercity_fare_unknown",
                    "message": "城际费用未知。",
                    "affected_refs": [SEGMENT_ID],
                    "source_ids": [SOURCE_ID],
                }
            ]
            if unknown_fare
            else []
        ),
        "sources": [source()],
        "errors": [],
        "retryable": False,
        "created_at": "2026-08-20T12:00:00+08:00",
        "updated_at": "2026-08-20T12:01:00+08:00",
    }


@pytest.mark.parametrize("city_count", [2, 3])
def test_v4_request_is_independent_strict_and_normalizes_service_number(city_count: int) -> None:
    request = TripPlanRequestV4.model_validate(request_payload(city_count=city_count))

    assert request.request_version == "4"
    assert request.transfer_dates == tuple(
        date(2026, 8, 22 + index) for index in range(city_count - 1)
    )
    assert (
        tuple(item.service_number for item in request.intercity_segments)
        == (
            "G1234",
            "D2281",
        )[: city_count - 1]
    )
    assert "duration" not in request.model_dump()["intercity_segments"][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("free_text", "SYNTHETIC_V4_PRIVATE_SENTINEL"),
        ("hard_constraints", ["SYNTHETIC_V4_PRIVATE_SENTINEL"]),
    ],
)
def test_v4_preferences_reject_free_text_and_hard_constraints(field: str, value: object) -> None:
    payload = request_payload()
    preferences = cast(dict[str, object], payload["preferences"])
    preferences[field] = value

    with pytest.raises(ValidationError):
        TripPlanRequestV4.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("service_number", "G-123"),
        ("service_number", 123),
        ("mode", "air"),
        ("duration", 120),
        ("passenger_name", "测试乘客"),
        ("order_number", "SECRET"),
        ("seat_number", "01A"),
        ("ticket_qr", "raw"),
    ],
)
def test_v4_segment_rejects_invalid_service_extra_or_ticketing_fields(
    field: str, value: object
) -> None:
    payload = request_payload()
    segments = cast(list[dict[str, object]], payload["intercity_segments"])
    segments[0][field] = value

    with pytest.raises(ValidationError):
        TripPlanRequestV4.model_validate(payload)


def test_v4_request_rejects_zero_fare_cross_day_timezone_and_tag_mismatch() -> None:
    mutations: list[tuple[str, object]] = [
        ("fare", money("0.00")),
        ("arrival_at", "2026-08-23T12:00:00+08:00"),
        ("departure_at", "2026-08-22T10:00:00+00:00"),
    ]
    for field, value in mutations:
        payload = request_payload()
        segments = cast(list[dict[str, object]], payload["intercity_segments"])
        segments[0][field] = value
        with pytest.raises(ValidationError):
            TripPlanRequestV4.model_validate(payload)

    v3_as_v4 = request_payload(version="3")
    with pytest.raises(ValidationError):
        TripPlanRequestV4.model_validate(v3_as_v4)
    v4_as_v3 = request_payload()
    with pytest.raises(ValidationError):
        TripPlanRequestV3.model_validate(v4_as_v3)


def test_v4_response_preserves_unverified_user_source_and_has_no_duration_key() -> None:
    response = TripPlanResponseV4.model_validate(response_payload())

    assert response.status is PlanningStatus.READY
    assert response.response_version == "4"
    assert response.plan is not None
    assert response.plan.plan_format_version == "4"
    assert response.plan.intercity_segments[0].service_number == "G1234"
    assert response.sources[0].freshness.value == "unknown_validity"
    assert response.sources[0].attributions == ("用户提供",)
    assert response.sources[0].warnings == ("未核验班次、票价、余票或库存",)
    assert "duration" not in response.model_dump()["plan"]["intercity_segments"][0]


def test_v4_unknown_fare_stays_null_and_requires_partial() -> None:
    partial = TripPlanResponseV4.model_validate(response_payload(unknown_fare=True))
    assert partial.status is PlanningStatus.PARTIAL
    assert partial.plan is not None
    assert partial.plan.intercity_segments[0].fare.amount is None

    invalid = response_payload(unknown_fare=True)
    invalid["status"] = "ready"
    with pytest.raises(ValidationError):
        TripPlanResponseV4.model_validate(invalid)


@pytest.mark.parametrize(
    ("location_id", "start_time", "end_time"),
    [
        (ACTIVITY_A, "08:30:00", "09:30:00"),
        (ACTIVITY_B, "12:15:00", "13:00:00"),
    ],
)
def test_v4_plan_enforces_rail_sixty_thirty_minute_buffers(
    location_id: str, start_time: str, end_time: str
) -> None:
    payload = response_payload()
    plan = cast(dict[str, object], payload["plan"])
    days = cast(list[dict[str, object]], plan["days"])
    transfer_activity = activity(
        "a5000000-0000-4000-8000-000000000001",
        location_id,
        "缓冲冲突活动",
    )
    transfer_activity.update(start_time=start_time, end_time=end_time)
    days[1]["activities"] = [transfer_activity]

    with pytest.raises(ValidationError):
        TripPlanResponseV4.model_validate(payload)


def test_v4_response_rejects_provider_claim_private_fields_and_tag_mismatch() -> None:
    for field, value in (
        ("provider", "amap"),
        ("freshness", "fresh"),
        ("provider_record_id", "G1234"),
        ("reference_url", "https://example.com/ticket"),
    ):
        payload = response_payload()
        sources = cast(list[dict[str, object]], payload["sources"])
        sources[0][field] = value
        with pytest.raises(ValidationError):
            TripPlanResponseV4.model_validate(payload)

    extra = response_payload()
    plan = cast(dict[str, object], extra["plan"])
    segments = cast(list[dict[str, object]], plan["intercity_segments"])
    segments[0]["order_number"] = "SECRET"
    with pytest.raises(ValidationError):
        TripPlanResponseV4.model_validate(extra)

    wrong_response = response_payload()
    wrong_response["response_version"] = "3"
    with pytest.raises(ValidationError):
        TripPlanResponseV4.model_validate(wrong_response)

    wrong_plan = response_payload()
    cast(dict[str, object], wrong_plan["plan"])["plan_format_version"] = "3"
    with pytest.raises(ValidationError):
        TripPlanResponseV4.model_validate(wrong_plan)


def test_v4_concrete_contracts_are_strict_and_v3_shape_remains_exact() -> None:
    request = TypeAdapter(TripPlanRequestV4).validate_python(request_payload())
    response = TypeAdapter(TripPlanResponseV4).validate_python(response_payload())
    plan = TypeAdapter(TripPlanV4).validate_python(response_payload()["plan"])

    assert isinstance(request, TripPlanRequestV4)
    assert isinstance(response, TripPlanResponseV4)
    assert isinstance(plan, TripPlanV4)

    v3 = request_payload(version="3")
    segments = cast(list[dict[str, object]], v3["intercity_segments"])
    for item in segments:
        item.pop("service_number")
    parsed_v3 = TripPlanRequestV3.model_validate(v3)
    assert set(parsed_v3.model_dump()) == set(v3)
    assert "service_number" not in parsed_v3.model_dump()["intercity_segments"][0]

    invalid = copy.deepcopy(request_payload())
    invalid["request_version"] = "3"
    with pytest.raises(ValidationError):
        TypeAdapter(TripPlanRequestV4).validate_python(invalid)
