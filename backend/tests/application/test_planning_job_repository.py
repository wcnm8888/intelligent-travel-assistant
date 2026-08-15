"""In-process planning jobs, deterministic idempotency, and state guards."""

import ast
import asyncio
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
    request_fingerprint,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
REPOSITORY_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "adapters"
    / "repositories"
)
JOB_ID_ONE = UUID("a0000000-0000-4000-8000-000000000001")
TRACE_ID_ONE = UUID("b0000000-0000-4000-8000-000000000001")
JOB_ID_TWO = UUID("a0000000-0000-4000-8000-000000000002")
TRACE_ID_TWO = UUID("b0000000-0000-4000-8000-000000000002")
TRACE_ID_THREE = UUID("b0000000-0000-4000-8000-000000000003")
TRACE_ID_FOUR = UUID("b0000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)


class ManualClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self) -> None:
        self.value += timedelta(seconds=1)


class SequentialIds:
    def __init__(self, *values: UUID) -> None:
        self.values = iter(values)
        self.calls = 0

    def __call__(self) -> UUID:
        self.calls += 1
        return next(self.values)


def _request(*, client_request_id: UUID | None = None, city: str = "杭州") -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    if client_request_id is not None:
        payload["client_request_id"] = str(client_request_id)
    payload["city"] = city
    return TripPlanRequest.model_validate(payload)


def _repository(*ids: UUID) -> tuple[InMemoryPlanningJobRepository, ManualClock, SequentialIds]:
    clock = ManualClock()
    factory = SequentialIds(*ids)
    return InMemoryPlanningJobRepository(clock=clock, id_factory=factory), clock, factory


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


def test_request_fingerprint_is_stable_normalized_and_never_contains_input_text() -> None:
    first = _request()
    same_body_new_client = _request(client_request_id=UUID("11111111-1111-4111-8111-111111111112"))
    normalized_whitespace = _request(city="  杭州  ")

    fingerprint = request_fingerprint(first)

    assert fingerprint == request_fingerprint(same_body_new_client)
    assert fingerprint == request_fingerprint(normalized_whitespace)
    assert fingerprint.algorithm == "sha256"
    assert len(fingerprint.digest) == 64
    assert "杭州" not in repr(fingerprint)
    assert "节奏不要太赶" not in repr(fingerprint)


def test_same_client_and_same_request_reuses_one_job_without_new_ids() -> None:
    repository, _, ids = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    request = _request()

    first = asyncio.run(repository.get_or_create(request))
    second = asyncio.run(repository.get_or_create(_request()))

    assert first.created is True
    assert second.created is False
    assert second.job is first.job
    assert first.job.job_id == JOB_ID_ONE
    assert first.job.trace_id == TRACE_ID_ONE
    assert first.job.status is PlanningStatus.DRAFT
    assert first.job.attempt == 1
    assert first.job.version == 1
    assert ids.calls == 2


def test_same_client_with_changed_request_is_a_stable_conflict() -> None:
    repository, _, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    request = _request()
    asyncio.run(repository.get_or_create(request))

    with pytest.raises(PlanningJobRepositoryError) as raised:
        asyncio.run(repository.get_or_create(_request(city="苏州")))

    assert raised.value.code is PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT
    assert str(request.client_request_id) not in str(raised.value)


def test_different_client_ids_create_distinct_jobs_for_the_same_body() -> None:
    repository, _, ids = _repository(JOB_ID_ONE, TRACE_ID_ONE, JOB_ID_TWO, TRACE_ID_TWO)
    first_request = _request()
    second_request = _request(client_request_id=UUID("11111111-1111-4111-8111-111111111112"))

    first = asyncio.run(repository.get_or_create(first_request))
    second = asyncio.run(repository.get_or_create(second_request))

    assert first.job.job_id != second.job.job_id
    assert first.job.request_fingerprint == second.job.request_fingerprint
    assert ids.calls == 4


def test_concurrent_same_request_has_exactly_one_creator() -> None:
    repository, _, ids = _repository(JOB_ID_ONE, TRACE_ID_ONE)

    async def create_concurrently() -> list[PlanningJobReservation]:
        return await asyncio.gather(*(repository.get_or_create(_request()) for _ in range(20)))

    results = asyncio.run(create_concurrently())

    assert sum(item.created for item in results) == 1
    assert {item.job.job_id for item in results} == {JOB_ID_ONE}
    assert ids.calls == 2


def test_job_snapshots_are_frozen_and_old_versions_do_not_mutate() -> None:
    repository, clock, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    created = asyncio.run(repository.get_or_create(_request())).job
    clock.advance()

    updated = asyncio.run(
        repository.advance(
            created.job_id,
            PlanningStatus.NORMALIZING,
            expected_version=created.version,
        )
    )

    assert created.status is PlanningStatus.DRAFT
    assert created.version == 1
    assert updated.status is PlanningStatus.NORMALIZING
    assert updated.version == 2
    assert updated.updated_at > created.updated_at
    with pytest.raises(FrozenInstanceError):
        updated.status = PlanningStatus.READY  # type: ignore[misc]


