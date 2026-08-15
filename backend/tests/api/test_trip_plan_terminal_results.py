"""Five terminal job representations and safe result-publication rules."""

import asyncio
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    PlanningStatus,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
CASE_FILES = (
    "synthetic_hangzhou_ready.json",
    "synthetic_hangzhou_partial.json",
    "synthetic_hangzhou_conflict.json",
    "synthetic_hangzhou_needs_input.json",
    "synthetic_hangzhou_failed.json",
)
RETRY_TRACE_ID = UUID("b0000000-0000-4000-8000-000000000099")


class ManualClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class SequentialIds:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def _request() -> TripPlanRequest:
    data = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    return TripPlanRequest.model_validate(data["request"])


def _response(case_file: str) -> TripPlanResponse:
    data = json.loads((FIXTURE_ROOT / case_file).read_text(encoding="utf-8"))
    return TripPlanResponse.model_validate(data["response"])


def _result(response: TripPlanResponse) -> PlanningJobResult:
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


def _predecessor_path(status: PlanningStatus) -> tuple[PlanningStatus, ...]:
    if status in {PlanningStatus.NEEDS_INPUT, PlanningStatus.FAILED}:
        return (PlanningStatus.NORMALIZING,)
    return (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.ENRICHING_ROUTES,
        PlanningStatus.VALIDATING,
    )


async def _publish(
    repository: InMemoryPlanningJobRepository,
    clock: ManualClock,
    response: TripPlanResponse,
) -> PlanningJob:
    job = (await repository.get_or_create(_request())).job
    for status in _predecessor_path(response.status):
        job = await repository.advance(job.job_id, status, expected_version=job.version)
    clock.value = response.updated_at
    return await repository.record_result(
        job.job_id,
        _result(response),
        expected_version=job.version,
    )


@pytest.mark.parametrize("case_file", CASE_FILES)
def test_get_returns_each_frozen_terminal_resource_exactly(case_file: str) -> None:
    expected = _response(case_file)
    clock = ManualClock(expected.created_at)
    repository = InMemoryPlanningJobRepository(
        clock=clock,
        id_factory=SequentialIds(expected.job_id, expected.trace_id),
    )
    stored = asyncio.run(_publish(repository, clock, expected))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.get(f"/api/trip-plans/{stored.job_id}")

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_duplicate_post_returns_the_existing_terminal_resource() -> None:
    expected = _response("synthetic_hangzhou_ready.json")
    clock = ManualClock(expected.created_at)
    repository = InMemoryPlanningJobRepository(
        clock=clock,
        id_factory=SequentialIds(expected.job_id, expected.trace_id),
    )
    asyncio.run(_publish(repository, clock, expected))
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post("/api/trip-plans", json=payload)

    assert response.status_code == 202
    assert response.json() == expected.model_dump(mode="json")


def test_retry_clears_stale_partial_result_before_next_attempt() -> None:
    terminal = _response("synthetic_hangzhou_partial.json")
    clock = ManualClock(terminal.created_at)
    repository = InMemoryPlanningJobRepository(
        clock=clock,
        id_factory=SequentialIds(terminal.job_id, terminal.trace_id, RETRY_TRACE_ID),
    )
    asyncio.run(_publish(repository, clock, terminal))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.post(f"/api/trip-plans/{terminal.job_id}/retry")

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "normalizing"
    assert body["attempt"] == 2
    assert body["trace_id"] == str(RETRY_TRACE_ID)
    assert body["resolved_destination"] is None
    assert body["plan"] is None
    assert body["violations"] == []
    assert body["warnings"] == []
    assert body["uncertainties"] == []
    assert body["sources"] == []
    assert body["errors"] == []


