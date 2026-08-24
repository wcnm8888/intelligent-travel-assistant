"""F-006 zero-call terminal behavior when required provider adapters are unavailable."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
from tests.api.test_multiday_trip_plans_api import legacy_payload, v2_payload
from tests.contracts.test_booked_rail_trip_planning_contracts import (
    request_payload as v4_payload,
)
from tests.contracts.test_multicity_trip_planning_contracts import (
    request_payload as v3_payload,
)

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    PlanningJobResultV3,
    PlanningJobResultV4,
    PlanningResult,
)
from intelligent_travel_assistant.application.services import (
    ConfigurationMissingPlanningJobExecutor,
)
from intelligent_travel_assistant.contracts import (
    ApiErrorCode,
    PlanningRequest,
    PlanningStatus,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanRequestV3,
    TripPlanRequestV4,
)

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "application"
    / "services"
    / "unavailable_planning_jobs.py"
)
SAFE_MESSAGE = "本机服务配置不完整，无法生成旅行计划。"
SAFE_DIAGNOSTIC = "required_provider_configuration_missing"


class RecordingRepository(InMemoryPlanningJobRepository):
    def __init__(self) -> None:
        super().__init__()
        self.transitions: list[PlanningStatus] = []
        self.results: list[PlanningResult] = []

    async def advance(
        self,
        job_id: UUID,
        target_status: PlanningStatus,
        *,
        expected_version: int,
        retryable: bool = False,
    ) -> PlanningJob:
        self.transitions.append(target_status)
        return await super().advance(
            job_id,
            target_status,
            expected_version=expected_version,
            retryable=retryable,
        )

    async def record_result(
        self,
        job_id: UUID,
        result: PlanningResult,
        *,
        expected_version: int,
    ) -> PlanningJob:
        self.results.append(result)
        return await super().record_result(job_id, result, expected_version=expected_version)


def _cases() -> tuple[
    tuple[str, Callable[[], PlanningRequest], type[PlanningResult]],
    ...,
]:
    return (
        ("legacy", lambda: TripPlanRequest.model_validate(legacy_payload()), PlanningJobResult),
        ("v2", lambda: TripPlanRequestV2.model_validate(v2_payload(3)), PlanningJobResult),
        ("v3", lambda: TripPlanRequestV3.model_validate(v3_payload()), PlanningJobResultV3),
        ("v4", lambda: TripPlanRequestV4.model_validate(v4_payload()), PlanningJobResultV4),
    )


@pytest.mark.parametrize(("_name", "request_factory", "result_type"), _cases())
def test_configuration_missing_executor_uses_frozen_transitions_and_typed_result(
    _name: str,
    request_factory: Callable[[], PlanningRequest],
    result_type: type[PlanningResult],
) -> None:
    repository = RecordingRepository()
    request = request_factory()
    job = asyncio.run(repository.get_or_create(request)).job

    asyncio.run(ConfigurationMissingPlanningJobExecutor(repository).execute(job.job_id))

    stored = asyncio.run(repository.get(job.job_id))
    assert repository.transitions == [PlanningStatus.NORMALIZING]
    assert stored.status is PlanningStatus.FAILED
    assert stored.version == 3
    assert stored.retryable is False
    assert isinstance(stored.result, result_type)
    assert stored.result is not None
    assert stored.result.plan is None
    assert stored.result.violations == ()
    assert stored.result.warnings == ()
    assert stored.result.uncertainties == ()
    assert stored.result.sources == ()
    assert len(stored.result.errors) == 1
    error = stored.result.errors[0]
    assert error.code is ApiErrorCode.CONFIGURATION_MISSING
    assert error.message == SAFE_MESSAGE
    assert error.diagnostic_code == SAFE_DIAGNOSTIC
    assert error.retryable is False
    if isinstance(stored.result, PlanningJobResult):
        assert stored.result.resolved_destination is None
    else:
        assert stored.result.resolved_destinations == ()


def test_configuration_missing_executor_finishes_existing_normalizing_retry() -> None:
    repository = RecordingRepository()
    job = asyncio.run(
        repository.get_or_create(TripPlanRequest.model_validate(legacy_payload()))
    ).job
    normalizing = asyncio.run(
        repository.advance(
            job.job_id,
            PlanningStatus.NORMALIZING,
            expected_version=job.version,
        )
    )
    repository.transitions.clear()

    asyncio.run(ConfigurationMissingPlanningJobExecutor(repository).execute(job.job_id))

    stored = asyncio.run(repository.get(job.job_id))
    assert normalizing.status is PlanningStatus.NORMALIZING
    assert repository.transitions == []
    assert stored.status is PlanningStatus.FAILED
    assert stored.version == normalizing.version + 1


def test_configuration_missing_executor_does_not_scan_or_backfill_other_drafts() -> None:
    repository = RecordingRepository()
    first = asyncio.run(
        repository.get_or_create(TripPlanRequest.model_validate(legacy_payload()))
    ).job
    second_request = TripPlanRequest.model_validate(
        legacy_payload() | {"client_request_id": "10000000-0000-4000-8000-000000000099"}
    )
    second = asyncio.run(repository.get_or_create(second_request)).job

    asyncio.run(ConfigurationMissingPlanningJobExecutor(repository).execute(first.job_id))

    assert asyncio.run(repository.get(first.job_id)).status is PlanningStatus.FAILED
    untouched = asyncio.run(repository.get(second.job_id))
    assert untouched.status is PlanningStatus.DRAFT
    assert untouched.version == 1
    assert untouched.result is None


def test_configuration_missing_executor_has_no_provider_agent_or_runtime_capability() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    forbidden = (
        "intelligent_travel_assistant.adapters",
        "intelligent_travel_assistant.application.planning",
        "intelligent_travel_assistant.application.ports",
        "intelligent_travel_assistant.application.tooling",
        "httpx",
        "socket",
        "urllib",
    )
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append(node.module)

    assert [item for item in imports if item.startswith(forbidden)] == []
