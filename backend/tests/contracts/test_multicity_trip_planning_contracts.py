"""F-004B1 standalone V3 request, plan, and response contracts."""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import date, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequestV3,
    TripPlanResponseV3,
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


def request_payload(city_count: int = 2) -> dict[str, object]:
    start = date(2026, 8, 21)
    day_count = city_count + 1
    cities = ["杭州", "上海", "南京"][:city_count]
    return {
        "request_version": "3",
        "client_request_id": "11111111-1111-4111-8111-111111111111",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=day_count - 1)).isoformat(),
        "travelers": 2,
        "total_budget": money("5000.00"),
        "preferences": {"interests": ["自然"], "free_text": "", "hard_constraints": []},
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


@pytest.mark.parametrize(("city_count", "day_count"), [(2, 3), (3, 4)])
def test_v3_request_accepts_two_or_three_ordered_city_stays(
    city_count: int, day_count: int
) -> None:
    request = TripPlanRequestV3.model_validate(request_payload(city_count))

    assert request.request_version == "3"
    assert request.day_count == day_count
    assert len(request.city_stays) == city_count
    assert len(request.intercity_segments) == city_count - 1
    assert request.transfer_dates == tuple(
        date(2026, 8, 22 + index) for index in range(city_count - 1)
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["city_stays"].pop(),
        lambda payload: payload["city_stays"].append(copy.deepcopy(payload["city_stays"][0])),
        lambda payload: payload["city_stays"][1].update(city="杭州"),
        lambda payload: payload["city_stays"][0].update(nights=2),
        lambda payload: payload["intercity_segments"].clear(),
        lambda payload: payload["intercity_segments"][0].update(to_city_index=2),
        lambda payload: payload["intercity_segments"][0].update(mode="self_drive"),
        lambda payload: payload["intercity_segments"][0].update(
            arrival_at="2026-08-23T01:00:00+08:00"
        ),
    ],
)
def test_v3_request_rejects_city_night_segment_and_overnight_drift(
    mutate: Callable[[dict[str, object]], object],
) -> None:
    payload = request_payload()
    mutate(payload)
    with pytest.raises(ValidationError):
        TripPlanRequestV3.model_validate(payload)


