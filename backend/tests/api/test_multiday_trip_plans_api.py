"""F-004A same-URI version 2 planning API compatibility tests."""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequestV2,
    TripPlanResponseV2,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)


def legacy_payload() -> dict[str, object]:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    assert isinstance(payload, dict)
    return payload


def v2_payload(day_count: int = 3) -> dict[str, object]:
    payload = copy.deepcopy(legacy_payload())
    start = date.fromisoformat(str(payload["start_date"]))
    payload["request_version"] = "2"
    payload["end_date"] = (start + timedelta(days=day_count - 1)).isoformat()
    payload["day_windows"] = [
        {"day_offset": offset, "start_time": "09:00:00", "end_time": "18:00:00"}
        for offset in range(day_count)
    ]
    return payload


def terminal_response(
    day_count: int = 3,
    scenario: str = "ready",
) -> TripPlanResponseV2:
    payload = copy.deepcopy(
        json.loads(
            (FIXTURE_ROOT / f"synthetic_hangzhou_{scenario}.json").read_text(encoding="utf-8")
        )["response"]
    )
    summary = payload["request_summary"]
    plan = payload["plan"]
    start = date.fromisoformat(str(summary["start_date"]))
    end = start + timedelta(days=day_count - 1)
    payload["response_version"] = "2"
    summary["request_version"] = "2"
    summary["end_date"] = end.isoformat()
    plan["plan_format_version"] = "2"
    plan["end_date"] = end.isoformat()
    originals = plan["days"]
    days = []
    for offset in range(day_count):
        day = copy.deepcopy(originals[min(offset, 1)])
        local_date = start + timedelta(days=offset)
        day["local_date"] = local_date.isoformat()
        if day["weather"] is not None:
            day["weather"]["forecast_date"] = local_date.isoformat()
        days.append(day)
    plan["days"] = days
    return TripPlanResponseV2.model_validate(payload)


class RecordingExecutor:
    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def execute(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


def test_v2_post_dispatches_executor_and_keeps_explicit_response_tags() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    executor = RecordingExecutor()
    app = create_app(
        planning_job_repository=repository,
        planning_job_executor=executor,
    )

    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=v2_payload(3))
        restored = client.get(f"/api/trip-plans/{created.json()['job_id']}")

    assert created.status_code == 202
    assert restored.status_code == 200
    assert restored.json() == created.json()
    assert created.json()["response_version"] == "2"
    assert created.json()["request_summary"]["request_version"] == "2"
    assert created.json()["request_summary"]["end_date"] == "2026-08-17"
    assert "plan_format_version" not in created.json()
    assert executor.job_ids == [UUID(created.json()["job_id"])]


def test_v2_terminal_get_projects_the_typed_multiday_plan() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def publish() -> PlanningJob:
        request = TripPlanRequestV2.model_validate(v2_payload(3))
        job = (await repository.get_or_create(request)).job
        for target in (
            PlanningStatus.NORMALIZING,
            PlanningStatus.COLLECTING,
            PlanningStatus.PLANNING,
            PlanningStatus.ENRICHING_ROUTES,
            PlanningStatus.VALIDATING,
        ):
            job = await repository.advance(job.job_id, target, expected_version=job.version)
        response = terminal_response(3)
        return await repository.record_result(
            job.job_id,
            PlanningJobResult(
                response.status,
                response.resolved_destination,
                response.plan,
                response.violations,
                response.warnings,
                response.uncertainties,
                response.sources,
                response.errors,
                response.retryable,
            ),
            expected_version=job.version,
        )

    stored = asyncio.run(publish())
    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.get(f"/api/trip-plans/{stored.job_id}")

    assert response.status_code == 200
    assert response.json()["response_version"] == "2"
    assert response.json()["plan"]["plan_format_version"] == "2"
    assert len(response.json()["plan"]["days"]) == 3


def test_v2_retry_dispatches_the_existing_executor() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def publish_partial() -> PlanningJob:
        request = TripPlanRequestV2.model_validate(v2_payload(3))
        job = (await repository.get_or_create(request)).job
        for target in (
            PlanningStatus.NORMALIZING,
            PlanningStatus.COLLECTING,
            PlanningStatus.PLANNING,
            PlanningStatus.ENRICHING_ROUTES,
            PlanningStatus.VALIDATING,
        ):
            job = await repository.advance(job.job_id, target, expected_version=job.version)
        response = terminal_response(3, "partial")
        return await repository.record_result(
            job.job_id,
            PlanningJobResult(
                response.status,
                response.resolved_destination,
                response.plan,
                response.violations,
                response.warnings,
                response.uncertainties,
                response.sources,
                response.errors,
                response.retryable,
            ),
            expected_version=job.version,
        )

    stored = asyncio.run(publish_partial())
    executor = RecordingExecutor()
    with TestClient(
        create_app(
            planning_job_repository=repository,
            planning_job_executor=executor,
        )
    ) as client:
        retried = client.post(f"/api/trip-plans/{stored.job_id}/retry")

    assert retried.status_code == 202
    assert retried.json()["status"] == "normalizing"
    assert retried.json()["attempt"] == 2
    assert executor.job_ids == [stored.job_id]


def test_unknown_or_ambiguous_request_versions_return_the_existing_safe_422() -> None:
    app = create_app(planning_job_repository=InMemoryPlanningJobRepository())
    with TestClient(app) as client:
        responses = []
        for version in (None, 2, "3", True):
            payload = v2_payload()
            payload["request_version"] = version
            responses.append(client.post("/api/trip-plans", json=payload))

    assert {response.status_code for response in responses} == {422}
    assert {response.json()["error"]["code"] for response in responses} == {"input_invalid"}


def test_legacy_post_shape_remains_untagged_and_cross_version_reuse_conflicts() -> None:
    app = create_app(planning_job_repository=InMemoryPlanningJobRepository(clock=lambda: NOW))
    legacy = legacy_payload()
    versioned = v2_payload()

    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=legacy)
        conflict = client.post("/api/trip-plans", json=versioned)

    assert created.status_code == 202
    assert "response_version" not in created.json()
    assert "request_version" not in created.json()["request_summary"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_openapi_keeps_a_typed_one_of_request_body() -> None:
    app = create_app(planning_job_repository=InMemoryPlanningJobRepository())
    schema = app.openapi()["paths"]["/api/trip-plans"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]

    assert len(schema["oneOf"]) == 2
    assert {item["$ref"].rsplit("/", 1)[-1] for item in schema["oneOf"]} == {
        "TripPlanRequest",
        "TripPlanRequestV2",
    }


def test_three_to_seven_day_replan_is_rejected_before_service_or_write() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    app = create_app(
        planning_job_repository=repository,
        replan_application_service=None,
    )
    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=v2_payload(3))
        job_id = created.json()["job_id"]
        rejected = client.post(
            f"/api/trip-plans/{job_id}/replans",
            json={
                "replan_request_id": "f0000000-0000-4000-8000-000000000006",
                "baseline_plan_id": "f0000000-0000-4000-8000-000000000007",
                "command": {
                    "operation": "adjust_activity_time",
                    "target_activity_id": "f0000000-0000-4000-8000-000000000008",
                    "start_time": "10:30:00",
                    "end_time": "12:30:00",
                    "reason_code": "user_schedule_preference",
                },
            },
        )
        restored = client.get(f"/api/trip-plans/{job_id}")

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "replan_scope_not_supported"
    assert restored.status_code == 200
    assert restored.json() == created.json()
