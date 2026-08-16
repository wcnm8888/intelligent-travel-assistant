"""Offline vertical tests for replan HTTP resources backed by temporary SQLite."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from uuid import UUID

import httpx2
from fastapi import FastAPI

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
    SqliteReplanRepository,
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
    AdjustActivityTime,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanCommand,
    ReplanStatus,
)
from intelligent_travel_assistant.settings import Settings

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
RESULT_PLAN_ID = UUID("f7000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)


def _settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


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


async def _seed_ready(repository: SqlitePlanningJobRepository) -> PlanningJob:
    job = (await repository.get_or_create(_request())).job
    for target in (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.VALIDATING,
    ):
        job = await repository.advance(job.job_id, target, expected_version=job.version)
    return await repository.record_result(
        job.job_id,
        _ready_result(),
        expected_version=job.version,
    )


class _Executor:
    def __init__(self, *, outcome: ReplanStatus | None = None) -> None:
        self.calls = 0
        self.outcome = outcome

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        assert isinstance(command, AdjustActivityTime)
        target = command.target_activity_id
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
        self.calls += 1
        if self.outcome is not None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(self.outcome, f"offline_{self.outcome.value}")
            )
        assert job.result is not None and job.result.plan is not None
        changed = _ready_result()
        assert changed.plan is not None
        changed = PlanningJobResult(
            changed.status,
            changed.resolved_destination,
            changed.plan.model_copy(update={"plan_id": RESULT_PLAN_ID}),
            changed.violations,
            changed.warnings,
            changed.uncertainties,
            changed.sources,
            changed.errors,
            changed.retryable,
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


class _ConcurrentExecutor(_Executor):
    def __init__(self) -> None:
        super().__init__()
        self._analysis_calls = 0
        self._both_analyzed = asyncio.Event()

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        impact = await super().analyze(job, command)
        self._analysis_calls += 1
        if self._analysis_calls == 2:
            self._both_analyzed.set()
        await self._both_analyzed.wait()
        return impact


def _payload(job: PlanningJob, request_id: str) -> dict[str, object]:
    assert job.result is not None and job.result.plan is not None
    return {
        "replan_request_id": request_id,
        "baseline_plan_id": str(job.result.plan.plan_id),
        "command": {
            "operation": "adjust_activity_time",
            "target_activity_id": str(job.result.plan.days[0].activities[0].item_id),
            "start_time": "10:30:00",
            "end_time": "12:30:00",
            "reason_code": "user_schedule_preference",
        },
    }


def _open(path: Path) -> SqliteDatabase:
    database = SqliteDatabase(SqliteConnectionConfig(path))
    MigrationRunner().run(database.open())
    return database


async def _request_api(
    app: FastAPI,
    method: str,
    url: str,
    *,
    json: object | None = None,
) -> httpx2.Response:
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, url, json=json)


def test_completed_replan_is_idempotent_and_survives_database_restart(tmp_path: Path) -> None:
    path = tmp_path / "vertical-replan.sqlite3"
    database = _open(path)
    planning = SqlitePlanningJobRepository(database, clock=lambda: NOW)
    job = asyncio.run(_seed_ready(planning))
    assert job.result is not None and job.result.plan is not None
    baseline_plan_id = job.result.plan.plan_id
    executor = _Executor()
    replans = SqliteReplanRepository(database, clock=lambda: NOW)
    app = create_app(
        settings=_settings(path),
        planning_job_repository=planning,
        replan_application_service=ReplanApplicationService(planning, replans, executor),
    )
    request_id = "f7000000-0000-4000-8000-000000000002"
    url = f"/api/trip-plans/{job.job_id}/replans"

    created = asyncio.run(_request_api(app, "POST", url, json=_payload(job, request_id)))
    repeated = asyncio.run(_request_api(app, "POST", url, json=_payload(job, request_id)))
    replan_id = created.json()["replan_id"]
    current = asyncio.run(_request_api(app, "GET", f"/api/trip-plans/{job.job_id}"))

    assert created.status_code == 202 and created.json()["status"] == "replanning"
    assert repeated.status_code == 202 and repeated.json()["status"] == "completed"
    assert repeated.json()["replan_id"] == replan_id
    assert current.json()["plan"]["plan_id"] == str(RESULT_PLAN_ID)
    assert executor.calls == 1
    stored_command = database.connection.execute(
        "SELECT request_json FROM replan_requests WHERE replan_id = ?", (replan_id,)
    ).fetchone()[0]
    assert set(json.loads(stored_command)) == {
        "operation",
        "target_activity_id",
        "start_time",
        "end_time",
        "reason_code",
    }
    assert not any(
        forbidden in stored_command.lower()
        for forbidden in ("authorization", "cookie", "token", "prompt", "provider_response")
    )
    database.close()

    restarted_database = _open(path)
    restarted_planning = SqlitePlanningJobRepository(restarted_database, clock=lambda: NOW)
    restarted_replans = SqliteReplanRepository(restarted_database, clock=lambda: NOW)
    restarted_app = create_app(
        settings=_settings(path),
        planning_job_repository=restarted_planning,
        replan_application_service=ReplanApplicationService(
            restarted_planning,
            restarted_replans,
            _Executor(),
        ),
    )
    restored = asyncio.run(
        _request_api(
            restarted_app,
            "GET",
            f"/api/trip-plans/{job.job_id}/replans/{replan_id}",
        )
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "completed"
    assert restored.json()["result"]["plan"]["plan_id"] == str(RESULT_PLAN_ID)
    assert restored.json()["change_set"]["baseline_plan_id"] == str(baseline_plan_id)
    migration_versions = restarted_database.connection.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert [row["version"] for row in migration_versions] == [1, 2]
    restarted_database.close()


def test_failed_replan_persists_and_preserves_the_original_plan(tmp_path: Path) -> None:
    path = tmp_path / "failed-replan.sqlite3"
    database = _open(path)
    planning = SqlitePlanningJobRepository(database, clock=lambda: NOW)
    job = asyncio.run(_seed_ready(planning))
    assert job.result is not None and job.result.plan is not None
    baseline_plan_id = job.result.plan.plan_id
    executor = _Executor(outcome=ReplanStatus.FAILED)
    replans = SqliteReplanRepository(database, clock=lambda: NOW)
    app = create_app(
        settings=_settings(path),
        planning_job_repository=planning,
        replan_application_service=ReplanApplicationService(planning, replans, executor),
    )

    created = asyncio.run(
        _request_api(
            app,
            "POST",
            f"/api/trip-plans/{job.job_id}/replans",
            json=_payload(job, "f7000000-0000-4000-8000-000000000003"),
        )
    )
    restored = asyncio.run(
        _request_api(
            app,
            "GET",
            f"/api/trip-plans/{job.job_id}/replans/{created.json()['replan_id']}",
        )
    )
    current = asyncio.run(_request_api(app, "GET", f"/api/trip-plans/{job.job_id}"))

    assert created.status_code == 202 and created.json()["status"] == "replanning"
    assert restored.json()["status"] == "failed"
    assert restored.json()["result"] is None and restored.json()["change_set"] is None
    assert current.json()["plan"]["plan_id"] == str(baseline_plan_id)
    assert executor.calls == 1
    database.close()


def test_concurrent_replans_create_at_most_one_new_plan_version(tmp_path: Path) -> None:
    path = tmp_path / "concurrent-replans.sqlite3"
    database = _open(path)
    planning = SqlitePlanningJobRepository(database, clock=lambda: NOW)
    job = asyncio.run(_seed_ready(planning))
    executor = _ConcurrentExecutor()
    replans = SqliteReplanRepository(database, clock=lambda: NOW)
    app = create_app(
        settings=_settings(path),
        planning_job_repository=planning,
        replan_application_service=ReplanApplicationService(planning, replans, executor),
    )
    url = f"/api/trip-plans/{job.job_id}/replans"

    async def create_both() -> tuple[httpx2.Response, httpx2.Response]:
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
            first, second = await asyncio.gather(
                client.post(
                    url,
                    json=_payload(job, "f7000000-0000-4000-8000-000000000004"),
                ),
                client.post(
                    url,
                    json=_payload(job, "f7000000-0000-4000-8000-000000000005"),
                ),
            )
        return first, second

    responses = asyncio.run(create_both())
    assert [response.status_code for response in responses] == [202, 202]
    restored = [
        asyncio.run(
            _request_api(
                app,
                "GET",
                f"{url}/{response.json()['replan_id']}",
            )
        )
        for response in responses
    ]
    assert sorted(response.json()["status"] for response in restored) == [
        "completed",
        "conflict",
    ]
    assert (
        database.connection.execute(
            "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?", (str(job.job_id),)
        ).fetchone()[0]
        == 2
    )
    database.close()