def test_advance_uses_state_machine_and_rejects_skips_without_mutation() -> None:
    repository, _, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    created = asyncio.run(repository.get_or_create(_request())).job

    with pytest.raises(PlanningJobRepositoryError) as raised:
        asyncio.run(
            repository.advance(
                created.job_id,
                PlanningStatus.READY,
                expected_version=created.version,
            )
        )

    assert raised.value.code is PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED
    assert asyncio.run(repository.get(created.job_id)) is created


def test_optimistic_version_prevents_lost_concurrent_updates() -> None:
    repository, _, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    created = asyncio.run(repository.get_or_create(_request())).job

    async def race() -> tuple[PlanningJob | BaseException, PlanningJob | BaseException]:
        return await asyncio.gather(
            repository.advance(
                created.job_id,
                PlanningStatus.NORMALIZING,
                expected_version=created.version,
            ),
            repository.advance(
                created.job_id,
                PlanningStatus.NORMALIZING,
                expected_version=created.version,
            ),
            return_exceptions=True,
        )

    results = asyncio.run(race())

    assert sum(not isinstance(item, Exception) for item in results) == 1
    errors = [item for item in results if isinstance(item, PlanningJobRepositoryError)]
    assert len(errors) == 1
    assert errors[0].code is PlanningJobRepositoryErrorCode.VERSION_CONFLICT


def test_retry_increments_attempt_changes_trace_and_reenters_normalizing() -> None:
    repository, clock, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE, TRACE_ID_TWO)
    job = asyncio.run(repository.get_or_create(_request())).job
    for status in (PlanningStatus.NORMALIZING, PlanningStatus.COLLECTING):
        clock.advance()
        job = asyncio.run(repository.advance(job.job_id, status, expected_version=job.version))
    clock.advance()
    job = asyncio.run(
        repository.record_result(
            job.job_id,
            _partial_result(),
            expected_version=job.version,
        )
    )
    old_trace = job.trace_id
    clock.advance()

    retried = asyncio.run(repository.retry(job.job_id, expected_version=job.version))

    assert retried.job_id == job.job_id
    assert retried.client_request_id == job.client_request_id
    assert retried.status is PlanningStatus.NORMALIZING
    assert retried.attempt == 2
    assert retried.trace_id == TRACE_ID_TWO
    assert retried.trace_id != old_trace
    assert retried.retryable is False


def test_retry_limit_and_nonretryable_status_are_rejected() -> None:
    repository, _, _ = _repository(
        JOB_ID_ONE,
        TRACE_ID_ONE,
        TRACE_ID_TWO,
        TRACE_ID_THREE,
        TRACE_ID_FOUR,
    )
    job = asyncio.run(repository.get_or_create(_request())).job
    for attempt in (1, 2, 3):
        if job.status is PlanningStatus.DRAFT:
            job = asyncio.run(
                repository.advance(
                    job.job_id,
                    PlanningStatus.NORMALIZING,
                    expected_version=job.version,
                )
            )
        job = asyncio.run(
            repository.advance(
                job.job_id,
                PlanningStatus.COLLECTING,
                expected_version=job.version,
            )
        )
        job = asyncio.run(
            repository.record_result(
                job.job_id,
                _partial_result(),
                expected_version=job.version,
            )
        )
        if attempt < 3:
            job = asyncio.run(repository.retry(job.job_id, expected_version=job.version))

    with pytest.raises(PlanningJobRepositoryError) as raised:
        asyncio.run(repository.retry(job.job_id, expected_version=job.version))

    assert job.attempt == 3
    assert raised.value.code is PlanningJobRepositoryErrorCode.RETRY_LIMIT_REACHED


def test_missing_job_and_invalid_retry_use_safe_errors() -> None:
    repository, _, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    missing = UUID("a0000000-0000-4000-8000-000000000099")

    with pytest.raises(PlanningJobRepositoryError) as missing_error:
        asyncio.run(repository.get(missing))
    assert missing_error.value.code is PlanningJobRepositoryErrorCode.JOB_NOT_FOUND
    assert str(missing) not in str(missing_error.value)

    job = asyncio.run(repository.get_or_create(_request())).job
    with pytest.raises(PlanningJobRepositoryError) as retry_error:
        asyncio.run(repository.retry(job.job_id, expected_version=job.version))
    assert retry_error.value.code is PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED


def test_repository_protocol_and_memory_adapter_have_narrow_offline_boundary() -> None:
    repository, _, _ = _repository(JOB_ID_ONE, TRACE_ID_ONE)
    assert isinstance(repository, PlanningJobRepository)

    forbidden_roots = {
        "fastapi",
        "httpx",
        "openai",
        "os",
        "requests",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "urllib",
    }
    observed: list[str] = []
    for path in REPOSITORY_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                modules = ()
            observed.extend(
                module for module in modules if module.split(".", 1)[0] in forbidden_roots
            )

    assert observed == []
