"""Exhaustive contract tests for the F-001 application state machine."""

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
    PlanningTransitionError,
    PlanningTransitionErrorCode,
    PlanningTransitionResult,
    PlanningTransitionTrigger,
)
from intelligent_travel_assistant.contracts import (
    ALLOWED_PLANNING_TRANSITIONS,
    PlanningStatus,
)

STATE_MACHINE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "application"
    / "state_machine"
)
RETRY_EDGES = {
    (PlanningStatus.PARTIAL, PlanningStatus.NORMALIZING),
    (PlanningStatus.FAILED, PlanningStatus.NORMALIZING),
}
ALL_EDGES = {
    (current, target)
    for current, targets in ALLOWED_PLANNING_TRANSITIONS.items()
    for target in targets
}


@pytest.mark.parametrize(("current", "target"), sorted(ALL_EDGES))
def test_every_frozen_allowed_edge_transitions_successfully(
    current: PlanningStatus,
    target: PlanningStatus,
) -> None:
    is_retry = (current, target) in RETRY_EDGES
    command = PlanningTransitionCommand(
        current_status=current,
        target_status=target,
        trigger=(
            PlanningTransitionTrigger.RETRY if is_retry else PlanningTransitionTrigger.ADVANCE
        ),
        retryable=is_retry,
    )

    result = PlanningStateMachine.transition(command)

    assert result == PlanningTransitionResult(
        previous_status=current,
        current_status=target,
        trigger=command.trigger,
    )
    assert command.current_status is current


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current in PlanningStatus
        for target in PlanningStatus
        if (current, target) not in ALL_EDGES
    ],
)
def test_every_non_edge_is_rejected_without_changing_state(
    current: PlanningStatus,
    target: PlanningStatus,
) -> None:
    command = PlanningTransitionCommand(current_status=current, target_status=target)

    with pytest.raises(PlanningTransitionError) as raised:
        PlanningStateMachine.transition(command)

    assert raised.value.code is PlanningTransitionErrorCode.TRANSITION_NOT_ALLOWED
    assert raised.value.current_status is current
    assert raised.value.target_status is target
    assert command.current_status is current


@pytest.mark.parametrize("current", (PlanningStatus.PARTIAL, PlanningStatus.FAILED))
def test_recovery_edge_requires_explicit_retry_trigger(current: PlanningStatus) -> None:
    command = PlanningTransitionCommand(
        current_status=current,
        target_status=PlanningStatus.NORMALIZING,
    )

    with pytest.raises(PlanningTransitionError) as raised:
        PlanningStateMachine.transition(command)

    assert raised.value.code is PlanningTransitionErrorCode.RETRY_REQUIRED


@pytest.mark.parametrize("current", (PlanningStatus.PARTIAL, PlanningStatus.FAILED))
def test_recovery_edge_requires_retryable_job(current: PlanningStatus) -> None:
    command = PlanningTransitionCommand(
        current_status=current,
        target_status=PlanningStatus.NORMALIZING,
        trigger=PlanningTransitionTrigger.RETRY,
        retryable=False,
    )

    with pytest.raises(PlanningTransitionError) as raised:
        PlanningStateMachine.transition(command)

    assert raised.value.code is PlanningTransitionErrorCode.RETRY_NOT_ALLOWED


def test_retry_trigger_cannot_be_used_for_normal_progression() -> None:
    command = PlanningTransitionCommand(
        current_status=PlanningStatus.DRAFT,
        target_status=PlanningStatus.NORMALIZING,
        trigger=PlanningTransitionTrigger.RETRY,
        retryable=True,
    )

    with pytest.raises(PlanningTransitionError) as raised:
        PlanningStateMachine.transition(command)

    assert raised.value.code is PlanningTransitionErrorCode.RETRY_NOT_ALLOWED


@pytest.mark.parametrize(
    "terminal",
    (PlanningStatus.NEEDS_INPUT, PlanningStatus.READY, PlanningStatus.CONFLICT),
)
def test_non_retryable_terminal_states_have_no_exit(terminal: PlanningStatus) -> None:
    assert ALLOWED_PLANNING_TRANSITIONS[terminal] == frozenset()
    for target in PlanningStatus:
        with pytest.raises(PlanningTransitionError) as raised:
            PlanningStateMachine.transition(
                PlanningTransitionCommand(
                    current_status=terminal,
                    target_status=target,
                    trigger=PlanningTransitionTrigger.RETRY,
                    retryable=True,
                )
            )
        assert raised.value.code is PlanningTransitionErrorCode.TRANSITION_NOT_ALLOWED


@pytest.mark.parametrize(
    ("field", "command", "code"),
    [
        (
            "current_status",
            PlanningTransitionCommand,
            PlanningTransitionErrorCode.STATUS_INVALID,
        ),
        (
            "target_status",
            PlanningTransitionCommand,
            PlanningTransitionErrorCode.STATUS_INVALID,
        ),
        (
            "trigger",
            PlanningTransitionCommand,
            PlanningTransitionErrorCode.TRIGGER_INVALID,
        ),
        (
            "retryable",
            PlanningTransitionCommand,
            PlanningTransitionErrorCode.RETRYABLE_FLAG_INVALID,
        ),
    ],
)
def test_command_rejects_unknown_or_loosely_typed_values(
    field: str,
    command: type[PlanningTransitionCommand],
    code: PlanningTransitionErrorCode,
) -> None:
    values: dict[str, object] = {
        "current_status": PlanningStatus.DRAFT,
        "target_status": PlanningStatus.NORMALIZING,
        "trigger": PlanningTransitionTrigger.ADVANCE,
        "retryable": False,
    }
    values[field] = 1 if field == "retryable" else "invented"

    with pytest.raises(PlanningTransitionError) as raised:
        command(**values)  # type: ignore[arg-type]

    assert raised.value.code is code


def test_command_result_and_error_expose_only_safe_stable_state_details() -> None:
    command = PlanningTransitionCommand(PlanningStatus.READY, PlanningStatus.PLANNING)
    with pytest.raises(PlanningTransitionError) as raised:
        PlanningStateMachine.transition(command)

    assert str(raised.value) == "transition_not_allowed: ready -> planning"
    assert not hasattr(raised.value, "raw_error")
    result = PlanningTransitionResult(
        PlanningStatus.DRAFT,
        PlanningStatus.NORMALIZING,
        PlanningTransitionTrigger.ADVANCE,
    )
    with pytest.raises(FrozenInstanceError):
        result.current_status = PlanningStatus.READY  # type: ignore[misc]


def test_state_machine_depends_only_on_standard_library_and_frozen_contracts() -> None:
    forbidden_modules = {
        "intelligent_travel_assistant.adapters",
        "intelligent_travel_assistant.agent",
        "intelligent_travel_assistant.application.ports",
        "intelligent_travel_assistant.domain.provider_result",
        "fastapi",
        "httpx",
        "openai",
        "os",
        "requests",
        "time",
    }
    observed: list[str] = []
    for path in STATE_MACHINE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                continue
            for module in modules:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in forbidden_modules
                ):
                    observed.append(f"{path.name}:{module}")

    assert observed == []
