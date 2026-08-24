"""F-004B1 V3 same-URI API and write-before-replan rejection tests."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from tests.application.test_multicity_planning_job_repository import (
    advance_to_validating,
    result,
)
from tests.contracts.test_multicity_trip_planning_contracts import request_payload

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import PlanningJob
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.settings import Settings

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)
_TERMINAL = frozenset({"ready", "partial", "needs_input", "conflict", "failed"})


def settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


def wait_for_terminal(client: TestClient, job_id: str) -> dict[str, object]:
    for _ in range(200):
        response = client.get(f"/api/trip-plans/{job_id}")
        body: dict[str, object] = response.json()
        if body["status"] in _TERMINAL:
            return body
        time.sleep(0.01)
    raise AssertionError("planning job did not reach a terminal state")


class RecordingExecutor:
    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def execute(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


def test_v3_post_get_retry_delete_share_existing_uris_with_executor_dispatch() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    executor = RecordingExecutor()
    app = create_app(planning_job_repository=repository, planning_job_executor=executor)

    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=request_payload())
        restored = client.get(f"/api/trip-plans/{created.json()['job_id']}")

    assert created.status_code == 202 and restored.status_code == 200
    assert restored.json() == created.json()
    assert created.json()["response_version"] == "3"
    assert created.json()["request_summary"]["request_version"] == "3"
    assert created.json()["resolved_destinations"] == []
    assert "resolved_destination" not in created.json()
    assert executor.job_ids == [UUID(created.json()["job_id"])]

    async def publish_partial() -> PlanningJob:
        job = await repository.get(UUID(created.json()["job_id"]))
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(unknown_fare=True, retryable=True),
            expected_version=job.version,
        )

    partial = asyncio.run(publish_partial())
    with TestClient(app) as client:
        terminal = client.get(f"/api/trip-plans/{partial.job_id}")
        retried = client.post(f"/api/trip-plans/{partial.job_id}/retry")
        deleted = client.delete(f"/api/trip-plans/{partial.job_id}")
        missing = client.get(f"/api/trip-plans/{partial.job_id}")

    assert terminal.status_code == 200
    assert terminal.json()["status"] == "partial"
    assert terminal.json()["plan"]["plan_format_version"] == "3"
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    assert deleted.status_code == 204 and missing.status_code == 404
    assert executor.job_ids == [partial.job_id, partial.job_id]


def test_openapi_and_strict_request_discriminator_expose_four_versioned_branches() -> None:
    app = create_app(planning_job_repository=InMemoryPlanningJobRepository())
    schema = app.openapi()["paths"]["/api/trip-plans"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]

    assert {item["$ref"].rsplit("/", 1)[-1] for item in schema["oneOf"]} == {
        "TripPlanRequest",
        "TripPlanRequestV2",
        "TripPlanRequestV3",
        "TripPlanRequestV4",
    }

    with TestClient(app) as client:
        invalid = []
        for version in (3, None, "5", True):
            payload = request_payload()
            payload["request_version"] = version
            invalid.append(client.post("/api/trip-plans", json=payload))

    assert {response.status_code for response in invalid} == {422}
    assert {response.json()["error"]["code"] for response in invalid} == {"input_invalid"}


def test_sqlite_v3_replan_is_rejected_before_service_and_all_writes(tmp_path: Path) -> None:
    path = tmp_path / "multicity-api.sqlite3"
    with TestClient(create_app(settings=settings(path))) as client:
        created = client.post("/api/trip-plans", json=request_payload())
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        baseline = wait_for_terminal(client, job_id)
        with sqlite3.connect(path) as inspection:
            baseline_job_row = inspection.execute(
                "SELECT version, status FROM planning_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        rejected = client.post(
            f"/api/trip-plans/{job_id}/replans",
            json={
                "replan_request_id": "f4000000-0000-4000-8000-000000000001",
                "baseline_plan_id": "f4000000-0000-4000-8000-000000000002",
                "command": {
                    "operation": "adjust_activity_time",
                    "target_activity_id": "f4000000-0000-4000-8000-000000000003",
                    "start_time": "10:30:00",
                    "end_time": "12:30:00",
                    "reason_code": "user_schedule_preference",
                },
            },
        )
        restored = client.get(f"/api/trip-plans/{job_id}")

    with sqlite3.connect(path) as inspection:
        counts = {
            table: inspection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("replan_requests", "decision_records", "plan_version_lineage")
        }
        job_row = inspection.execute(
            "SELECT version, status FROM planning_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()

    assert created.status_code == 202
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "replan_scope_not_supported"
    assert restored.json() == baseline
    assert counts == {table: 0 for table in counts}
    assert tuple(job_row) == tuple(baseline_job_row)
    assert job_row[1] == PlanningStatus.FAILED.value
