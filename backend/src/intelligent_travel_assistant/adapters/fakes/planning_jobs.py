"""Synthetic planning-job execution for offline browser verification only."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType
from uuid import UUID

from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import PlanningStatus

_FULL_VALIDATION_PATH = (
    PlanningStatus.NORMALIZING,
    PlanningStatus.COLLECTING,
    PlanningStatus.PLANNING,
    PlanningStatus.ENRICHING_ROUTES,
    PlanningStatus.VALIDATING,
)
_PATHS_BY_TERMINAL = {
    PlanningStatus.READY: _FULL_VALIDATION_PATH,
    PlanningStatus.PARTIAL: _FULL_VALIDATION_PATH,
    PlanningStatus.CONFLICT: _FULL_VALIDATION_PATH,
    PlanningStatus.NEEDS_INPUT: (PlanningStatus.NORMALIZING,),
    PlanningStatus.FAILED: (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
    ),
}


class SyntheticPlanningJobExecutor:
    """Publish one frozen, clearly synthetic terminal result through the real repository."""

    __slots__ = ("_histories", "_repository", "_result", "_wait_between_states")

    def __init__(
        self,
        repository: PlanningJobRepository,
        result: PlanningJobResult,
        *,
        wait_between_states: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if not isinstance(result, PlanningJobResult):
            raise TypeError("synthetic_result_invalid")
        self._repository = repository
        self._result = result
        self._wait_between_states = wait_between_states
        self._histories: dict[UUID, tuple[PlanningStatus, ...]] = {}

    @property
    def histories(self) -> Mapping[UUID, tuple[PlanningStatus, ...]]:
        return MappingProxyType(self._histories.copy())

    async def execute(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        history = [job.status]
        path = _PATHS_BY_TERMINAL[self._result.status]
        try:
            start = path.index(job.status) + 1
        except ValueError:
            if job.status is not PlanningStatus.DRAFT:
                raise RuntimeError("synthetic_job_state_invalid") from None
            start = 0

        for target in path[start:]:
            job = await self._repository.advance(
                job_id,
                target,
                expected_version=job.version,
            )
            history.append(job.status)
            if self._wait_between_states is not None:
                await self._wait_between_states()
        job = await self._repository.record_result(
            job_id,
            self._result,
            expected_version=job.version,
        )
        history.append(job.status)
        self._histories[job_id] = tuple(history)
