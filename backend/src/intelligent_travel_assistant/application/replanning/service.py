"""Application orchestration for analysis, confirmation, execution, and commit."""

from __future__ import annotations

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
from intelligent_travel_assistant.contracts import PlanningStatus
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

    async def create(
        self,
        request: ReplanApplicationRequest,
        *,
        defer_execution: bool = False,
    ) -> ReplanApplicationResult:
        if not isinstance(request, ReplanApplicationRequest):
            raise ReplanApplicationError("replan_request_invalid")
        job = await self._planning_jobs.get(request.job_id)
        reservation = await self._replans.reserve(
            request.job_id,
            request.replan_request_id,
            request.command,
            baseline_plan_id=request.baseline_plan_id,
            expected_job_version=job.version,
        )
        if not reservation.created:
            return ReplanApplicationResult(reservation.replan)
        self._require_baseline(job, request.baseline_plan_id)
        impact = await self._executor.analyze(job, request.command)
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
        replan = await self._replans.get(job_id, replan_id)
        return await self._execute(job, replan)

    async def _execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanApplicationResult:
        if not isinstance(replan, ReplanRecord):
            raise ReplanApplicationError("replan_record_invalid")
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
        execution = await self._executor.execute(job, executable)
        if execution.outcome is not None:
            terminal = await self._replans.record_outcome(
                job.job_id,
                executable.replan_id,
                execution.outcome,
                expected_replan_version=executable.aggregate_version,
            )
            return ReplanApplicationResult(terminal)
        if execution.commit is None:
            raise ReplanApplicationError("replan_execution_result_invalid")
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
