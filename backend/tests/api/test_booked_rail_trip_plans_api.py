"""F-004C V4 same-URI API projection and pre-write replan rejection."""

from __future__ import annotations

import asyncio
import copy
import sqlite3
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from tests.application.test_booked_rail_planning_job_repository import (
    advance_to_validating,
    result,
)
from tests.contracts.test_booked_rail_trip_planning_contracts import request_payload

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import PlanningJob
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.settings import Settings

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)


class RecordingExecutor:
    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def execute(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


def settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


def test_v4_post_get_retry_delete_use_existing_uris_and_exact_shape() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    executor = RecordingExecutor()
    app = create_app(planning_job_repository=repository, planning_job_executor=executor)

    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=request_payload())
        restored = client.get(f"/api/trip-plans/{created.json()['job_id']}")
        repeated = client.post("/api/trip-plans", json=request_payload())
        changed = copy.deepcopy(request_payload())
        segments = changed["intercity_segments"]
        assert isinstance(segments, list) and isinstance(segments[0], dict)
        segments[0]["service_number"] = "G1235"
        conflict = client.post("/api/trip-plans", json=changed)

    assert created.status_code == 202 and restored.status_code == 200
    assert restored.json() == created.json()
    assert repeated.status_code == 202 and repeated.json() == created.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert created.json()["response_version"] == "4"
    assert created.json()["request_summary"]["request_version"] == "4"
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

    assert terminal.json()["plan"]["plan_format_version"] == "4"
    assert terminal.json()["plan"]["intercity_segments"][0]["service_number"] == "G1234"
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    assert deleted.status_code == 204
    assert executor.job_ids == [partial.job_id, partial.job_id]


def test_openapi_exposes_v4_as_the_fourth_strict_request_branch() -> None:
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


def test_sqlite_v4_replan_is_rejected_before_all_replan_writes(tmp_path: Path) -> None:
    path = tmp_path / "booked-rail-api.sqlite3"
    with TestClient(create_app(settings=settings(path))) as client:
        created = client.post("/api/trip-plans", json=request_payload())
        job_id = created.json()["job_id"]
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
    assert restored.json() == created.json()
    assert counts == {table: 0 for table in counts}
    assert tuple(job_row) == (1, PlanningStatus.DRAFT.value)
