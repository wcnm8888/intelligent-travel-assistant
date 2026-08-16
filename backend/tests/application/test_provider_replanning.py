"""Provider-neutral replan execution tests; no adapter or network is used."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast
from uuid import UUID

from intelligent_travel_assistant.adapters.repositories import InMemoryReplanRepository
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanOutcome,
    ReplanRecord,
    request_fingerprint,
)
from intelligent_travel_assistant.application.services import ProviderNeutralReplanExecutor
from intelligent_travel_assistant.application.services.provider_replanning import (
    ReplanBudgetEffectPort,
    ReplanImpactContextPort,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlan,
    TripPlanRequest,
    TripPlanResponse,
)
from intelligent_travel_assistant.domain import (
    ChangeEntityKind,
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanEntitySnapshot,
    ReplanStatus,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
JOB_ID = UUID("e0000000-0000-4000-8000-000000000001")
TRACE_ID = UUID("e0000000-0000-4000-8000-000000000002")
REQUEST_ID = UUID("e0000000-0000-4000-8000-000000000003")
REPLAN_ID = UUID("e0000000-0000-4000-8000-000000000004")
REPLAN_TRACE_ID = UUID("e0000000-0000-4000-8000-000000000005")
DECISION_ID = UUID("e0000000-0000-4000-8000-000000000006")
RESULT_PLAN_ID = UUID("e0000000-0000-4000-8000-000000000007")
ACTIVITY_ID = UUID("91000000-0000-4000-8000-000000000001")
OTHER_ID = UUID("e0000000-0000-4000-8000-000000000099")


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _result(*, plan_id: UUID | None = None) -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    plan = response.plan
    assert plan is not None
    if plan_id is not None:
        plan = plan.model_copy(update={"plan_id": plan_id})
    return PlanningJobResult(
        response.status,
        response.resolved_destination,
        plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
    )


def _job() -> PlanningJob:
    request = _request()
    result = _result()
    generated_at = TripPlanResponse.model_validate(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
    ).created_at
    return PlanningJob(
        JOB_ID,
        TRACE_ID,
        request.client_request_id,
        request_fingerprint(request),
        request,
        PlanningStatus.READY,
        1,
        5,
        False,
        generated_at,
        generated_at,
        result,
    )


def _impact() -> ImpactAnalysis:
    return ImpactAnalysis(
        (ImpactCategory.SAME_DAY_LOW,),
        ImpactDisposition.AUTO,
        (ACTIVITY_ID,),
        (),
        (),
        (),
        (),
        ("schedule",),
        False,
    )


def _replan() -> ReplanRecord:
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    repository = InMemoryReplanRepository(id_factory=identifiers.__next__)
    job = _job()
    assert job.result is not None and job.result.plan is not None
    reserved = asyncio.run(
        repository.reserve(
            job.job_id,
            REQUEST_ID,
            DeleteActivity(ACTIVITY_ID),
            baseline_plan_id=job.result.plan.plan_id,
            expected_job_version=job.version,
        )
    )
    return asyncio.run(
        repository.record_analysis(
            job.job_id,
            reserved.replan.replan_id,
            _impact(),
            expected_replan_version=reserved.replan.aggregate_version,
        )
    )


class NoopContext:
    pass


class NoopBudget:
    pass


class StubPlanner:
    def __init__(self, result: PlanningJobResult | ReplanOutcome) -> None:
        self.result = result
        self.calls = 0

    async def execute(
        self, job: PlanningJob, replan: ReplanRecord
    ) -> PlanningJobResult | ReplanOutcome:
        self.calls += 1
        return self.result


class StubSnapshots:
    def __init__(self, changed_ref: UUID) -> None:
        self.changed_ref = changed_ref

    def project(self, plan: TripPlan) -> tuple[PlanEntitySnapshot, ...]:
        fingerprint = "a" * 64 if plan.plan_id != RESULT_PLAN_ID else "b" * 64
        return (PlanEntitySnapshot(self.changed_ref, ChangeEntityKind.ACTIVITY, fingerprint),)


def _executor(planner: StubPlanner, changed_ref: UUID) -> ProviderNeutralReplanExecutor:
    return ProviderNeutralReplanExecutor(
        cast(ReplanImpactContextPort, NoopContext()),
        cast(ReplanBudgetEffectPort, NoopBudget()),
        planner,
        StubSnapshots(changed_ref),
    )


def test_offline_execution_builds_scoped_change_set() -> None:
    planner = StubPlanner(_result(plan_id=RESULT_PLAN_ID))
    execution = asyncio.run(_executor(planner, ACTIVITY_ID).execute(_job(), _replan()))

    assert execution.commit is not None
    assert execution.outcome is None
    assert execution.commit.change_set.changed_refs == (ACTIVITY_ID,)
    assert planner.calls == 1


def test_out_of_scope_result_fails_closed_as_conflict() -> None:
    planner = StubPlanner(_result(plan_id=RESULT_PLAN_ID))
    execution = asyncio.run(_executor(planner, OTHER_ID).execute(_job(), _replan()))

    assert execution.commit is None
    assert execution.outcome is not None
    assert execution.outcome.status is ReplanStatus.CONFLICT
    assert execution.outcome.error_code == "replan_change_scope_conflict"


def test_planner_safe_outcome_is_forwarded_without_provider_material() -> None:
    expected = ReplanOutcome(ReplanStatus.NEEDS_INPUT, "replacement_input_required")
    planner = StubPlanner(expected)
    execution = asyncio.run(_executor(planner, ACTIVITY_ID).execute(_job(), _replan()))

    assert execution.outcome == expected
    assert execution.commit is None
