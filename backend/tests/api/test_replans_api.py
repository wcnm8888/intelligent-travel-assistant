"""Offline HTTP contract tests for F-003 replan resources."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
    InMemoryReplanRepository,
)
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationService,
    ReplanExecutionResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequest, TripPlanResponse
from intelligent_travel_assistant.domain import (
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanCommand,
    ReplanStatus,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
JOB_ID = UUID("f0000000-0000-4000-8000-000000000001")
JOB_TRACE_ID = UUID("f0000000-0000-4000-8000-000000000002")
REPLAN_ID = UUID("f0000000-0000-4000-8000-000000000003")
REPLAN_TRACE_ID = UUID("f0000000-0000-4000-8000-000000000004")
DECISION_ID = UUID("f0000000-0000-4000-8000-000000000005")
REPLAN_REQUEST_ID = UUID("f0000000-0000-4000-8000-000000000006")
RESULT_PLAN_ID = UUID("f0000000-0000-4000-8000-000000000007")
NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)


class ManualClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _ready_result() -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    return PlanningJobResult(
        response.status,
        response.resolved_destination,
        response.plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
    )


async def _ready_repository() -> tuple[InMemoryPlanningJobRepository, PlanningJob]:
    identifiers = iter((JOB_ID, JOB_TRACE_ID))
    repository = InMemoryPlanningJobRepository(id_factory=identifiers.__next__)
    job = (await repository.get_or_create(_request())).job
    for target in (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.VALIDATING,
    ):
        job = await repository.advance(job.job_id, target, expected_version=job.version)
    job = await repository.record_result(job.job_id, _ready_result(), expected_version=job.version)
    return repository, job


class ConfirmingExecutor:
    def __init__(self) -> None:
        self.execution_calls = 0

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        target = command.target_activity_id  # type: ignore[union-attr]
        return ImpactAnalysis(
            (ImpactCategory.SOURCE_REFRESH,),
            ImpactDisposition.CONFIRM,
            (target,),
            (),
            (),
            (),
            (),
            ("schedule",),
            True,
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        return ReplanExecutionResult(
            outcome=ReplanOutcome(ReplanStatus.FAILED, "offline_execution_failed")
        )


class CommittingExecutor(ConfirmingExecutor):
    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        target = command.target_activity_id  # type: ignore[union-attr]
        return ImpactAnalysis(
            (ImpactCategory.SAME_DAY_LOW,),
            ImpactDisposition.AUTO,
            (target,),
            (),
            (),
            (),
            (),
            ("schedule",),
            False,
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        assert job.result is not None and job.result.plan is not None
        result = _ready_result()
        assert result.plan is not None
        changed = PlanningJobResult(
            result.status,
            result.resolved_destination,
            result.plan.model_copy(update={"plan_id": RESULT_PLAN_ID}),
            result.violations,
            result.warnings,
            result.uncertainties,
            result.sources,
            result.errors,
            result.retryable,
        )
        return ReplanExecutionResult(
            commit=ReplanCommit(
                changed,
                PlanChangeSet(
                    job.result.plan.plan_id,
                    RESULT_PLAN_ID,
                    (),
                    (),
                    (),
                    (),
                    (),
                ),
            )
        )


class RejectingExecutor(ConfirmingExecutor):
    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        target = command.target_activity_id  # type: ignore[union-attr]
        return ImpactAnalysis(
            (ImpactCategory.CROSS_CITY,),
            ImpactDisposition.REJECT,
            (target,),
            (),
            (),
            (),
            (),
            ("constraints",),
            False,
        )


def _client(
    executor: ConfirmingExecutor | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
) -> tuple[TestClient, PlanningJob, ConfirmingExecutor]:
    planning, job = asyncio.run(_ready_repository())
    identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID, DECISION_ID))
    replans = InMemoryReplanRepository(clock=clock, id_factory=identifiers.__next__)
    selected_executor = executor or ConfirmingExecutor()
    service = ReplanApplicationService(planning, replans, selected_executor)
    return (
        TestClient(
            create_app(
                planning_job_repository=planning,
                replan_application_service=service,
            )
        ),
        job,
        selected_executor,
    )


def _payload(job: PlanningJob) -> dict[str, object]:
    assert job.result is not None and job.result.plan is not None
    activity_id = job.result.plan.days[0].activities[0].item_id
    return {
        "replan_request_id": str(REPLAN_REQUEST_ID),
        "baseline_plan_id": str(job.result.plan.plan_id),
        "command": {
            "operation": "adjust_activity_time",
            "target_activity_id": str(activity_id),
            "start_time": "10:30:00",
            "end_time": "12:30:00",
            "reason_code": "user_schedule_preference",
        },
    }


def test_create_and_get_replan_return_exact_awaiting_confirmation_shape() -> None:
    client, job, executor = _client()
    with client:
        created = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        restored = client.get(f"/api/trip-plans/{job.job_id}/replans/{REPLAN_ID}")

    assert created.status_code == 202
    assert created.headers["location"].endswith(f"/replans/{REPLAN_ID}")
    body = created.json()
    assert set(body) == {
        "job_id",
        "replan_id",
        "replan_request_id",
        "trace_id",
        "baseline_plan_id",
        "operation",
        "status",
        "impact",
        "confirmation_expires_at",
        "decision",
        "result",
        "change_set",
        "errors",
        "created_at",
        "updated_at",
    }
    assert body["status"] == "awaiting_confirmation"
    assert body["impact"]["budget_effect"] is None
    assert body["decision"]["choice"] is None
    assert body["result"] is None and body["change_set"] is None
    assert restored.status_code == 200 and restored.json() == body
    assert executor.execution_calls == 0


def test_cancel_is_200_idempotent_and_opposite_decision_conflicts() -> None:
    client, job, _ = _client()
    with client:
        created = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        url = f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}/decision"
        cancelled = client.post(url, json={"choice": "cancel"})
        repeated = client.post(url, json={"choice": "cancel"})
        opposite = client.post(url, json={"choice": "approve"})

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert repeated.status_code == 200 and repeated.json() == cancelled.json()
    assert opposite.status_code == 409
    assert opposite.json()["error"]["code"] == "confirmation_conflict"


def test_approve_returns_202_snapshot_and_background_failure_preserves_plan() -> None:
    client, job, executor = _client()
    with client:
        created = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        url = f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}/decision"
        approved = client.post(url, json={"choice": "approve"})
        restored = client.get(f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}")
        repeated = client.post(url, json={"choice": "approve"})
        current = client.get(f"/api/trip-plans/{job.job_id}")

    assert approved.status_code == 202
    assert approved.json()["status"] == "replanning"
    assert restored.json()["status"] == "failed"
    assert repeated.status_code == 200 and repeated.json() == restored.json()
    assert current.json()["plan"]["plan_id"] == str(job.result.plan.plan_id)  # type: ignore[union-attr]
    assert executor.execution_calls == 1


def test_replan_errors_are_stable_and_strict() -> None:
    client, job, _ = _client()
    with client:
        invalid = client.post(
            f"/api/trip-plans/{job.job_id}/replans",
            json={**_payload(job), "prompt": "not allowed"},
        )
        missing = client.get(
            f"/api/trip-plans/{job.job_id}/replans/00000000-0000-4000-8000-000000000099"
        )
        no_list = client.get(f"/api/trip-plans/{job.job_id}/replans")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "input_invalid"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "replan_not_found"
    assert no_list.status_code == 405


def test_auto_replan_background_commit_is_read_as_completed_result_and_change_set() -> None:
    client, job, executor = _client(CommittingExecutor())
    with client:
        created = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        restored = client.get(f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}")

    assert created.status_code == 202 and created.json()["status"] == "replanning"
    body = restored.json()
    assert body["status"] == "completed"
    assert body["result"]["plan"]["plan_id"] == str(RESULT_PLAN_ID)
    assert body["change_set"]["baseline_plan_id"] == str(job.result.plan.plan_id)  # type: ignore[union-attr]
    assert body["change_set"]["result_plan_id"] == str(RESULT_PLAN_ID)
    assert executor.execution_calls == 1


def test_idempotency_baseline_and_scope_errors_use_frozen_public_codes() -> None:
    client, job, _ = _client()
    changed = _payload(job)
    command = changed["command"]
    assert isinstance(command, dict)
    changed_command = dict(command)
    changed_command["end_time"] = "13:00:00"
    changed["command"] = changed_command
    wrong_baseline = _payload(job)
    wrong_baseline["baseline_plan_id"] = "f0000000-0000-4000-8000-000000000099"
    with client:
        first = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        idempotency = client.post(f"/api/trip-plans/{job.job_id}/replans", json=changed)
        baseline = client.post(f"/api/trip-plans/{job.job_id}/replans", json=wrong_baseline)
    assert first.status_code == 202
    assert idempotency.status_code == 409
    assert idempotency.json()["error"]["code"] == "replan_idempotency_conflict"
    assert baseline.status_code == 409
    assert baseline.json()["error"]["code"] == "version_conflict"

    rejected_client, rejected_job, _ = _client(RejectingExecutor())
    with rejected_client:
        rejected = rejected_client.post(
            f"/api/trip-plans/{rejected_job.job_id}/replans",
            json=_payload(rejected_job),
        )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "replan_scope_not_supported"


def test_confirmation_at_exact_expiry_is_409_and_persists_expired_state() -> None:
    clock = ManualClock()
    client, job, executor = _client(clock=clock)
    with client:
        created = client.post(f"/api/trip-plans/{job.job_id}/replans", json=_payload(job))
        clock.now += timedelta(minutes=15)
        decision_url = (
            f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}/decision"
        )
        expired = client.post(decision_url, json={"choice": "approve"})
        restored = client.get(f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}")

    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "confirmation_expired"
    assert restored.status_code == 200 and restored.json()["status"] == "expired"
    assert executor.execution_calls == 0
