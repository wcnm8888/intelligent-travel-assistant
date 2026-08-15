"""Narrow application boundary for asynchronously executing one planning job."""

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class PlanningJobExecutor(Protocol):
    """Execute an already reserved job without exposing providers to HTTP."""

    async def execute(self, job_id: UUID) -> None: ...
