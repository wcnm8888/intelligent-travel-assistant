"""Concurrency-safe, process-local planning-job repository."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID, uuid4

from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
    request_fingerprint,
    result_matches_request,
)
from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
    PlanningTransitionError,
    PlanningTransitionTrigger,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequest


class InMemoryPlanningJobRepository:
    """Atomic within one event loop and intentionally non-durable across restarts."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._lock = asyncio.Lock()
        self._jobs: dict[UUID, PlanningJob] = {}
        self._job_id_by_client_request_id: dict[UUID, UUID] = {}
        self._used_ids: set[UUID] = set()

    async def get_or_create(self, request: TripPlanRequest) -> PlanningJobReservation:
        fingerprint = request_fingerprint(request)
        async with self._lock:
            existing_job_id = self._job_id_by_client_request_id.get(request.client_request_id)
            if existing_job_id is not None:
                existing = self._jobs[existing_job_id]
                if existing.request_fingerprint != fingerprint:
                    self._raise(PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT)
                return PlanningJobReservation(created=False, job=existing)

            created_at = self._now()
            job = PlanningJob(
                job_id=self._next_id(),
                trace_id=self._next_id(),
                client_request_id=request.client_request_id,
                request_fingerprint=fingerprint,
                request=request,
                status=PlanningStatus.DRAFT,
                attempt=1,
                version=1,
                retryable=False,
                created_at=created_at,
                updated_at=created_at,
            )
            self._jobs[job.job_id] = job
            self._job_id_by_client_request_id[job.client_request_id] = job.job_id
            return PlanningJobReservation(created=True, job=job)

    async def get(self, job_id: UUID) -> PlanningJob:
        async with self._lock:
            return self._get(job_id)

    async def advance(
        self,
        job_id: UUID,
        target_status: PlanningStatus,
        *,
        expected_version: int,
        retryable: bool = False,
    ) -> PlanningJob:
        async with self._lock:
            current = self._get(job_id)
            self._require_version(current, expected_version)
            if type(retryable) is not bool or (
                retryable and target_status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}
            ):
                self._raise(PlanningJobRepositoryErrorCode.RETRYABLE_FLAG_INVALID)
            try:
                transition = PlanningStateMachine.transition(
                    PlanningTransitionCommand(
                        current_status=current.status,
                        target_status=target_status,
                    )
                )
            except PlanningTransitionError:
                self._raise(PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED)
            if transition.current_status in {
                PlanningStatus.READY,
                PlanningStatus.PARTIAL,
                PlanningStatus.CONFLICT,
                PlanningStatus.NEEDS_INPUT,
                PlanningStatus.FAILED,
            }:
                self._raise(PlanningJobRepositoryErrorCode.RESULT_REQUIRED)

            updated = replace(
                current,
                status=transition.current_status,
                retryable=retryable,
                version=current.version + 1,
                updated_at=self._now(not_before=current.updated_at),
            )
            self._jobs[job_id] = updated
            return updated

    async def record_result(
        self,
        job_id: UUID,
        result: PlanningJobResult,
        *,
        expected_version: int,
    ) -> PlanningJob:
        async with self._lock:
            current = self._get(job_id)
            self._require_version(current, expected_version)
            if not isinstance(result, PlanningJobResult):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
            if not result_matches_request(result, current.request):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH)
            try:
                transition = PlanningStateMachine.transition(
                    PlanningTransitionCommand(
                        current_status=current.status,
                        target_status=result.status,
                    )
                )
            except PlanningTransitionError:
                self._raise(PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED)

            updated = replace(
                current,
                status=transition.current_status,
                retryable=result.retryable,
                result=result,
                version=current.version + 1,
                updated_at=self._now(not_before=current.updated_at),
            )
            self._jobs[job_id] = updated
            return updated

    async def retry(self, job_id: UUID, *, expected_version: int) -> PlanningJob:
        async with self._lock:
            current = self._get(job_id)
            self._require_version(current, expected_version)
            if current.attempt >= 3:
                self._raise(PlanningJobRepositoryErrorCode.RETRY_LIMIT_REACHED)
            retryable_status = current.status in {
                PlanningStatus.PARTIAL,
                PlanningStatus.FAILED,
            }
            if not retryable_status or not current.retryable:
                self._raise(PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED)
            try:
                transition = PlanningStateMachine.transition(
                    PlanningTransitionCommand(
                        current_status=current.status,
                        target_status=PlanningStatus.NORMALIZING,
                        trigger=PlanningTransitionTrigger.RETRY,
                        retryable=True,
                    )
                )
            except PlanningTransitionError:
                self._raise(PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED)

            updated = replace(
                current,
                trace_id=self._next_id(),
                status=transition.current_status,
                attempt=current.attempt + 1,
                version=current.version + 1,
                retryable=False,
                result=None,
                updated_at=self._now(not_before=current.updated_at),
            )
            self._jobs[job_id] = updated
            return updated

    async def delete(self, job_id: UUID) -> None:
        """Delete exactly one in-memory job for HTTP contract parity."""

        async with self._lock:
            job = self._get(job_id)
            del self._jobs[job.job_id]
            del self._job_id_by_client_request_id[job.client_request_id]

    def _get(self, job_id: UUID) -> PlanningJob:
        if not isinstance(job_id, UUID):
            self._raise(PlanningJobRepositoryErrorCode.JOB_NOT_FOUND)
        try:
            return self._jobs[job_id]
        except KeyError:
            self._raise(PlanningJobRepositoryErrorCode.JOB_NOT_FOUND)

    def _require_version(self, job: PlanningJob, expected_version: int) -> None:
        if type(expected_version) is not int or expected_version != job.version:
            self._raise(PlanningJobRepositoryErrorCode.VERSION_CONFLICT)

    def _next_id(self) -> UUID:
        identifier = self._id_factory()
        if not isinstance(identifier, UUID):
            self._raise(PlanningJobRepositoryErrorCode.IDENTIFIER_INVALID)
        if identifier in self._used_ids:
            self._raise(PlanningJobRepositoryErrorCode.IDENTIFIER_COLLISION)
        self._used_ids.add(identifier)
        return identifier

    def _now(self, *, not_before: datetime | None = None) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            self._raise(PlanningJobRepositoryErrorCode.CLOCK_INVALID)
        if not_before is not None and value < not_before:
            self._raise(PlanningJobRepositoryErrorCode.CLOCK_INVALID)
        return value

    @staticmethod
    def _raise(code: PlanningJobRepositoryErrorCode) -> NoReturn:
        raise PlanningJobRepositoryError(code)
