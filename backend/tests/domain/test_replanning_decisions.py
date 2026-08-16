"""Typed lifecycle and decision values remain framework-free."""

from intelligent_travel_assistant.domain import (
    ReplanChoice,
    ReplanDecisionStatus,
    ReplanStatus,
)


def test_replan_lifecycle_is_independent_from_planning_status() -> None:
    assert ReplanStatus.AWAITING_CONFIRMATION.value == "awaiting_confirmation"
    assert ReplanDecisionStatus.PENDING.value == "pending"
    assert ReplanChoice.APPROVE.value == "approve"
