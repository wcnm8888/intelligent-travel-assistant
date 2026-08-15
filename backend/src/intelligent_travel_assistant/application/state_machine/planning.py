"""Pure execution guard for the frozen F-001 planning transition graph."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from intelligent_travel_assistant.contracts import (
    ALLOWED_PLANNING_TRANSITIONS,
    PlanningStatus,
)


class PlanningTransitionTrigger(StrEnum):
    ADVANCE = "advance"
    RETRY = "retry"


class PlanningTransitionErrorCode(StrEnum):
    STATUS_INVALID = "status_invalid"
    TRIGGER_INVALID = "trigger_invalid"
    RETRYABLE_FLAG_INVALID = "retryable_flag_invalid"
    TRANSITION_NOT_ALLOWED = "transition_not_allowed"
    RETRY_REQUIRED = "retry_required"
    RETRY_NOT_ALLOWED = "retry_not_allowed"


class PlanningTransitionError(ValueError):
    """Stable error without mutable state or untrusted provider details."""

    __slots__ = ("code", "current_status", "target_status")

    def __init__(
        self,
        code: PlanningTransitionErrorCode,
        *,
        current_status: PlanningStatus | None = None,
        target_status: PlanningStatus | None = None,
    ) -> None:
        self.code = code
        self.current_status = current_status
        self.target_status = target_status
        if current_status is not None and target_status is not None:
            message = f"{code.value}: {current_status.value} -> {target_status.value}"
        else:
            message = code.value
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PlanningTransitionCommand:
    current_status: PlanningStatus
    target_status: PlanningStatus
    trigger: PlanningTransitionTrigger = PlanningTransitionTrigger.ADVANCE
    retryable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.current_status, PlanningStatus):
            raise PlanningTransitionError(PlanningTransitionErrorCode.STATUS_INVALID)
        if not isinstance(self.target_status, PlanningStatus):
            raise PlanningTransitionError(PlanningTransitionErrorCode.STATUS_INVALID)
        if not isinstance(self.trigger, PlanningTransitionTrigger):
            raise PlanningTransitionError(PlanningTransitionErrorCode.TRIGGER_INVALID)
        if type(self.retryable) is not bool:
            raise PlanningTransitionError(PlanningTransitionErrorCode.RETRYABLE_FLAG_INVALID)


@dataclass(frozen=True, slots=True)
class PlanningTransitionResult:
    previous_status: PlanningStatus
    current_status: PlanningStatus
    trigger: PlanningTransitionTrigger


_RETRY_EDGES: Final = frozenset(
    {
        (PlanningStatus.PARTIAL, PlanningStatus.NORMALIZING),
        (PlanningStatus.FAILED, PlanningStatus.NORMALIZING),
    }
)


class PlanningStateMachine:
    """Stateless owner of every F-001 planning status change."""

    @staticmethod
    def transition(command: PlanningTransitionCommand) -> PlanningTransitionResult:
        current = command.current_status
        target = command.target_status
        if target not in ALLOWED_PLANNING_TRANSITIONS[current]:
            raise PlanningTransitionError(
                PlanningTransitionErrorCode.TRANSITION_NOT_ALLOWED,
                current_status=current,
                target_status=target,
            )

        edge = (current, target)
        if edge in _RETRY_EDGES:
            if command.trigger is not PlanningTransitionTrigger.RETRY:
                raise PlanningTransitionError(
                    PlanningTransitionErrorCode.RETRY_REQUIRED,
                    current_status=current,
                    target_status=target,
                )
            if not command.retryable:
                raise PlanningTransitionError(
                    PlanningTransitionErrorCode.RETRY_NOT_ALLOWED,
                    current_status=current,
                    target_status=target,
                )
        elif command.trigger is PlanningTransitionTrigger.RETRY:
            raise PlanningTransitionError(
                PlanningTransitionErrorCode.RETRY_NOT_ALLOWED,
                current_status=current,
                target_status=target,
            )

        return PlanningTransitionResult(
            previous_status=current,
            current_status=target,
            trigger=command.trigger,
        )