def test_advance_cannot_create_a_terminal_job_without_a_result() -> None:
    expected = _response("synthetic_hangzhou_partial.json")
    clock = ManualClock(expected.created_at)
    repository = InMemoryPlanningJobRepository(
        clock=clock,
        id_factory=SequentialIds(expected.job_id, expected.trace_id),
    )

    async def attempt() -> tuple[PlanningJob, PlanningJobRepositoryError]:
        job = (await repository.get_or_create(_request())).job
        for status in (PlanningStatus.NORMALIZING, PlanningStatus.COLLECTING):
            job = await repository.advance(job.job_id, status, expected_version=job.version)
        with pytest.raises(PlanningJobRepositoryError) as raised:
            await repository.advance(
                job.job_id,
                PlanningStatus.PARTIAL,
                expected_version=job.version,
                retryable=True,
            )
        return await repository.get(job.job_id), raised.value

    stored, error = asyncio.run(attempt())

    assert error.code is PlanningJobRepositoryErrorCode.RESULT_REQUIRED
    assert stored.status is PlanningStatus.COLLECTING
    assert stored.result is None


@pytest.mark.parametrize(
    ("case_file", "replacement"),
    (
        ("synthetic_hangzhou_ready.json", {"plan": None}),
        ("synthetic_hangzhou_failed.json", {"errors": ()}),
        ("synthetic_hangzhou_needs_input.json", {"retryable": True}),
        ("synthetic_hangzhou_conflict.json", {"violations": (), "errors": ()}),
        (
            "synthetic_hangzhou_partial.json",
            {"warnings": (), "uncertainties": (), "errors": (), "violations": ()},
        ),
    ),
)
def test_terminal_result_contract_rejects_forged_field_combinations(
    case_file: str,
    replacement: dict[str, object],
) -> None:
    valid = _result(_response(case_file))

    with pytest.raises(ValueError) as raised:
        replace(valid, **cast(Any, replacement))

    assert "result_" in str(raised.value)


def test_result_rejects_sensitive_error_text_without_echoing_it() -> None:
    valid = _result(_response("synthetic_hangzhou_failed.json"))
    unsafe = ApiError(
        code=ApiErrorCode.INTERNAL_ERROR,
        message="Authorization: Bearer secret=do-not-expose",
        retryable=True,
    )

    with pytest.raises(ValueError) as raised:
        replace(valid, errors=(unsafe,))

    assert str(raised.value) == "result_text_unsafe"
    assert "do-not-expose" not in str(raised.value)


def test_result_rejects_dangling_source_references() -> None:
    valid = _result(_response("synthetic_hangzhou_ready.json"))

    with pytest.raises(ValueError) as raised:
        replace(valid, sources=())

    assert str(raised.value) == "result_source_reference_invalid"


def test_record_result_rejects_request_mismatch_and_stale_version_without_mutation() -> None:
    expected = _response("synthetic_hangzhou_ready.json")
    clock = ManualClock(expected.created_at)
    repository = InMemoryPlanningJobRepository(
        clock=clock,
        id_factory=SequentialIds(expected.job_id, expected.trace_id),
    )

    async def attempt() -> tuple[PlanningJobRepositoryErrorCode, PlanningJobRepositoryErrorCode]:
        job = (await repository.get_or_create(_request())).job
        for status in _predecessor_path(expected.status):
            job = await repository.advance(job.job_id, status, expected_version=job.version)
        plan = expected.plan
        assert plan is not None
        mismatched_plan = plan.model_copy(update={"start_date": plan.start_date.replace(day=16)})
        mismatched = replace(_result(expected), plan=mismatched_plan)
        with pytest.raises(PlanningJobRepositoryError) as mismatch_error:
            await repository.record_result(
                job.job_id,
                mismatched,
                expected_version=job.version,
            )
        with pytest.raises(PlanningJobRepositoryError) as version_error:
            await repository.record_result(
                job.job_id,
                _result(expected),
                expected_version=job.version - 1,
            )
        assert (await repository.get(job.job_id)).result is None
        return mismatch_error.value.code, version_error.value.code

    mismatch_code, version_code = asyncio.run(attempt())

    assert mismatch_code is PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH
    assert version_code is PlanningJobRepositoryErrorCode.VERSION_CONFLICT
