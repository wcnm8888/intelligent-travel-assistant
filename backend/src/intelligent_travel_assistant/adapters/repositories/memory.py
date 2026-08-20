"""Concurrency-safe, process-local planning-job repository."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import NoReturn
from uuid import UUID, uuid4

from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
    ReplanCommit,
    ReplanCommitResult,
    ReplanDecisionRecord,
    ReplanOutcome,
    ReplanRecord,
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
    ReplanReservation,
    RequestFingerprint,
    request_fingerprint,
    result_matches_request,
)
from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
    PlanningTransitionError,
    PlanningTransitionTrigger,
)
from intelligent_travel_assistant.contracts import PlanningRequest, PlanningStatus
from intelligent_travel_assistant.domain.replanning import (
    AdjustActivityTime,
    DeleteActivity,
    ImpactAnalysis,
    ImpactDisposition,
    ReorderActivities,
    ReplaceActivity,
    ReplanChoice,
    ReplanCommand,
    ReplanDecisionStatus,
    ReplanStatus,
)


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

    async def get_or_create(self, request: PlanningRequest) -> PlanningJobReservation:
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


class InMemoryReplanRepository:
    """Process-local contract double with the same aggregate/version semantics as SQLite."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._lock = asyncio.Lock()
        self._records: dict[UUID, ReplanRecord] = {}
        self._by_request: dict[tuple[UUID, UUID], UUID] = {}
        self._job_versions: dict[UUID, int] = {}
        self._used_ids: set[UUID] = set()

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
    ) -> ReplanReservation:
        _require_memory_ids(job_id, replan_request_id, baseline_plan_id)
        _require_memory_command(command)
        if baseline_plan_version is None:
            baseline_plan_version = 1
        if type(baseline_plan_version) is not int or baseline_plan_version < 1:
            _raise_memory(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
        if type(expected_job_version) is not int or expected_job_version < 1:
            _raise_memory(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
        fingerprint = _memory_command_fingerprint(command)
        async with self._lock:
            key = (job_id, replan_request_id)
            existing_id = self._by_request.get(key)
            if existing_id is not None:
                existing = self._records[existing_id]
                if existing.request_fingerprint != fingerprint:
                    _raise_memory(ReplanRepositoryErrorCode.IDEMPOTENCY_CONFLICT)
                if existing.baseline_plan_id != baseline_plan_id:
                    _raise_memory(ReplanRepositoryErrorCode.BASELINE_CONFLICT)
                return ReplanReservation(False, existing)
            current_job_version = self._job_versions.setdefault(job_id, expected_job_version)
            if current_job_version != expected_job_version:
                _raise_memory(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
            now = self._now()
            record = ReplanRecord(
                replan_id=self._next_id(),
                job_id=job_id,
                replan_request_id=replan_request_id,
                request_fingerprint=fingerprint,
                baseline_plan_id=baseline_plan_id,
                baseline_plan_version=baseline_plan_version,
                expected_job_version=expected_job_version,
                trace_id=trace_id or self._next_id(),
                operation=command.operation,
                command=command,
                impact=None,
                status=ReplanStatus.ANALYZING,
                aggregate_version=1,
                decision=None,
                result_plan_version=None,
                result=None,
                change_set=None,
                error_code=None,
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(minutes=15),
                decided_at=None,
            )
            self._records[record.replan_id] = record
            self._by_request[key] = record.replan_id
            return ReplanReservation(True, record)

    async def get(self, job_id: UUID, replan_id: UUID) -> ReplanRecord:
        _require_memory_ids(job_id, replan_id)
        async with self._lock:
            record = self._records.get(replan_id)
            if record is None or record.job_id != job_id:
                _raise_memory(ReplanRepositoryErrorCode.REPLAN_NOT_FOUND)
            return record

    async def record_analysis(
        self,
        job_id: UUID,
        replan_id: UUID,
        impact: ImpactAnalysis,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord:
        if not isinstance(impact, ImpactAnalysis):
            _raise_memory(ReplanRepositoryErrorCode.JSON_INVALID)
        async with self._lock:
            current = self._get(job_id, replan_id)
            self._check_version(current, expected_replan_version)
            if current.status is not ReplanStatus.ANALYZING:
                _raise_memory(ReplanRepositoryErrorCode.INVALID_STATE)
            now = self._now(not_before=current.updated_at)
            decision_status = (
                ReplanDecisionStatus.AUTO_APPROVED
                if impact.disposition is ImpactDisposition.AUTO
                else ReplanDecisionStatus.REJECTED
                if impact.disposition is ImpactDisposition.REJECT
                else ReplanDecisionStatus.PENDING
            )
            decided_at = now if decision_status is not ReplanDecisionStatus.PENDING else None
            decision = ReplanDecisionRecord(
                decision_id=self._next_id(),
                job_id=job_id,
                attempt=1,
                trace_id=current.trace_id,
                baseline_plan_version=current.baseline_plan_version,
                kind="replan",
                status=decision_status,
                command=current.command,
                impact=impact,
                choice=None,
                created_at=now,
                decided_at=decided_at,
            )
            next_status = (
                ReplanStatus.AWAITING_CONFIRMATION
                if impact.disposition is ImpactDisposition.CONFIRM
                else ReplanStatus.REPLANNING
                if impact.disposition is ImpactDisposition.AUTO
                else ReplanStatus.REJECTED
            )
            updated = replace(
                current,
                impact=impact,
                status=next_status,
                aggregate_version=current.aggregate_version + 1,
                decision=decision,
                updated_at=now,
                expires_at=(
                    now + timedelta(minutes=15)
                    if next_status is ReplanStatus.AWAITING_CONFIRMATION
                    else current.expires_at
                ),
                decided_at=decided_at,
            )
            self._records[replan_id] = updated
            return updated

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        if not isinstance(choice, ReplanChoice):
            raise TypeError("replan_choice_invalid")
        async with self._lock:
            current = self._get(job_id, replan_id)
            if current.decision is not None and current.decision.choice is choice:
                return current
            if current.decision is not None and current.decision.choice is not None:
                _raise_memory(ReplanRepositoryErrorCode.DECISION_CONFLICT)
            self._check_version(current, expected_replan_version)
            if current.decision is None:
                _raise_memory(ReplanRepositoryErrorCode.DECISION_CONFLICT)
            if current.status is not ReplanStatus.AWAITING_CONFIRMATION:
                _raise_memory(ReplanRepositoryErrorCode.INVALID_STATE)
            self._check_job_version(current, expected_job_version)
            now = self._now(not_before=current.updated_at)
            if now >= current.expires_at:
                decision = replace(
                    current.decision,
                    status=ReplanDecisionStatus.EXPIRED,
                    decided_at=now,
                )
                expired = replace(
                    current,
                    status=ReplanStatus.EXPIRED,
                    aggregate_version=current.aggregate_version + 1,
                    decision=decision,
                    error_code=ReplanRepositoryErrorCode.CONFIRMATION_EXPIRED.value,
                    updated_at=now,
                    decided_at=now,
                )
                self._records[replan_id] = expired
                return expired
            decision = replace(
                current.decision,
                status=(
                    ReplanDecisionStatus.APPROVED
                    if choice is ReplanChoice.APPROVE
                    else ReplanDecisionStatus.CANCELLED
                ),
                choice=choice,
                decided_at=now,
            )
            updated = replace(
                current,
                status=(
                    ReplanStatus.REPLANNING
                    if choice is ReplanChoice.APPROVE
                    else ReplanStatus.CANCELLED
                ),
                aggregate_version=current.aggregate_version + 1,
                decision=decision,
                updated_at=now,
                decided_at=now,
            )
            self._records[replan_id] = updated
            return updated

    async def begin_execution(
        self,
        job_id: UUID,
        replan_id: UUID,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        async with self._lock:
            current = self._get(job_id, replan_id)
            self._check_version(current, expected_replan_version)
            self._check_job_version(current, expected_job_version)
            if current.status is not ReplanStatus.REPLANNING or current.decision is None:
                _raise_memory(ReplanRepositoryErrorCode.INVALID_STATE)
            if current.decision.status not in {
                ReplanDecisionStatus.AUTO_APPROVED,
                ReplanDecisionStatus.APPROVED,
            }:
                _raise_memory(ReplanRepositoryErrorCode.DECISION_CONFLICT)
            return current

    async def record_outcome(
        self,
        job_id: UUID,
        replan_id: UUID,
        outcome: ReplanOutcome,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord:
        if not isinstance(outcome, ReplanOutcome):
            _raise_memory(ReplanRepositoryErrorCode.OUTCOME_INVALID)
        async with self._lock:
            current = self._get(job_id, replan_id)
            self._check_version(current, expected_replan_version)
            if current.status not in {ReplanStatus.ANALYZING, ReplanStatus.REPLANNING}:
                _raise_memory(ReplanRepositoryErrorCode.INVALID_STATE)
            now = self._now(not_before=current.updated_at)
            updated = replace(
                current,
                status=outcome.status,
                aggregate_version=current.aggregate_version + 1,
                error_code=outcome.error_code,
                updated_at=now,
            )
            self._records[replan_id] = updated
            return updated

    async def commit(
        self,
        job_id: UUID,
        replan_id: UUID,
        commit: ReplanCommit,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanCommitResult:
        if not isinstance(commit, ReplanCommit):
            _raise_memory(ReplanRepositoryErrorCode.COMMIT_INVALID)
        async with self._lock:
            current = self._get(job_id, replan_id)
            self._check_version(current, expected_replan_version)
            self._check_job_version(current, expected_job_version)
            if current.status is not ReplanStatus.REPLANNING:
                _raise_memory(ReplanRepositoryErrorCode.INVALID_STATE)
            if current.decision is None or current.decision.status not in {
                ReplanDecisionStatus.AUTO_APPROVED,
                ReplanDecisionStatus.APPROVED,
            }:
                _raise_memory(ReplanRepositoryErrorCode.DECISION_CONFLICT)
            if commit.change_set.baseline_plan_id != current.baseline_plan_id:
                _raise_memory(ReplanRepositoryErrorCode.BASELINE_CONFLICT)
            now = self._now(not_before=current.updated_at)
            plan_version = current.baseline_plan_version + 1
            updated = replace(
                current,
                status=ReplanStatus.COMPLETED,
                aggregate_version=current.aggregate_version + 1,
                result_plan_version=plan_version,
                result=commit.result,
                change_set=commit.change_set,
                updated_at=now,
            )
            self._records[replan_id] = updated
            self._job_versions[job_id] = expected_job_version + 1
            return ReplanCommitResult(
                replan=updated,
                job_version=expected_job_version + 1,
                plan_version=plan_version,
            )

    def _get(self, job_id: UUID, replan_id: UUID) -> ReplanRecord:
        record = self._records.get(replan_id)
        if record is None or record.job_id != job_id:
            _raise_memory(ReplanRepositoryErrorCode.REPLAN_NOT_FOUND)
        return record

    @staticmethod
    def _check_version(record: ReplanRecord, expected: int) -> None:
        if type(expected) is not int or record.aggregate_version != expected:
            _raise_memory(ReplanRepositoryErrorCode.VERSION_CONFLICT)

    def _check_job_version(self, record: ReplanRecord, expected: int) -> None:
        if (
            type(expected) is not int
            or expected != record.expected_job_version
            or self._job_versions.get(record.job_id) != record.expected_job_version
        ):
            _raise_memory(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)

    def _next_id(self) -> UUID:
        identifier = self._id_factory()
        _require_memory_ids(identifier)
        if identifier in self._used_ids:
            _raise_memory(ReplanRepositoryErrorCode.IDENTIFIER_INVALID)
        self._used_ids.add(identifier)
        return identifier

    def _now(self, *, not_before: datetime | None = None) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            _raise_memory(ReplanRepositoryErrorCode.JSON_INVALID)
        if not_before is not None and now < not_before:
            _raise_memory(ReplanRepositoryErrorCode.JSON_INVALID)
        return now


def _require_memory_ids(*values: UUID) -> None:
    if any(not isinstance(value, UUID) for value in values):
        _raise_memory(ReplanRepositoryErrorCode.IDENTIFIER_INVALID)


def _require_memory_command(command: ReplanCommand) -> None:
    if not isinstance(
        command, (ReplaceActivity, DeleteActivity, AdjustActivityTime, ReorderActivities)
    ):
        _raise_memory(ReplanRepositoryErrorCode.JSON_INVALID)


def _memory_command_fingerprint(command: ReplanCommand) -> RequestFingerprint:
    payload: object
    if isinstance(command, ReplaceActivity):
        payload = (
            command.operation.value,
            str(command.target_activity_id),
            command.replacement_categories,
            command.reason_code,
        )
    elif isinstance(command, DeleteActivity):
        payload = (command.operation.value, str(command.target_activity_id), command.reason_code)
    elif isinstance(command, AdjustActivityTime):
        payload = (
            command.operation.value,
            str(command.target_activity_id),
            command.start_time.isoformat(),
            command.end_time.isoformat(),
            command.reason_code,
        )
    else:
        payload = (
            command.operation.value,
            command.local_date.isoformat(),
            tuple(str(value) for value in command.ordered_activity_ids),
            command.reason_code,
        )
    return RequestFingerprint(
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _raise_memory(code: ReplanRepositoryErrorCode) -> NoReturn:
    raise ReplanRepositoryError(code)
