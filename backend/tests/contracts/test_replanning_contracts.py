"""Strict public DTO tests for the three F-003 replan endpoints."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from intelligent_travel_assistant.contracts import (
    ReplanChangeSetResponse,
    ReplanDecisionRequest,
    ReplanPublicOperation,
    ReplanPublicStatus,
    ReplanRequest,
    ReplanResponse,
    TripPlanResponseV2,
)

REQUEST_ID = "10000000-0000-4000-8000-000000000001"
PLAN_ID = "10000000-0000-4000-8000-000000000002"
ACTIVITY_ID = "10000000-0000-4000-8000-000000000003"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def _v2_response() -> TripPlanResponseV2:
    payload = copy.deepcopy(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
    )
    summary = payload["request_summary"]
    plan = payload["plan"]
    start = date.fromisoformat(str(summary["start_date"]))
    end = start + timedelta(days=1)
    payload["response_version"] = "2"
    summary["request_version"] = "2"
    summary["end_date"] = end.isoformat()
    plan["plan_format_version"] = "2"
    return TripPlanResponseV2.model_validate(payload)


@pytest.mark.parametrize(
    "command",
    (
        {
            "operation": "replace_activity",
            "target_activity_id": ACTIVITY_ID,
            "replacement_categories": ["museum"],
            "reason_code": "user_preference",
        },
        {"operation": "delete_activity", "target_activity_id": ACTIVITY_ID},
        {
            "operation": "adjust_activity_time",
            "target_activity_id": ACTIVITY_ID,
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        },
        {
            "operation": "reorder_activities",
            "local_date": "2026-08-15",
            "ordered_activity_ids": [ACTIVITY_ID],
        },
    ),
)
def test_replan_request_accepts_only_the_four_tagged_commands(
    command: dict[str, object],
) -> None:
    request = ReplanRequest.model_validate(
        {
            "replan_request_id": REQUEST_ID,
            "baseline_plan_id": PLAN_ID,
            "command": command,
        }
    )
    assert request.replan_request_id == UUID(REQUEST_ID)
    assert request.command.operation == command["operation"]


@pytest.mark.parametrize(
    "mutation",
    (
        {"unexpected": "field"},
        {"command": {"operation": "add_activity", "target_activity_id": ACTIVITY_ID}},
        {
            "command": {
                "operation": "delete_activity",
                "target_activity_id": ACTIVITY_ID,
                "prompt": "完整自然语言请求",
            }
        },
    ),
)
def test_replan_request_rejects_extra_unsupported_and_prompt_fields(
    mutation: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "replan_request_id": REQUEST_ID,
        "baseline_plan_id": PLAN_ID,
        "command": {"operation": "delete_activity", "target_activity_id": ACTIVITY_ID},
    }
    payload.update(mutation)
    with pytest.raises(ValidationError):
        ReplanRequest.model_validate(payload)


def test_decision_request_is_strict_and_choice_is_closed() -> None:
    assert ReplanDecisionRequest.model_validate({"choice": "approve"}).choice == "approve"
    assert ReplanDecisionRequest.model_validate({"choice": "cancel"}).choice == "cancel"
    with pytest.raises(ValidationError):
        ReplanDecisionRequest.model_validate({"choice": "restore"})
    with pytest.raises(ValidationError):
        ReplanDecisionRequest.model_validate({"choice": "approve", "prompt": "secret"})


def test_completed_replan_preserves_version_2_response_and_plan_tags() -> None:
    result = _v2_response()
    assert result.plan is not None
    now = datetime(2026, 8, 20, 3, tzinfo=UTC)
    response = ReplanResponse(
        job_id=result.job_id,
        replan_id=UUID("10000000-0000-4000-8000-000000000004"),
        replan_request_id=UUID(REQUEST_ID),
        trace_id=result.trace_id,
        baseline_plan_id=result.plan.plan_id,
        operation=ReplanPublicOperation.ADJUST_ACTIVITY_TIME,
        status=ReplanPublicStatus.COMPLETED,
        impact=None,
        confirmation_expires_at=now + timedelta(minutes=15),
        decision=None,
        result=result,
        change_set=ReplanChangeSetResponse(
            baseline_plan_id=result.plan.plan_id,
            result_plan_id=result.plan.plan_id,
            added_refs=(),
            removed_refs=(),
            changed_refs=(),
            change_codes=(),
        ),
        errors=(),
        created_at=now,
        updated_at=now,
    )

    serialized = response.model_dump(mode="json")
    assert serialized["result"]["response_version"] == "2"
    assert serialized["result"]["plan"]["plan_format_version"] == "2"
