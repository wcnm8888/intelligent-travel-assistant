"""Typed application values for local replanning orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from intelligent_travel_assistant.application.repositories import (
    ReplanCommit,
    ReplanCommitResult,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.domain import ReplanCommand


@dataclass(frozen=True, slots=True)
class ReplanApplicationRequest:
    job_id: UUID
    replan_request_id: UUID
    baseline_plan_id: UUID
    command: ReplanCommand

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, UUID)
            for value in (self.job_id, self.replan_request_id, self.baseline_plan_id)
        ):
            raise ValueError("replan_application_identifier_invalid")


@dataclass(frozen=True, slots=True)
class ReplanExecutionResult:
    commit: ReplanCommit | None = None
    outcome: ReplanOutcome | None = None

    def __post_init__(self) -> None:
        if (self.commit is None) == (self.outcome is None):
            raise ValueError("replan_execution_result_invalid")


@dataclass(frozen=True, slots=True)
class ReplanApplicationResult:
    replan: ReplanRecord
    commit: ReplanCommitResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.replan, ReplanRecord):
            raise ValueError("replan_application_result_invalid")
        if self.commit is not None and self.commit.replan != self.replan:
            raise ValueError("replan_application_commit_mismatch")
