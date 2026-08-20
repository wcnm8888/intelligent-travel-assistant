"""F-004A planning repository contract for explicitly versioned requests and plans."""

from __future__ import annotations

import asyncio
import copy
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobResult,
    request_fingerprint,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanResponseV2,
    TripPlanV2,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)


def legacy_request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def v2_request(
    day_count: int = 3,
    *,
    client_request_id: UUID | None = None,
) -> TripPlanRequestV2:
    payload = copy.deepcopy(legacy_request().model_dump(mode="json"))
    start = date.fromisoformat(str(payload["start_date"]))
    payload["request_version"] = "2"
    payload["end_date"] = (start + timedelta(days=day_count - 1)).isoformat()
    payload["day_windows"] = [
        {"day_offset": offset, "start_time": "09:00:00", "end_time": "18:00:00"}
        for offset in range(day_count)
    ]
    if client_request_id is not None:
        payload["client_request_id"] = str(client_request_id)
    return TripPlanRequestV2.model_validate(payload)


def v2_response(day_count: int = 3) -> TripPlanResponseV2:
    payload = copy.deepcopy(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
            "response"
        ]
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


def result(response: TripPlanResponseV2) -> PlanningJobResult:
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


async def advance_to_validating(
    repository: InMemoryPlanningJobRepository, job: PlanningJob
) -> PlanningJob:
    for status in (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.ENRICHING_ROUTES,
        PlanningStatus.VALIDATING,
    ):
        job = await repository.advance(job.job_id, status, expected_version=job.version)
    return job


def test_legacy_fingerprint_golden_remains_byte_for_byte_stable() -> None:
    assert request_fingerprint(legacy_request()).digest == (
        "f8e8a85d192745f703d968695945c2fa4200f224d4e8ae9162a69abd57bf7edd"
    )


def test_v2_fingerprint_is_stable_and_includes_version_end_date_and_windows() -> None:
    first = v2_request(3)
    same = v2_request(3)
    longer = v2_request(4)

    assert request_fingerprint(first) == request_fingerprint(same)
    assert request_fingerprint(first) != request_fingerprint(longer)
    assert request_fingerprint(first) != request_fingerprint(legacy_request())


def test_memory_repository_round_trips_v2_request_and_terminal_plan() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def scenario() -> PlanningJob:
        created = await repository.get_or_create(v2_request())
        job = await advance_to_validating(repository, created.job)
        return await repository.record_result(
            job.job_id,
            result(v2_response()),
            expected_version=job.version,
        )

    stored = asyncio.run(scenario())

    assert isinstance(stored.request, TripPlanRequestV2)
    assert stored.result is not None
    assert isinstance(stored.result.plan, TripPlanV2)
    assert stored.result.plan.plan_format_version == "2"
    assert len(stored.result.plan.days) == 3


def test_same_client_id_across_legacy_and_v2_is_an_idempotency_conflict() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    legacy = legacy_request()
    versioned = v2_request(client_request_id=legacy.client_request_id)

    async def scenario() -> PlanningJobRepositoryErrorCode:
        await repository.get_or_create(legacy)
        with pytest.raises(PlanningJobRepositoryError) as raised:
            await repository.get_or_create(versioned)
        return raised.value.code

    assert asyncio.run(scenario()) is PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT


def test_v2_result_with_a_different_end_date_is_rejected_without_mutation() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def scenario() -> tuple[PlanningJobRepositoryErrorCode, PlanningJob]:
        created = await repository.get_or_create(v2_request(3))
        job = await advance_to_validating(repository, created.job)
        mismatched = result(v2_response(2))
        with pytest.raises(PlanningJobRepositoryError) as raised:
            await repository.record_result(
                job.job_id,
                mismatched,
                expected_version=job.version,
            )
        return raised.value.code, await repository.get(job.job_id)

    code, stored = asyncio.run(scenario())
    assert code is PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH
    assert stored.result is None
    assert stored.status is PlanningStatus.VALIDATING