def test_v3_request_is_independent_and_rejects_single_city_fields_and_private_ticketing() -> None:
    for field, value in (
        ("city", "杭州"),
        ("accommodation", {"area_or_poi": "西湖"}),
        ("intercity_transport_cost", money("1.00")),
        ("passenger_name", "测试乘客"),
    ):
        payload = request_payload()
        payload[field] = value
        with pytest.raises(ValidationError):
            TripPlanRequestV3.model_validate(payload)


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
        "response_version": "3",
        "job_id": "22222222-2222-4222-8222-222222222222",
        "trace_id": "33333333-3333-4333-8333-333333333333",
        "client_request_id": "11111111-1111-4111-8111-111111111111",
        "status": "partial" if unknown_fare else "ready",
        "attempt": 1,
        "request_summary": {
            "request_version": "3",
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
            "plan_format_version": "3",
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


def test_v3_ready_response_validates_city_day_segment_and_user_source_references() -> None:
    response = TripPlanResponseV3.model_validate(response_payload())
    assert response.status is PlanningStatus.READY
    assert response.plan is not None
    assert response.plan.plan_format_version == "3"
    assert response.plan.days[1].intercity_segment_id is not None
    assert len(response.resolved_destinations) == 2


def test_v3_plan_rejects_transfer_activity_inside_buffer_and_cross_city_route() -> None:
    inside_buffer = response_payload()
    plan = cast(dict[str, object], inside_buffer["plan"])
    days = cast(list[dict[str, object]], plan["days"])
    days[1]["activities"] = [
        {
            **activity("a5000000-0000-4000-8000-000000000001", ACTIVITY_A, "出发前活动"),
            "start_time": "08:30:00",
            "end_time": "09:30:00",
        }
    ]
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(inside_buffer)

    cross_city = response_payload()
    plan = cast(dict[str, object], cross_city["plan"])
    days = cast(list[dict[str, object]], plan["days"])
    days[0]["routes"] = [
        {
            "route_id": "a6000000-0000-4000-8000-000000000001",
            "origin_location_id": HOTEL_A,
            "destination_location_id": STATION_B,
            "mode": "walking",
            "distance_meters": 100,
            "duration_minutes": 10,
            "fare": None,
            "source_ids": [SOURCE_ID],
        }
    ]
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(cross_city)


def test_v3_plan_rejects_cross_day_city_jump_before_the_transfer() -> None:
    payload = response_payload()
    plan = cast(dict[str, object], payload["plan"])
    days = cast(list[dict[str, object]], plan["days"])
    days[0].update(
        departure_city_index=1,
        arrival_city_index=1,
        overnight_city_index=1,
        accommodation_location_id=HOTEL_B,
        activities=[activity(ITEM_A, ACTIVITY_B, "提前跳到上海")],
    )

    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(payload)


def test_v3_response_binds_transfer_dates_to_request_summary_nights() -> None:
    payload = response_payload()
    plan = cast(dict[str, object], payload["plan"])
    segments = cast(list[dict[str, object]], plan["intercity_segments"])
    segments[0].update(
        departure_at="2026-08-23T10:00:00+08:00",
        arrival_at="2026-08-23T12:00:00+08:00",
    )
    days = cast(list[dict[str, object]], plan["days"])
    days[1].update(
        departure_city_index=0,
        arrival_city_index=0,
        overnight_city_index=0,
        intercity_segment_id=None,
        accommodation_location_id=HOTEL_A,
        activities=[activity(ITEM_A, ACTIVITY_A, "西湖")],
    )
    days[2].update(
        departure_city_index=0,
        arrival_city_index=1,
        overnight_city_index=1,
        intercity_segment_id=SEGMENT_ID,
        activities=[],
    )

    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(payload)


def test_v3_unknown_fare_is_partial_and_cannot_be_projected_ready() -> None:
    partial = TripPlanResponseV3.model_validate(response_payload(unknown_fare=True))
    assert partial.status is PlanningStatus.PARTIAL
    assert partial.plan is not None
    assert partial.plan.budget_summary.unknown_count == 1
    assert partial.plan.intercity_segments[0].fare.amount is None

    invalid_ready = response_payload(unknown_fare=True)
    invalid_ready["status"] = "ready"
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(invalid_ready)


def test_v3_user_source_cannot_claim_provider_verification_or_url() -> None:
    for field, value in (
        ("provider", "amap"),
        ("freshness", "fresh"),
        ("provider_record_id", "G123"),
        ("reference_url", "https://example.com/ticket"),
    ):
        payload = response_payload()
        sources = cast(list[dict[str, object]], payload["sources"])
        sources[0][field] = value
        with pytest.raises(ValidationError):
            TripPlanResponseV3.model_validate(payload)


def test_v3_terminal_shapes_fail_closed() -> None:
    failed_with_plan = response_payload()
    failed_with_plan["status"] = "failed"
    failed_with_plan["errors"] = [
        {
            "code": "internal_error",
            "message": "规划失败。",
            "field": None,
            "provider": None,
            "retryable": False,
        }
    ]
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(failed_with_plan)

    partial_without_evidence = response_payload()
    partial_without_evidence["status"] = "partial"
    partial_without_evidence["warnings"] = []
    partial_without_evidence["uncertainties"] = []
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(partial_without_evidence)

    ready_with_error = response_payload()
    ready_with_error["errors"] = [
        {
            "code": "internal_error",
            "message": "规划失败。",
            "field": None,
            "provider": None,
            "retryable": False,
        }
    ]
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(ready_with_error)

    needs_input_with_plan = response_payload()
    needs_input_with_plan["status"] = "needs_input"
    needs_input_with_plan["errors"] = [
        {
            "code": "input_invalid",
            "message": "需要补充输入。",
            "field": "city_stays",
            "provider": None,
            "retryable": False,
        }
    ]
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(needs_input_with_plan)

    needs_input_without_error = response_payload()
    needs_input_without_error.update(
        status="needs_input",
        resolved_destinations=[],
        plan=None,
        errors=[],
    )
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(needs_input_without_error)

    retryable_without_retryable_error = response_payload(unknown_fare=True)
    retryable_without_retryable_error["retryable"] = True
    with pytest.raises(ValidationError):
        TripPlanResponseV3.model_validate(retryable_without_retryable_error)


def test_v3_accepts_all_five_valid_terminal_shapes() -> None:
    ready = response_payload()
    partial = response_payload(unknown_fare=True)
    conflict = response_payload()
    conflict.update(
        status="conflict",
        violations=[
            {
                "code": "intercity_buffer_conflict",
                "severity": "error",
                "message": "城际缓冲与活动窗口冲突。",
                "affected_refs": [SEGMENT_ID],
            }
        ],
    )
    needs_input = response_payload()
    needs_input.update(
        status="needs_input",
        resolved_destinations=[],
        plan=None,
        errors=[
            {
                "code": "input_invalid",
                "message": "需要补充输入。",
                "field": "city_stays",
                "provider": None,
                "retryable": False,
            }
        ],
    )
    failed = response_payload()
    failed.update(
        status="failed",
        resolved_destinations=[],
        plan=None,
        errors=[
            {
                "code": "internal_error",
                "message": "规划失败。",
                "field": None,
                "provider": None,
                "retryable": False,
            }
        ],
    )

    assert [
        TripPlanResponseV3.model_validate(payload).status
        for payload in (ready, partial, conflict, needs_input, failed)
    ] == [
        PlanningStatus.READY,
        PlanningStatus.PARTIAL,
        PlanningStatus.CONFLICT,
        PlanningStatus.NEEDS_INPUT,
        PlanningStatus.FAILED,
    ]
