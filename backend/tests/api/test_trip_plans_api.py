"""Offline HTTP contract tests for F-001 planning-job resources."""

import ast
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import SERVICE_NAME, create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobReservation,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
API_ROOT = Path(__file__).resolve().parents[2] / "src" / "intelligent_travel_assistant" / "api"
NOW = datetime(2026, 8, 14, 3, tzinfo=UTC)
JOB_ID = UUID("a0000000-0000-4000-8000-000000000001")
TRACE_ID_ONE = UUID("b0000000-0000-4000-8000-000000000001")
TRACE_ID_TWO = UUID("b0000000-0000-4000-8000-000000000002")
TRACE_ID_THREE = UUID("b0000000-0000-4000-8000-000000000003")


class RecordingExecutor:
    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def execute(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


class SequentialIds:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)
        self.calls = 0

    def __call__(self) -> UUID:
        self.calls += 1
        return next(self._values)


def _payload() -> dict[str, object]:
    raw = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    assert isinstance(raw, dict)
    return raw


def _repository(
    *ids: UUID,
) -> tuple[InMemoryPlanningJobRepository, SequentialIds]:
    factory = SequentialIds(*ids)
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW, id_factory=factory)
    return repository, factory


def _partial_result() -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_partial.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    return PlanningJobResult(
        status=response.status,
        resolved_destination=response.resolved_destination,
        plan=response.plan,
        violations=response.violations,
        warnings=response.warnings,
        uncertainties=response.uncertainties,
        sources=response.sources,
        errors=response.errors,
        retryable=response.retryable,
    )


def _assert_safe_error(response_body: dict[str, object], code: str) -> None:
    assert set(response_body) == {"error"}
    error = response_body["error"]
    assert isinstance(error, dict)
    assert error["code"] == code
    assert error["retryable"] is False
    assert set(error) == {"code", "message", "retryable"}
    serialized = json.dumps(response_body)
    assert "client_request_id" not in serialized
    assert "request_fingerprint" not in serialized
    assert "version" not in serialized


def test_post_creates_draft_job_with_location_and_exact_public_shape() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post("/api/trip-plans", json=_payload())

    assert response.status_code == 202
    assert response.headers["location"] == f"/api/trip-plans/{JOB_ID}"
    body = response.json()
    assert set(body) == {
        "job_id",
        "trace_id",
        "client_request_id",
        "status",
        "attempt",
        "request_summary",
        "resolved_destination",
        "plan",
        "violations",
        "warnings",
        "uncertainties",
        "sources",
        "errors",
        "retryable",
        "created_at",
        "updated_at",
    }
    assert body["job_id"] == str(JOB_ID)
    assert body["trace_id"] == str(TRACE_ID_ONE)
    assert body["status"] == "draft"
    assert body["attempt"] == 1
    assert body["request_summary"] == {
        "city": "杭州",
        "start_date": "2026-08-15",
        "end_date": "2026-08-16",
        "travelers": 2,
        "budget": {"amount": "4000.00", "currency": "CNY"},
    }
    assert body["retryable"] is False
    assert "version" not in body
    assert "request_fingerprint" not in body


def test_duplicate_post_reuses_the_same_resource_without_allocating_ids() -> None:
    repository, ids = _repository(JOB_ID, TRACE_ID_ONE)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        first = client.post("/api/trip-plans", json=_payload())
        second = client.post("/api/trip-plans", json=_payload())

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert first.headers["location"] == second.headers["location"]
    assert ids.calls == 2


def test_post_schedules_new_job_once_but_idempotent_reuse_does_not_reschedule() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    executor = RecordingExecutor()
    with TestClient(
        create_app(planning_job_repository=repository, planning_job_executor=executor)
    ) as client:
        first = client.post("/api/trip-plans", json=_payload())
        second = client.post("/api/trip-plans", json=_payload())

    assert first.status_code == second.status_code == 202
    assert executor.job_ids == [JOB_ID]


def test_same_client_id_with_changed_body_returns_safe_conflict() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    changed = _payload()
    changed["city"] = "苏州"
    with TestClient(create_app(planning_job_repository=repository)) as client:
        assert client.post("/api/trip-plans", json=_payload()).status_code == 202
        response = client.post("/api/trip-plans", json=changed)

    assert response.status_code == 409
    _assert_safe_error(response.json(), "idempotency_conflict")
    assert str(JOB_ID) not in response.text


