"""Application-owned planning-job repository port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from intelligent_travel_assistant.application.repositories.models import (
    AcceptanceRecord,
    PlanningJob,
    PlanningJobReservation,
    PlanningResult,
    ReplanCommit,
    ReplanCommitResult,
    ReplanOutcome,
    ReplanRecord,
    ReplanReservation,
)
from intelligent_travel_assistant.contracts import PlanningRequest, PlanningStatus
from intelligent_travel_assistant.domain.replanning import (
    ImpactAnalysis,
    ReplanChoice,
    ReplanCommand,
)


@runtime_checkable
class PlanningJobRepository(Protocol):
    """Atomic persistence boundary used by future HTTP handlers and orchestration."""

    async def get_or_create(self, request: PlanningRequest) -> PlanningJobReservation: ...

    async def get(self, job_id: UUID) -> PlanningJob: ...

    async def advance(
        self,
        job_id: UUID,
        target_status: PlanningStatus,
        *,
        expected_version: int,
        retryable: bool = False,
    ) -> PlanningJob: ...

    async def record_result(
        self,
        job_id: UUID,
        result: PlanningResult,
        *,
        expected_version: int,
    ) -> PlanningJob: ...

    async def retry(self, job_id: UUID, *, expected_version: int) -> PlanningJob: ...

    async def delete(self, job_id: UUID) -> None: ...


@runtime_checkable
class PlanningJobMaintenanceRepository(Protocol):
    """Internal lifecycle operations that are never exposed as bulk public APIs."""

    async def cleanup_expired(self, now: datetime, *, limit: int = 1000) -> int: ...


@runtime_checkable
class AcceptanceRecordRepository(Protocol):
    """Internal typed acceptance evidence writer."""

    async def record_acceptance(self, record: AcceptanceRecord) -> AcceptanceRecord: ...


@runtime_checkable
class ReplanRepository(Protocol):
    """Command-oriented persistence boundary separate from PlanningJobRepository."""

    async def reserve(
        self,
        job_id: UUID,
        replan_request_id: UUID,
        command: ReplanCommand,
        *,
        baseline_plan_id: UUID,
        baseline_plan_version: int | None = None,
        expected_job_version: int,
        trace_id: UUID | None = None,
    ) -> ReplanReservation: ...

    async def get(self, job_id: UUID, replan_id: UUID) -> ReplanRecord: ...

    async def record_analysis(
        self,
        job_id: UUID,
        replan_id: UUID,
        impact: ImpactAnalysis,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord: ...

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord: ...

    async def begin_execution(
        self,
        job_id: UUID,
        replan_id: UUID,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord: ...

    async def record_outcome(
        self,
        job_id: UUID,
        replan_id: UUID,
        outcome: ReplanOutcome,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord: ...

    async def commit(
        self,
        job_id: UUID,
        replan_id: UUID,
        commit: ReplanCommit,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanCommitResult: ...
