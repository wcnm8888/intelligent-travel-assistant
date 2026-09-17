"""Provider-neutral replan execution tests; no adapter or network is used."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

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
    ApiError,
    ApiErrorCode,
    PlanningStatus,
    TripPlan,
    TripPlanRequest,
    TripPlanResponse,
)
from intelligent_travel_assistant.domain import (
    ChangeEntityKind,
    DeleteActivity,
    DomainInvariantError,
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


@pytest.mark.parametrize(
    ("code", "retryable", "expected_status"),
    (
        (ApiErrorCode.PROVIDER_TIMEOUT, True, ReplanStatus.FAILED),
        (ApiErrorCode.PROVIDER_UNAVAILABLE, True, ReplanStatus.FAILED),
        (ApiErrorCode.DATA_MISSING, False, ReplanStatus.NEEDS_INPUT),
        (ApiErrorCode.BUDGET_INCOMPLETE, False, ReplanStatus.NEEDS_INPUT),
        (ApiErrorCode.CONSTRAINT_CONFLICT, False, ReplanStatus.CONFLICT),
        (ApiErrorCode.REPLAN_SCOPE_NOT_SUPPORTED, False, ReplanStatus.REJECTED),
    ),
)
def test_planless_result_preserves_first_safe_error_for_recovery(
    code: ApiErrorCode,
    retryable: bool,
    expected_status: ReplanStatus,
) -> None:
    base = _result()
    planless = PlanningJobResult(
        status=PlanningStatus.FAILED,
        resolved_destination=base.resolved_destination,
        plan=None,
        violations=base.violations,
        warnings=base.warnings,
        uncertainties=base.uncertainties,
        sources=base.sources,
        errors=(ApiError(code=code, message="Safe offline failure.", retryable=retryable),),
        retryable=retryable,
    )

    execution = asyncio.run(
        _executor(StubPlanner(planless), ACTIVITY_ID).execute(_job(), _replan())
    )

    assert execution.commit is None
    assert execution.outcome == ReplanOutcome(expected_status, code.value)


def _typed_executor(*, failure: str | None = None, planless: bool = False) -> tuple[Any, ...]:
    from datetime import time

    from intelligent_travel_assistant.application.services.replan_facts import ReplanFactProjector
    from intelligent_travel_assistant.domain import AdjustActivityTime

    now = datetime.fromisoformat("2026-08-13T10:01:00+08:00")
    job = _job()
    assert isinstance(job.result, PlanningJobResult) and isinstance(job.result.plan, TripPlan)
    plan = job.result.plan
    command = AdjustActivityTime(plan.days[0].activities[0].item_id, time(10, 15), time(12, 15))
    projector = ReplanFactProjector()
    impact = projector.analyze(job, command, evaluated_at=now)
    record = replace(_replan(), command=command, operation=command.operation, impact=impact)
    day = plan.days[0]
    day = day.model_copy(
        update={
            "activities": (
                day.activities[0].model_copy(
                    update={"start_time": command.start_time, "end_time": command.end_time}
                ),
                *day.activities[1:],
            )
        }
    )
    candidate = replace(
        job.result,
        status=PlanningStatus.PARTIAL,
        plan=plan.model_copy(update={"plan_id": RESULT_PLAN_ID, "days": (day, plan.days[1])}),
    )
    if planless:
        candidate = replace(
            candidate,
            status=PlanningStatus.FAILED,
            plan=None,
            errors=(
                ApiError(code=ApiErrorCode.PROVIDER_TIMEOUT, message="synthetic", retryable=True),
            ),
        )
    events: list[tuple[str, datetime]] = []

    class Clock:
        def __call__(self) -> datetime:
            events.append(("clock", now))
            return now

    class SpyFacts:
        def analyze(self, j: Any, c: Any, *, evaluated_at: datetime) -> Any:
            events.append(("analyze", evaluated_at))
            if failure == "analyze":
                raise ValueError("synthetic internal failure")
            return projector.analyze(j, c, evaluated_at=evaluated_at)

        def changes(self, j: Any, c: Any, i: Any, r: Any, *, evaluated_at: datetime) -> Any:
            events.append(("changes", evaluated_at))
            if failure == "changes":
                raise DomainInvariantError("synthetic", field="facts")
            return projector.changes(j, c, i, r, evaluated_at=evaluated_at)

    class ForbiddenLegacy:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError("new facts path accessed legacy port")

    legacy = ForbiddenLegacy()
    executor = ProviderNeutralReplanExecutor(
        legacy, legacy, StubPlanner(candidate), legacy, facts=SpyFacts(), clock=Clock()
    )
    return executor, job, record, events


def test_typed_executor_uses_full_facts_and_one_clock_per_call() -> None:
    import copy

    executor, job, record, events = _typed_executor()
    saved = copy.deepcopy((job, record))
    analysis = asyncio.run(executor.analyze(job, record.command))
    execution = asyncio.run(executor.execute(job, record))
    assert analysis == record.impact
    assert execution.commit is not None and execution.outcome is None
    assert execution.commit.change_set.change_codes == ("schedule",)
    assert [event[0] for event in events] == ["clock", "analyze", "clock", "changes"]
    assert len({event[1] for event in events}) == 1
    assert (job, record) == saved


@pytest.mark.parametrize("failure", ("analyze", "changes"))
def test_new_executor_failure_never_calls_legacy_ports(failure: str) -> None:
    executor, job, record, events = _typed_executor(failure=failure)
    if failure == "analyze":
        with pytest.raises(DomainInvariantError, match="replan_analysis_failed"):
            asyncio.run(executor.analyze(job, record.command))
    else:
        execution = asyncio.run(executor.execute(job, record))
        assert execution.commit is None
        assert execution.outcome == ReplanOutcome(
            ReplanStatus.CONFLICT, "replan_change_scope_conflict"
        )
    assert len([e for e in events if e[0] == "clock"]) == 1


def test_new_executor_planless_keeps_error_without_snapshot_fallback() -> None:
    executor, job, record, events = _typed_executor(planless=True)
    result = asyncio.run(executor.execute(job, record))
    assert result.commit is None
    assert result.outcome == ReplanOutcome(ReplanStatus.FAILED, "provider_timeout")
    assert events == []


@pytest.mark.parametrize("pair", ("facts_only", "clock_only"))
def test_new_executor_requires_explicit_clock_and_projector_pair(pair: str) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import ReplanFactProjector

    with pytest.raises(ValueError, match="replan_fact_clock_pair_required"):
        ProviderNeutralReplanExecutor(
            cast(ReplanImpactContextPort, NoopContext()),
            cast(ReplanBudgetEffectPort, NoopBudget()),
            StubPlanner(_result()),
            StubSnapshots(ACTIVITY_ID),
            facts=ReplanFactProjector() if pair == "facts_only" else None,
            clock=(lambda: datetime.fromisoformat("2026-08-13T10:01:00+08:00"))
            if pair == "clock_only"
            else None,
        )


@pytest.mark.parametrize(
    "fault",
    (
        None,
        "job",
        "replan",
        "baseline",
        "version",
        "candidate",
        "old_seam",
        "facts_only",
        "clock_only",
        "old_facts",
        "body",
        "missing_proof",
        "planless",
        "record_version",
        "record_job",
    ),
)
def test_evidence_executor_binding_and_no_legacy_fallback(fault: str | None) -> None:
    import copy

    from tests.application.test_replan_facts import NOW, PROJECTOR, weather_case

    from intelligent_travel_assistant.application.services.replan_facts import (
        EvidencedReplanResult,
        ReplanEvidence,
    )

    job, command, candidate, impact, event = weather_case()
    record = replace(
        _replan(),
        job_id=job.job_id,
        command=command,
        operation=command.operation,
        impact=impact,
        expected_job_version=job.version,
    )
    proof = ReplanEvidence.bind(job, record.replan_id, command, candidate, (event,))
    if fault in {"job", "replan", "baseline", "version", "candidate"}:
        fields = {
            "job": "job_id",
            "replan": "replan_id",
            "baseline": "baseline_plan_id",
            "version": "job_version",
            "candidate": "candidate_fingerprint",
        }
        changes: dict[str, Any] = {
            fields[fault]: 999
            if fault == "version"
            else "0" * 64
            if fault == "candidate"
            else OTHER_ID
        }
        proof = replace(proof, **changes)
    wrapped = EvidencedReplanResult(candidate, proof)
    if fault in {"body", "missing_proof"}:
        object.__setattr__(wrapped, "result" if fault == "body" else "evidence", None)
    elif fault == "planless":
        object.__setattr__(wrapped.result, "plan", None)
    elif fault == "record_version":
        record = replace(record, expected_job_version=record.expected_job_version + 1)
    elif fault == "record_job":
        record = replace(record, job_id=OTHER_ID)
    saved = copy.deepcopy((job, record, wrapped))
    ticks: list[datetime] = []

    class ForbiddenLegacy:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError("evidence escaped to old seam")

    class Planner:
        async def execute(self, j: Any, r: Any) -> EvidencedReplanResult:
            return wrapped

    def clock() -> datetime:
        ticks.append(NOW)
        return NOW

    legacy = cast(Any, ForbiddenLegacy())

    class OldFacts:
        def changes(self, j: Any, c: Any, i: Any, r: Any, *, evaluated_at: datetime) -> Any:
            raise AssertionError("new evidence cannot use the old facts interface")

    kwargs = {
        "facts": PROJECTOR if fault not in {"old_seam", "clock_only"} else None,
        "clock": clock if fault not in {"old_seam", "facts_only"} else None,
    }
    if fault == "old_facts":
        kwargs["facts"] = cast(Any, OldFacts())
    if fault in {"facts_only", "clock_only"}:
        with pytest.raises(ValueError, match="replan_fact_clock_pair_required"):
            ProviderNeutralReplanExecutor(legacy, legacy, Planner(), legacy, **cast(Any, kwargs))
        return
    executor = ProviderNeutralReplanExecutor(legacy, legacy, Planner(), legacy, **cast(Any, kwargs))
    execution = asyncio.run(executor.execute(job, record))
    if fault is None:
        assert execution.commit is not None and execution.commit.result == candidate
        assert not hasattr(execution.commit, "evidence") and ticks == [NOW]
    else:
        assert execution.commit is None and execution.outcome is not None
        assert execution.outcome.status is ReplanStatus.CONFLICT
    assert (job, record, wrapped) == saved