def test_invalid_request_returns_project_error_without_creating_a_job() -> None:
    repository, ids = _repository(JOB_ID, TRACE_ID_ONE)
    invalid = _payload()
    invalid["travelers"] = 0
    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post("/api/trip-plans", json=invalid)
        valid = client.post("/api/trip-plans", json=_payload())

    assert response.status_code == 422
    _assert_safe_error(response.json(), "input_invalid")
    assert valid.status_code == 202
    assert ids.calls == 2


def test_invalid_day_windows_fail_before_repository_or_executor_work() -> None:
    repository, ids = _repository(JOB_ID, TRACE_ID_ONE)
    executor = RecordingExecutor()
    invalid = _payload()
    invalid["day_windows"] = [
        {"day_offset": 0, "start_time": "18:00:00", "end_time": "09:00:00"},
        {"day_offset": 0, "start_time": "09:00:00", "end_time": "18:00:00"},
    ]

    with TestClient(
        create_app(planning_job_repository=repository, planning_job_executor=executor)
    ) as client:
        response = client.post("/api/trip-plans", json=invalid)

    assert response.status_code == 422
    _assert_safe_error(response.json(), "input_invalid")
    assert ids.calls == 0
    assert executor.job_ids == []


def test_get_returns_job_and_invalid_or_missing_ids_share_safe_404() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    missing = UUID("a0000000-0000-4000-8000-000000000099")
    with TestClient(create_app(planning_job_repository=repository)) as client:
        created = client.post("/api/trip-plans", json=_payload())
        found = client.get(f"/api/trip-plans/{JOB_ID}")
        missing_response = client.get(f"/api/trip-plans/{missing}")
        invalid_response = client.get("/api/trip-plans/not-a-uuid")

    assert found.status_code == 200
    assert found.json() == created.json()
    for response in (missing_response, invalid_response):
        assert response.status_code == 404
        _assert_safe_error(response.json(), "job_not_found")
        assert response.request.url.path not in response.text


def test_delete_removes_one_job_and_uses_safe_not_found_contract() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        assert client.post("/api/trip-plans", json=_payload()).status_code == 202
        deleted = client.delete(f"/api/trip-plans/{JOB_ID}")
        missing_get = client.get(f"/api/trip-plans/{JOB_ID}")
        missing_delete = client.delete(f"/api/trip-plans/{JOB_ID}")
        invalid_delete = client.delete("/api/trip-plans/not-a-uuid")

    assert deleted.status_code == 204
    assert deleted.content == b""
    for response in (missing_get, missing_delete, invalid_delete):
        assert response.status_code == 404
        _assert_safe_error(response.json(), "job_not_found")


async def _make_retryable(
    repository: InMemoryPlanningJobRepository,
    request: TripPlanRequest,
) -> PlanningJob:
    job = (await repository.get_or_create(request)).job
    for status in (PlanningStatus.NORMALIZING, PlanningStatus.COLLECTING):
        job = await repository.advance(job.job_id, status, expected_version=job.version)
    return await repository.record_result(
        job.job_id,
        _partial_result(),
        expected_version=job.version,
    )


async def _make_attempt_three_retryable(
    repository: InMemoryPlanningJobRepository,
    request: TripPlanRequest,
) -> PlanningJob:
    job = await _make_retryable(repository, request)
    for _attempt in (2, 3):
        job = await repository.retry(job.job_id, expected_version=job.version)
        job = await repository.advance(
            job.job_id,
            PlanningStatus.COLLECTING,
            expected_version=job.version,
        )
        job = await repository.record_result(
            job.job_id,
            _partial_result(),
            expected_version=job.version,
        )
    return job


def test_retry_reuses_job_increments_attempt_and_changes_trace() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE, TRACE_ID_TWO)
    request = TripPlanRequest.model_validate(_payload())
    before = asyncio.run(_make_retryable(repository, request))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post(f"/api/trip-plans/{JOB_ID}/retry")
        fetched = client.get(f"/api/trip-plans/{JOB_ID}")

    assert response.status_code == 202
    assert response.headers["location"] == f"/api/trip-plans/{JOB_ID}"
    assert response.json() == fetched.json()
    body = response.json()
    assert body["job_id"] == str(before.job_id)
    assert body["client_request_id"] == str(before.client_request_id)
    assert body["trace_id"] == str(TRACE_ID_TWO)
    assert body["status"] == "normalizing"
    assert body["attempt"] == 2
    assert body["retryable"] is False


