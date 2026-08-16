"""Application-owned planning-job repository port."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from intelligent_travel_assistant.application.repositories.models import (
    AcceptanceRecord,
    PlanningJob,
    PlanningJobReservation,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequest


@runtime_checkable
class PlanningJobRepository(Protocol):
    """Atomic persistence boundary used by future HTTP handlers and orchestration."""

    async def get_or_create(self, request: TripPlanRequest) -> PlanningJobReservation: ...

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
        result: PlanningJobResult,
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
