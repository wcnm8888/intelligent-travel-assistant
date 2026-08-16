"""Offline application-service tests for F-003 replan orchestration."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.repositories import InMemoryReplanRepository
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationError,
    ReplanApplicationRequest,
    ReplanApplicationService,
    ReplanExecutionResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
    request_fingerprint,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequest, TripPlanResponse
from intelligent_travel_assistant.domain import (
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanChoice,
    ReplanCommand,
    ReplanStatus,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
JOB_ID = UUID("a0000000-0000-4000-8000-000000000001")
TRACE_ID = UUID("b0000000-0000-4000-8000-000000000001")
REPLAN_REQUEST_ID = UUID("d0000000-0000-4000-8000-000000000001")
REPLAN_ID = UUID("d0000000-0000-4000-8000-000000000002")
REPLAN_TRACE_ID = UUID("d0000000-0000-4000-8000-000000000003")
DECISION_ID = UUID("d0000000-0000-4000-8000-000000000004")
RESULT_PLAN_ID = UUID("d0000000-0000-4000-8000-000000000005")
ACTIVITY_ID = UUID("91000000-0000-4000-8000-000000000001")


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _result(name: str = "ready", *, plan_id: UUID | None = None) -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / f"synthetic_hangzhou_{name}.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    plan = response.plan
    assert plan is not None
    if plan_id is not None:
        plan = plan.model_copy(update={"plan_id": plan_id})
    return PlanningJobResult(
        status=response.status,
        resolved_destination=response.resolved_destination,
        plan=plan,
        violations=response.violations,
        warnings=response.warnings,
        uncertainties=response.uncertainties,
        sources=response.sources,
        errors=response.errors,
        retryable=response.retryable,
    )


def _job() -> PlanningJob:
    request = _request()
    result = _result()
    return PlanningJob(
        job_id=JOB_ID,
        trace_id=TRACE_ID,
        client_request_id=request.client_request_id,
        request_fingerprint=request_fingerprint(request),
        request=request,
        status=PlanningStatus.READY,
        attempt=1,
        version=5,
        retryable=False,
        created_at=response_time(),
        updated_at=response_time(),
        result=result,
    )


def response_time() -> datetime:
    return TripPlanResponse.model_validate(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
    ).created_at


def _impact(disposition: ImpactDisposition) -> ImpactAnalysis:
    category = (
        ImpactCategory.SAME_DAY_LOW
        if disposition is ImpactDisposition.AUTO
        else ImpactCategory.SOURCE_REFRESH
    )
    return ImpactAnalysis(
        categories=(category,),
        disposition=disposition,
        direct_refs=(ACTIVITY_ID,),
        transitive_refs=(),
        affected_dates=(),
        route_refs=(),
        source_actions=(),
        required_validations=("schedule",),
        confirmation_required=disposition is ImpactDisposition.CONFIRM,
    )


def _commit() -> ReplanCommit:
    baseline = _result().plan
    assert baseline is not None
    return ReplanCommit(
        result=_result(plan_id=RESULT_PLAN_ID),
        change_set=PlanChangeSet(
            baseline_plan_id=baseline.plan_id,
            result_plan_id=RESULT_PLAN_ID,
            added_refs=(),
            removed_refs=(),
            changed_refs=(),
            added_origins=(),
            change_codes=(),
        ),
    )


@dataclass
class StubPlanningJobs:
    job: PlanningJob

    async def get(self, job_id: UUID) -> PlanningJob:
        assert job_id == self.job.job_id
        return self.job


class StubExecutor:
    def __init__(self, impact: ImpactAnalysis, execution: ReplanExecutionResult) -> None:
        self.impact = impact
        self.execution = execution
        self.analysis_calls = 0
        self.execution_calls = 0

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        self.analysis_calls += 1
        return self.impact

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        return self.execution


class FailingExecutor(StubExecutor):
    def __init__(self, impact: ImpactAnalysis, *, fail_analysis: bool = False) -> None:
        super().__init__(
            impact, ReplanExecutionResult(outcome=ReplanOutcome(ReplanStatus.FAILED, "unused"))
        )
        self.fail_analysis = fail_analysis

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        if self.fail_analysis:
            raise RuntimeError("synthetic analysis failure")
        return await super().analyze(job, command)

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        raise RuntimeError("synthetic execution failure")


class BlockingExecutor(StubExecutor):
    def __init__(self, impact: ImpactAnalysis, execution: ReplanExecutionResult) -> None:
        super().__init__(impact, execution)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        self.started.set()
        await self.release.wait()
        return self.execution


class BlockingAnalysisExecutor(StubExecutor):
    def __init__(self, impact: ImpactAnalysis) -> None:
        super().__init__(impact, ReplanExecutionResult(commit=_commit()))
        self.started = asyncio.Event()

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        self.started.set()
        await asyncio.Event().wait()
        return self.impact


def _service(
    impact: ImpactAnalysis,
    execution: ReplanExecutionResult,
    *,
    job: PlanningJob | None = None,
) -> tuple[ReplanApplicationService, StubExecutor]:
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    executor = StubExecutor(impact, execution)
    service = ReplanApplicationService(
        cast(PlanningJobRepository, StubPlanningJobs(job or _job())),
        InMemoryReplanRepository(id_factory=identifiers.__next__),
        executor,
    )
    return service, executor


def _application_request() -> ReplanApplicationRequest:
    plan = _result().plan
    assert plan is not None
    return ReplanApplicationRequest(
        JOB_ID,
        REPLAN_REQUEST_ID,
        plan.plan_id,
        DeleteActivity(ACTIVITY_ID, reason_code="user_requested"),
    )


def test_auto_replan_analyzes_executes_and_commits_once() -> None:
    service, executor = _service(
        _impact(ImpactDisposition.AUTO), ReplanExecutionResult(commit=_commit())
    )

    result = asyncio.run(service.create(_application_request()))
    repeated = asyncio.run(service.create(_application_request()))

    assert result.replan.status is ReplanStatus.COMPLETED
    assert result.commit is not None and result.commit.plan_version == 2
    assert repeated.replan == result.replan
    assert executor.analysis_calls == 1
    assert executor.execution_calls == 1


def test_concurrent_execute_calls_invoke_executor_once() -> None:
    async def scenario() -> tuple[ReplanStatus, ReplanStatus, int]:
        identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
        executor = BlockingExecutor(
            _impact(ImpactDisposition.AUTO), ReplanExecutionResult(commit=_commit())
        )
        service = ReplanApplicationService(
            cast(PlanningJobRepository, StubPlanningJobs(_job())),
            InMemoryReplanRepository(id_factory=identifiers.__next__),
            executor,
        )
        pending = await service.create(_application_request(), defer_execution=True)
        first = asyncio.create_task(service.execute(JOB_ID, pending.replan.replan_id))
        await executor.started.wait()
        second = asyncio.create_task(service.execute(JOB_ID, pending.replan.replan_id))
        executor.release.set()
        first_result, second_result = await asyncio.gather(first, second)
        return first_result.replan.status, second_result.replan.status, executor.execution_calls

    assert asyncio.run(scenario()) == (ReplanStatus.COMPLETED, ReplanStatus.COMPLETED, 1)


def test_cancelled_execution_is_persisted_as_failed() -> None:
    async def scenario() -> tuple[ReplanStatus, str | None]:
        identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
        repository = InMemoryReplanRepository(id_factory=identifiers.__next__)
        executor = BlockingExecutor(
            _impact(ImpactDisposition.AUTO), ReplanExecutionResult(commit=_commit())
        )
        service = ReplanApplicationService(
            cast(PlanningJobRepository, StubPlanningJobs(_job())), repository, executor
        )
        pending = await service.create(_application_request(), defer_execution=True)
        task = asyncio.create_task(service.execute(JOB_ID, pending.replan.replan_id))
        await executor.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        restored = await repository.get(JOB_ID, pending.replan.replan_id)
        return restored.status, restored.error_code

    assert asyncio.run(scenario()) == (
        ReplanStatus.FAILED,
        "replan_execution_cancelled",
    )


def test_cancelled_analysis_is_persisted_as_failed() -> None:
    async def scenario() -> tuple[ReplanStatus, str | None]:
        identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID))
        repository = InMemoryReplanRepository(id_factory=identifiers.__next__)
        executor = BlockingAnalysisExecutor(_impact(ImpactDisposition.AUTO))
        service = ReplanApplicationService(
            cast(PlanningJobRepository, StubPlanningJobs(_job())), repository, executor
        )
        task = asyncio.create_task(service.create(_application_request()))
        await executor.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        restored = await repository.get(JOB_ID, REPLAN_ID)
        return restored.status, restored.error_code

    assert asyncio.run(scenario()) == (
        ReplanStatus.FAILED,
        "replan_analysis_cancelled",
    )


def test_analysis_and_execution_exceptions_are_persisted_as_safe_failures() -> None:
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID))
    analysis_executor = FailingExecutor(_impact(ImpactDisposition.AUTO), fail_analysis=True)
    analysis_service = ReplanApplicationService(
        cast(PlanningJobRepository, StubPlanningJobs(_job())),
        InMemoryReplanRepository(id_factory=identifiers.__next__),
        analysis_executor,
    )
    analyzed = asyncio.run(analysis_service.create(_application_request()))
    assert analyzed.replan.status is ReplanStatus.FAILED
    assert analyzed.replan.error_code == "replan_analysis_failed"

    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    execution_executor = FailingExecutor(_impact(ImpactDisposition.AUTO))
    execution_service = ReplanApplicationService(
        cast(PlanningJobRepository, StubPlanningJobs(_job())),
        InMemoryReplanRepository(id_factory=identifiers.__next__),
        execution_executor,
    )
    executed = asyncio.run(execution_service.create(_application_request()))
    assert executed.replan.status is ReplanStatus.FAILED
    assert executed.replan.error_code == "replan_execution_failed"


def test_ready_commit_rejects_preserved_unknown_budget() -> None:
    partial = _result("partial", plan_id=RESULT_PLAN_ID)
    assert partial.plan is not None and partial.plan.budget_summary.unknown_count > 0
    promoted = PlanningJobResult(
        status=PlanningStatus.READY,
        resolved_destination=partial.resolved_destination,
        plan=partial.plan,
        violations=(),
        warnings=partial.warnings,
        uncertainties=partial.uncertainties,
        sources=partial.sources,
        errors=(),
        retryable=False,
    )

    with pytest.raises(ValueError, match="replan_ready_unknown_budget_invalid"):
        ReplanCommit(
            result=promoted,
            change_set=PlanChangeSet(
                baseline_plan_id=_result().plan.plan_id,  # type: ignore[union-attr]
                result_plan_id=RESULT_PLAN_ID,
                added_refs=(),
                removed_refs=(),
                changed_refs=(),
                added_origins=(),
                change_codes=(),
            ),
        )


def test_confirmation_does_not_execute_until_approved() -> None:
    service, executor = _service(
        _impact(ImpactDisposition.CONFIRM), ReplanExecutionResult(commit=_commit())
    )

    pending = asyncio.run(service.create(_application_request()))
    assert pending.replan.status is ReplanStatus.AWAITING_CONFIRMATION
    assert executor.execution_calls == 0

    approved = asyncio.run(
        service.decide(
            JOB_ID,
            pending.replan.replan_id,
            ReplanChoice.APPROVE,
            expected_replan_version=pending.replan.aggregate_version,
        )
    )
    assert approved.replan.status is ReplanStatus.COMPLETED
    assert executor.execution_calls == 1


def test_stale_confirmation_conflicts_before_execution() -> None:
    planning_jobs = StubPlanningJobs(_job())
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    replans = InMemoryReplanRepository(id_factory=identifiers.__next__)
    executor = StubExecutor(
        _impact(ImpactDisposition.CONFIRM), ReplanExecutionResult(commit=_commit())
    )
    service = ReplanApplicationService(
        cast(PlanningJobRepository, planning_jobs), replans, executor
    )
    pending = asyncio.run(service.create(_application_request()))
    planning_jobs.job = replace(planning_jobs.job, version=planning_jobs.job.version + 1)
    replans._job_versions[JOB_ID] = planning_jobs.job.version

    with pytest.raises(ReplanRepositoryError) as error:
        asyncio.run(
            service.decide(
                JOB_ID,
                pending.replan.replan_id,
                ReplanChoice.APPROVE,
                expected_replan_version=pending.replan.aggregate_version,
            )
        )

    assert error.value.code is ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT
    assert executor.execution_calls == 0
    assert asyncio.run(replans.get(JOB_ID, pending.replan.replan_id)).status is (
        ReplanStatus.AWAITING_CONFIRMATION
    )


def test_stale_auto_replan_is_persisted_as_conflict_without_execution() -> None:
    planning_jobs = StubPlanningJobs(_job())
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    replans = InMemoryReplanRepository(id_factory=identifiers.__next__)
    executor = StubExecutor(
        _impact(ImpactDisposition.AUTO), ReplanExecutionResult(commit=_commit())
    )
    service = ReplanApplicationService(
        cast(PlanningJobRepository, planning_jobs), replans, executor
    )
    pending = asyncio.run(service.create(_application_request(), defer_execution=True))
    planning_jobs.job = replace(planning_jobs.job, version=planning_jobs.job.version + 1)
    replans._job_versions[JOB_ID] = planning_jobs.job.version

    result = asyncio.run(service.execute(JOB_ID, pending.replan.replan_id))

    assert result.replan.status is ReplanStatus.CONFLICT
    assert result.replan.error_code == ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT.value
    assert executor.execution_calls == 0


def test_cancel_and_safe_failed_outcome_preserve_current_plan() -> None:
    service, executor = _service(
        _impact(ImpactDisposition.CONFIRM),
        ReplanExecutionResult(outcome=ReplanOutcome(ReplanStatus.FAILED, "offline_failed")),
    )
    pending = asyncio.run(service.create(_application_request()))
    cancelled = asyncio.run(
        service.decide(
            JOB_ID,
            pending.replan.replan_id,
            ReplanChoice.CANCEL,
            expected_replan_version=pending.replan.aggregate_version,
        )
    )
    assert cancelled.replan.status is ReplanStatus.CANCELLED
    assert cancelled.commit is None
    assert executor.execution_calls == 0

    failed_service, _ = _service(
        _impact(ImpactDisposition.AUTO),
        ReplanExecutionResult(outcome=ReplanOutcome(ReplanStatus.FAILED, "offline_failed")),
    )
    failed = asyncio.run(failed_service.create(_application_request()))
    assert failed.replan.status is ReplanStatus.FAILED
    assert failed.replan.error_code == "offline_failed"
    assert failed.commit is None


def test_only_ready_or_executable_partial_can_be_replanned() -> None:
    conflict = _result("conflict")
    service, _ = _service(
        _impact(ImpactDisposition.AUTO),
        ReplanExecutionResult(commit=_commit()),
        job=replace(
            _job(),
            status=PlanningStatus.CONFLICT,
            retryable=conflict.retryable,
            result=conflict,
        ),
    )

    with pytest.raises(ReplanApplicationError) as error:
        asyncio.run(service.create(_application_request()))
    assert str(error.value) == "replan_not_allowed"


def test_partial_baseline_and_unknown_amount_are_not_promoted_or_zero_filled() -> None:
    partial = _result("partial")
    assert partial.plan is not None
    unknown_before = tuple(
        item.amount for item in partial.plan.budget_summary.cost_items if item.amount is None
    )
    partial_job = replace(
        _job(),
        status=PlanningStatus.PARTIAL,
        retryable=partial.retryable,
        result=partial,
    )
    service, _ = _service(
        _impact(ImpactDisposition.AUTO),
        ReplanExecutionResult(outcome=ReplanOutcome(ReplanStatus.FAILED, "offline_failed")),
        job=partial_job,
    )
    application_request = replace(_application_request(), baseline_plan_id=partial.plan.plan_id)

    result = asyncio.run(service.create(application_request))

    assert result.replan.status is ReplanStatus.FAILED
    assert partial_job.status is PlanningStatus.PARTIAL
    assert unknown_before and all(value is None for value in unknown_before)
