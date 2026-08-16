"""Strict public DTO tests for the three F-003 replan endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from intelligent_travel_assistant.contracts import ReplanDecisionRequest, ReplanRequest

REQUEST_ID = "10000000-0000-4000-8000-000000000001"
PLAN_ID = "10000000-0000-4000-8000-000000000002"
ACTIVITY_ID = "10000000-0000-4000-8000-000000000003"


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
