"""F-004A version 2 request/plan/response contracts and legacy isolation."""

from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from intelligent_travel_assistant.contracts import (
    PlanningRequest,
    PlanningResponse,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanResponse,
    TripPlanResponseV2,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def legacy_request_payload() -> dict[str, object]:
    value = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    assert isinstance(value, dict)
    return value


def v2_request_payload(day_count: int = 3) -> dict[str, object]:
    value = copy.deepcopy(legacy_request_payload())
    start = date.fromisoformat(str(value["start_date"]))
    value["request_version"] = "2"
    value["end_date"] = (start + timedelta(days=day_count - 1)).isoformat()
    value["day_windows"] = [
        {"day_offset": offset, "start_time": "09:00:00", "end_time": "18:00:00"}
        for offset in range(day_count)
    ]
    return value


def v2_response_payload(day_count: int = 3) -> dict[str, object]:
    value = copy.deepcopy(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
    )
    assert isinstance(value, dict)
    summary = value["request_summary"]
    plan = value["plan"]
    assert isinstance(summary, dict)
    assert isinstance(plan, dict)
    start = date.fromisoformat(str(summary["start_date"]))
    end = start + timedelta(days=day_count - 1)
    summary["request_version"] = "2"
    summary["end_date"] = end.isoformat()
    value["response_version"] = "2"
    plan["plan_format_version"] = "2"
    plan["end_date"] = end.isoformat()
    original_days = plan["days"]
    assert isinstance(original_days, list) and len(original_days) == 2
    days: list[object] = []
    for offset in range(day_count):
        source = original_days[min(offset, 1)]
        assert isinstance(source, dict)
        day = copy.deepcopy(source)
        day_date = start + timedelta(days=offset)
        day["local_date"] = day_date.isoformat()
        weather = day.get("weather")
        if isinstance(weather, dict):
            weather["forecast_date"] = day_date.isoformat()
        days.append(day)
    plan["days"] = days
    return value


@pytest.mark.parametrize("day_count", [2, 3, 7])
def test_v2_request_accepts_exact_two_to_seven_day_spans(day_count: int) -> None:
    request: PlanningRequest = TypeAdapter(PlanningRequest).validate_python(
        v2_request_payload(day_count)
    )

    assert isinstance(request, TripPlanRequestV2)
    assert request.day_count == day_count
    assert tuple(item.day_offset for item in request.day_windows) == tuple(range(day_count))


@pytest.mark.parametrize("day_count", [1, 8])
def test_v2_request_rejects_out_of_scope_spans(day_count: int) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(PlanningRequest).validate_python(v2_request_payload(day_count))


@pytest.mark.parametrize("version", [None, 2, "3", True])
def test_version_discriminator_rejects_ambiguous_or_unknown_versions(version: object) -> None:
    payload = v2_request_payload()
    payload["request_version"] = version

    with pytest.raises(ValidationError):
        TypeAdapter(PlanningRequest).validate_python(payload)


def test_missing_version_is_legacy_only_and_never_backfills_v2_fields() -> None:
    legacy = legacy_request_payload()
    parsed: PlanningRequest = TypeAdapter(PlanningRequest).validate_python(legacy)
    assert type(parsed) is TripPlanRequest
    assert parsed.model_dump(mode="json") == legacy

    v2_without_tag = v2_request_payload()
    del v2_without_tag["request_version"]
    with pytest.raises(ValidationError):
        TypeAdapter(PlanningRequest).validate_python(v2_without_tag)


def test_v2_windows_require_the_exact_offset_set_and_strict_integer_offsets() -> None:
    for invalid_windows in (
        [
            {"day_offset": 0, "start_time": "09:00:00", "end_time": "18:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
        ],
        [
            {"day_offset": 0, "start_time": "09:00:00", "end_time": "18:00:00"},
            {"day_offset": 1, "start_time": "09:00:00", "end_time": "18:00:00"},
            {"day_offset": "2", "start_time": "09:00:00", "end_time": "18:00:00"},
        ],
    ):
        payload = v2_request_payload()
        payload["day_windows"] = invalid_windows
        with pytest.raises(ValidationError):
            TypeAdapter(PlanningRequest).validate_python(payload)


@pytest.mark.parametrize("day_count", [2, 3, 7])
def test_v2_response_and_plan_are_explicitly_tagged_and_cover_every_day(
    day_count: int,
) -> None:
    response: PlanningResponse = TypeAdapter(PlanningResponse).validate_python(
        v2_response_payload(day_count)
    )

    assert isinstance(response, TripPlanResponseV2)
    assert response.response_version == "2"
    assert response.request_summary.request_version == "2"
    assert response.plan is not None
    assert response.plan.plan_format_version == "2"
    assert len(response.plan.days) == day_count


def test_v2_plan_rejects_missing_middle_day_and_more_than_two_daily_activities() -> None:
    missing_middle = v2_response_payload(3)
    plan = missing_middle["plan"]
    assert isinstance(plan, dict)
    days = plan["days"]
    assert isinstance(days, list)
    del days[1]
    with pytest.raises(ValidationError):
        TripPlanResponseV2.model_validate(missing_middle)

    too_many = v2_response_payload(3)
    plan = too_many["plan"]
    assert isinstance(plan, dict)
    days = plan["days"]
    assert isinstance(days, list) and isinstance(days[1], dict)
    activities = days[1]["activities"]
    assert isinstance(activities, list)
    assert activities
    activities.extend(copy.deepcopy(activities[0]) for _ in range(2))
    with pytest.raises(ValidationError):
        TripPlanResponseV2.model_validate(too_many)


def test_legacy_response_shape_remains_exact_and_rejects_v2_tags() -> None:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )["response"]
    response: PlanningResponse = TypeAdapter(PlanningResponse).validate_python(payload)

    assert type(response) is TripPlanResponse
    assert response.model_dump(mode="json") == payload

    tagged = copy.deepcopy(payload)
    tagged["response_version"] = "2"
    with pytest.raises(ValidationError):
        TripPlanResponse.model_validate(tagged)
