"""Offline execution-boundary tests for browser-loop synthetic jobs."""

import asyncio
import json
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.fakes import SyntheticPlanningJobExecutor
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.repositories import PlanningJobResult
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _result(case_file: str) -> PlanningJobResult:
    payload = json.loads((FIXTURE_ROOT / case_file).read_text(encoding="utf-8"))["response"]
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


@pytest.mark.parametrize(
    ("case_file", "expected_history"),
    [
        (
            "synthetic_hangzhou_ready.json",
            (
                PlanningStatus.DRAFT,
                PlanningStatus.NORMALIZING,
                PlanningStatus.COLLECTING,
                PlanningStatus.PLANNING,
                PlanningStatus.ENRICHING_ROUTES,
                PlanningStatus.VALIDATING,
                PlanningStatus.READY,
            ),
        ),
        (
            "synthetic_hangzhou_partial.json",
            (
                PlanningStatus.DRAFT,
                PlanningStatus.NORMALIZING,
                PlanningStatus.COLLECTING,
                PlanningStatus.PLANNING,
                PlanningStatus.ENRICHING_ROUTES,
                PlanningStatus.VALIDATING,
                PlanningStatus.PARTIAL,
            ),
        ),
        (
            "synthetic_hangzhou_conflict.json",
            (
                PlanningStatus.DRAFT,
                PlanningStatus.NORMALIZING,
                PlanningStatus.COLLECTING,
                PlanningStatus.PLANNING,
                PlanningStatus.ENRICHING_ROUTES,
                PlanningStatus.VALIDATING,
                PlanningStatus.CONFLICT,
            ),
        ),
        (
            "synthetic_hangzhou_needs_input.json",
            (
                PlanningStatus.DRAFT,
                PlanningStatus.NORMALIZING,
                PlanningStatus.NEEDS_INPUT,
            ),
        ),
        (
            "synthetic_hangzhou_failed.json",
            (
                PlanningStatus.DRAFT,
                PlanningStatus.NORMALIZING,
                PlanningStatus.COLLECTING,
                PlanningStatus.PLANNING,
                PlanningStatus.FAILED,
            ),
        ),
    ],
)
def test_synthetic_executor_publishes_each_frozen_terminal_case(
    case_file: str,
    expected_history: tuple[PlanningStatus, ...],
) -> None:
    async def scenario() -> tuple[PlanningStatus, tuple[PlanningStatus, ...]]:
        repository = InMemoryPlanningJobRepository()
        job = (await repository.get_or_create(_request())).job
        executor = SyntheticPlanningJobExecutor(repository, _result(case_file))

        await executor.execute(job.job_id)
        terminal = await repository.get(job.job_id)
        return terminal.status, executor.histories[job.job_id]

    status, history = asyncio.run(scenario())

    assert status.value in case_file
    assert history == expected_history


def test_synthetic_executor_replays_retryable_partial_on_the_same_job() -> None:
    async def scenario() -> tuple[int, UUID, UUID, PlanningStatus]:
        repository = InMemoryPlanningJobRepository()
        job = (await repository.get_or_create(_request())).job
        executor = SyntheticPlanningJobExecutor(
            repository,
            _result("synthetic_hangzhou_partial.json"),
        )
        await executor.execute(job.job_id)
        first = await repository.get(job.job_id)
        await repository.retry(job.job_id, expected_version=first.version)
        await executor.execute(job.job_id)
        second = await repository.get(job.job_id)
        return second.attempt, first.trace_id, second.trace_id, second.status

    attempt, first_trace, second_trace, status = asyncio.run(scenario())

    assert attempt == 2
    assert second_trace != first_trace
    assert status is PlanningStatus.PARTIAL
