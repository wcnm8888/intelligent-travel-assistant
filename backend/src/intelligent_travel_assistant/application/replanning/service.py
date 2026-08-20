"""Application orchestration for analysis, confirmation, execution, and commit."""

from __future__ import annotations

import asyncio
from uuid import UUID

from intelligent_travel_assistant.application.replanning.models import (
    ReplanApplicationRequest,
    ReplanApplicationResult,
)
from intelligent_travel_assistant.application.replanning.ports import ReplanExecutionPort
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    ReplanOutcome,
    ReplanRecord,
    ReplanRepository,
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequestV2
from intelligent_travel_assistant.domain import ReplanChoice, ReplanStatus


class ReplanApplicationError(ValueError):
    """Stable application error without request or provider material."""


class ReplanApplicationService:
    def __init__(
        self,
        planning_jobs: PlanningJobRepository,
        replans: ReplanRepository,
        executor: ReplanExecutionPort,
    ) -> None:
        self._planning_jobs = planning_jobs
        self._replans = replans
        self._executor = executor
        self._execution_locks: dict[UUID, asyncio.Lock] = {}

    async def create(
        self,
        request: ReplanApplicationRequest,
        *,
        defer_execution: bool = False,
    ) -> ReplanApplicationResult:
        if not isinstance(request, ReplanApplicationRequest):
            raise ReplanApplicationError("replan_request_invalid")
        job = await self._planning_jobs.get(request.job_id)
        self._require_supported_scope(job)
        reservation = await self._replans.reserve(
            request.job_id,
            request.replan_request_id,
            request.command,
            baseline_plan_id=request.baseline_plan_id,
            expected_job_version=job.version,
        )
        if not reservation.created:
            return ReplanApplicationResult(reservation.replan)
        try:
            self._require_baseline(job, request.baseline_plan_id)
        except ReplanApplicationError as error:
            await self._replans.record_outcome(
                job.job_id,
                reservation.replan.replan_id,
                ReplanOutcome(ReplanStatus.CONFLICT, str(error)),
                expected_replan_version=reservation.replan.aggregate_version,
            )
            raise
        try:
            impact = await self._executor.analyze(job, request.command)
        except asyncio.CancelledError:
            await self._replans.record_outcome(
                job.job_id,
                reservation.replan.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_analysis_cancelled"),
                expected_replan_version=reservation.replan.aggregate_version,
            )
            raise
        except Exception:
            failed = await self._replans.record_outcome(
                job.job_id,
                reservation.replan.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_analysis_failed"),
                expected_replan_version=reservation.replan.aggregate_version,
            )
            return ReplanApplicationResult(failed)
        analyzed = await self._replans.record_analysis(
            request.job_id,
            reservation.replan.replan_id,
            impact,
            expected_replan_version=reservation.replan.aggregate_version,
        )
        if analyzed.status is not ReplanStatus.REPLANNING:
            return ReplanApplicationResult(analyzed)
        if defer_execution:
            return ReplanApplicationResult(analyzed)
        return await self._execute(job, analyzed)

    async def get(self, job_id: UUID, replan_id: UUID) -> ReplanApplicationResult:
        if not isinstance(job_id, UUID) or not isinstance(replan_id, UUID):
            raise ReplanApplicationError("replan_identifier_invalid")
        return ReplanApplicationResult(await self._replans.get(job_id, replan_id))

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        defer_execution: bool = False,
    ) -> ReplanApplicationResult:
        if not isinstance(job_id, UUID) or not isinstance(replan_id, UUID):
            raise ReplanApplicationError("replan_identifier_invalid")
        job = await self._planning_jobs.get(job_id)
        self._require_supported_scope(job)
        decided = await self._replans.decide(
            job_id,
            replan_id,
            choice,
            expected_replan_version=expected_replan_version,
            expected_job_version=job.version,
        )
        if decided.status is not ReplanStatus.REPLANNING:
            return ReplanApplicationResult(decided)
        if defer_execution:
            return ReplanApplicationResult(decided)
        return await self._execute(job, decided)

    async def execute(self, job_id: UUID, replan_id: UUID) -> ReplanApplicationResult:
        if not isinstance(job_id, UUID) or not isinstance(replan_id, UUID):
            raise ReplanApplicationError("replan_identifier_invalid")
        job = await self._planning_jobs.get(job_id)
        self._require_supported_scope(job)
        replan = await self._replans.get(job_id, replan_id)
        return await self._execute(job, replan)

    @staticmethod
    def _require_supported_scope(job: PlanningJob) -> None:
        if isinstance(job.request, TripPlanRequestV2) and job.request.day_count > 2:
            raise ReplanApplicationError("replan_scope_not_supported")

    async def _execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanApplicationResult:
        if not isinstance(replan, ReplanRecord):
            raise ReplanApplicationError("replan_record_invalid")
        lock = self._execution_locks.setdefault(replan.replan_id, asyncio.Lock())
        async with lock:
            current_job = await self._planning_jobs.get(job.job_id)
            current = await self._replans.get(job.job_id, replan.replan_id)
            if current.status is not ReplanStatus.REPLANNING:
                return ReplanApplicationResult(current)
            return await self._execute_once(current_job, current)

    async def _execute_once(
        self, job: PlanningJob, replan: ReplanRecord
    ) -> ReplanApplicationResult:
        try:
            executable = await self._replans.begin_execution(
                job.job_id,
                replan.replan_id,
                expected_replan_version=replan.aggregate_version,
                expected_job_version=job.version,
            )
        except ReplanRepositoryError as error:
            if error.code is not ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT:
                raise
            return await self._record_job_version_conflict(replan)
        try:
            execution = await self._executor.execute(job, executable)
        except asyncio.CancelledError:
            await self._replans.record_outcome(
                job.job_id,
                executable.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_execution_cancelled"),
                expected_replan_version=executable.aggregate_version,
            )
            raise
        except Exception:
            terminal = await self._replans.record_outcome(
                job.job_id,
                executable.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_execution_failed"),
                expected_replan_version=executable.aggregate_version,
            )
            return ReplanApplicationResult(terminal)
        if execution.outcome is not None:
            terminal = await self._replans.record_outcome(
                job.job_id,
                executable.replan_id,
                execution.outcome,
                expected_replan_version=executable.aggregate_version,
            )
            return ReplanApplicationResult(terminal)
        if execution.commit is None:
            terminal = await self._replans.record_outcome(
                job.job_id,
                executable.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_execution_result_invalid"),
                expected_replan_version=executable.aggregate_version,
            )
            return ReplanApplicationResult(terminal)
        try:
            committed = await self._replans.commit(
                job.job_id,
                executable.replan_id,
                execution.commit,
                expected_replan_version=executable.aggregate_version,
                expected_job_version=job.version,
            )
        except ReplanRepositoryError as error:
            if error.code is not ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT:
                raise
            return await self._record_job_version_conflict(executable)
        return ReplanApplicationResult(committed.replan, committed)

    async def _record_job_version_conflict(self, replan: ReplanRecord) -> ReplanApplicationResult:
        terminal = await self._replans.record_outcome(
            replan.job_id,
            replan.replan_id,
            ReplanOutcome(
                ReplanStatus.CONFLICT,
                ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT.value,
            ),
            expected_replan_version=replan.aggregate_version,
        )
        return ReplanApplicationResult(terminal)

    @staticmethod
    def _require_baseline(job: PlanningJob, baseline_plan_id: object) -> None:
        if job.status not in {PlanningStatus.READY, PlanningStatus.PARTIAL}:
            raise ReplanApplicationError("replan_not_allowed")
        if job.result is None or job.result.plan is None:
            raise ReplanApplicationError("replan_baseline_missing")
        if job.result.plan.plan_id != baseline_plan_id:
            raise ReplanApplicationError("replan_baseline_conflict")