def test_retry_schedules_the_existing_job_for_another_execution() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE, TRACE_ID_TWO)
    request = TripPlanRequest.model_validate(_payload())
    asyncio.run(_make_retryable(repository, request))
    executor = RecordingExecutor()

    with TestClient(
        create_app(planning_job_repository=repository, planning_job_executor=executor)
    ) as client:
        response = client.post(f"/api/trip-plans/{JOB_ID}/retry")

    assert response.status_code == 202
    assert executor.job_ids == [JOB_ID]


def test_retry_draft_missing_and_invalid_jobs_use_frozen_errors() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        client.post("/api/trip-plans", json=_payload())
        draft = client.post(f"/api/trip-plans/{JOB_ID}/retry")
        missing = client.post("/api/trip-plans/a0000000-0000-4000-8000-000000000099/retry")
        invalid = client.post("/api/trip-plans/not-a-uuid/retry")

    assert draft.status_code == 409
    _assert_safe_error(draft.json(), "retry_not_allowed")
    for response in (missing, invalid):
        assert response.status_code == 404
        _assert_safe_error(response.json(), "job_not_found")


def test_retry_limit_maps_to_the_same_stable_conflict() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE, TRACE_ID_TWO, TRACE_ID_THREE)
    request = TripPlanRequest.model_validate(_payload())
    job = asyncio.run(_make_attempt_three_retryable(repository, request))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post(f"/api/trip-plans/{job.job_id}/retry")

    assert job.attempt == 3
    assert response.status_code == 409
    _assert_safe_error(response.json(), "retry_not_allowed")


class BrokenRepository:
    async def get_or_create(self, request: TripPlanRequest) -> PlanningJobReservation:
        del request
        raise RuntimeError("sensitive internal detail")

    async def get(self, job_id: UUID) -> PlanningJob:
        del job_id
        raise RuntimeError("sensitive internal detail")

    async def advance(
        self,
        job_id: UUID,
        target_status: PlanningStatus,
        *,
        expected_version: int,
        retryable: bool = False,
    ) -> PlanningJob:
        del job_id, target_status, expected_version, retryable
        raise RuntimeError("sensitive internal detail")

    async def retry(self, job_id: UUID, *, expected_version: int) -> PlanningJob:
        del job_id, expected_version
        raise RuntimeError("sensitive internal detail")

    async def record_result(
        self,
        job_id: UUID,
        result: PlanningJobResult,
        *,
        expected_version: int,
    ) -> PlanningJob:
        del job_id, result, expected_version
        raise RuntimeError("sensitive internal detail")

    async def delete(self, job_id: UUID) -> None:
        del job_id
        raise RuntimeError("sensitive internal detail")


def test_unexpected_repository_failure_returns_safe_internal_error() -> None:
    with TestClient(create_app(planning_job_repository=BrokenRepository())) as client:
        response = client.post("/api/trip-plans", json=_payload())
        delete_response = client.delete(f"/api/trip-plans/{JOB_ID}")

    assert response.status_code == 500
    _assert_safe_error(response.json(), "internal_error")
    assert "sensitive internal detail" not in response.text
    assert delete_response.status_code == 500
    _assert_safe_error(delete_response.json(), "internal_error")
    assert "sensitive internal detail" not in delete_response.text


def test_default_apps_have_isolated_process_local_repositories() -> None:
    first_payload = _payload()
    second_payload = _payload()
    second_payload["city"] = "苏州"

    with TestClient(create_app()) as first_client:
        first = first_client.post("/api/trip-plans", json=first_payload)
    with TestClient(create_app()) as second_client:
        second = second_client.post("/api/trip-plans", json=second_payload)

    assert first.status_code == second.status_code == 202


def test_health_contract_remains_available_without_provider_configuration() -> None:
    repository, _ = _repository(JOB_ID, TRACE_ID_ONE)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": SERVICE_NAME}


def test_http_adapter_has_no_orchestrator_provider_or_storage_dependency() -> None:
    forbidden_roots = {
        "httpx",
        "openai",
        "requests",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "urllib",
    }
    forbidden_modules = {
        "intelligent_travel_assistant.adapters.fakes",
        "intelligent_travel_assistant.application.services",
        "intelligent_travel_assistant.application.ports",
    }
    observed: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                modules = ()
            observed.extend(
                module
                for module in modules
                if module.split(".", 1)[0] in forbidden_roots
                or any(module.startswith(forbidden) for forbidden in forbidden_modules)
            )

    assert observed == []
