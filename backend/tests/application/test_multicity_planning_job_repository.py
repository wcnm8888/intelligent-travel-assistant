"""F-004B1 V3 repository union, fingerprint, and replan scope tests."""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.contracts.test_multicity_trip_planning_contracts import (
    request_payload,
    response_payload,
)

from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
    InMemoryReplanRepository,
)
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationError,
    ReplanApplicationRequest,
    ReplanApplicationService,
    ReplanExecutionResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobResult,
    PlanningJobResultV3,
    ReplanRecord,
    ReplanReservation,
    request_fingerprint,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    PlanningStatus,
    TripPlanRequestV3,
    TripPlanResponseV3,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    ImpactAnalysis,
    ReplanChoice,
    ReplanCommand,
)

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)
REPLAN_REQUEST_ID = UUID("f3000000-0000-4000-8000-000000000001")
BASELINE_PLAN_ID = UUID("f3000000-0000-4000-8000-000000000002")
REPLAN_ID = UUID("f3000000-0000-4000-8000-000000000003")
REPLAN_TRACE_ID = UUID("f3000000-0000-4000-8000-000000000004")
ACTIVITY_ID = UUID("f3000000-0000-4000-8000-000000000005")


def request(*, client_request_id: UUID | None = None) -> TripPlanRequestV3:
    payload = request_payload()
    if client_request_id is not None:
        payload["client_request_id"] = str(client_request_id)
    return TripPlanRequestV3.model_validate(payload)


def result(*, unknown_fare: bool = False, retryable: bool = False) -> PlanningJobResultV3:
    payload = response_payload(unknown_fare=unknown_fare)
    if retryable:
        payload["retryable"] = True
        payload["errors"] = [
            {
                "code": "provider_timeout",
                "message": "路线服务暂时超时。",
                "field": None,
                "provider": "amap",
                "retryable": True,
            }
        ]
    response = TripPlanResponseV3.model_validate(payload)
    return PlanningJobResultV3(
        response.status,
        response.resolved_destinations,
        response.plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
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


def test_v3_fingerprint_excludes_client_id_but_preserves_ordered_multicity_fields() -> None:
    first = request()
    same = request(client_request_id=UUID("f3000000-0000-4000-8000-000000000010"))
    changed_payload = copy.deepcopy(request_payload())
    segments = changed_payload["intercity_segments"]
    assert isinstance(segments, list) and isinstance(segments[0], dict)
    segments[0]["departure_station"] = "杭州东站"
    changed = TripPlanRequestV3.model_validate(changed_payload)

    assert request_fingerprint(first) == request_fingerprint(same)
    assert request_fingerprint(first) != request_fingerprint(changed)


def test_memory_repository_round_trips_v3_request_result_retry_and_delete() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def scenario() -> tuple[PlanningJob, PlanningJob]:
        created = await repository.get_or_create(request())
        validating = await advance_to_validating(repository, created.job)
        partial = await repository.record_result(
            validating.job_id,
            result(unknown_fare=True, retryable=True),
            expected_version=validating.version,
        )
        retried = await repository.retry(partial.job_id, expected_version=partial.version)
        await repository.delete(retried.job_id)
        return partial, retried

    partial, retried = asyncio.run(scenario())

    assert isinstance(partial.request, TripPlanRequestV3)
    assert isinstance(partial.result, PlanningJobResultV3)
    assert partial.result.plan is not None and partial.result.plan.plan_format_version == "3"
    assert retried.attempt == 2 and retried.result is None


def test_v3_job_rejects_a_legacy_terminal_result_even_when_plan_is_absent() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    legacy_failed = PlanningJobResult(
        status=PlanningStatus.FAILED,
        resolved_destination=None,
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(
            ApiError(
                code=ApiErrorCode.INTERNAL_ERROR,
                message="规划失败。",
                retryable=False,
            ),
        ),
        retryable=False,
    )

    async def scenario() -> tuple[PlanningJobRepositoryErrorCode, PlanningJob]:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        with pytest.raises(PlanningJobRepositoryError) as raised:
            await repository.record_result(
                job.job_id,
                legacy_failed,
                expected_version=job.version,
            )
        return raised.value.code, await repository.get(job.job_id)

    code, stored = asyncio.run(scenario())
    assert code is PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH
    assert stored.status is PlanningStatus.VALIDATING and stored.result is None


class RecordingReplanRepository(InMemoryReplanRepository):
    def __init__(self) -> None:
        identifiers = iter((REPLAN_ID, REPLAN_TRACE_ID))
        super().__init__(clock=lambda: NOW, id_factory=identifiers.__next__)
        self.reserve_calls = 0
        self.lookup_calls = 0
        self.decision_calls = 0

    async def reserve(
        self,
        job_id: UUID,
        replan_request_id: UUID,
        command: ReplanCommand,
        *,
        baseline_plan_id: UUID,
        baseline_plan_version: int | None = None,
        expected_job_version: int,
        trace_id: UUID | None = None,
    ) -> ReplanReservation:
        self.reserve_calls += 1
        return await super().reserve(
            job_id,
            replan_request_id,
            command,
            baseline_plan_id=baseline_plan_id,
            baseline_plan_version=baseline_plan_version,
            expected_job_version=expected_job_version,
            trace_id=trace_id,
        )

    async def get(self, job_id: UUID, replan_id: UUID) -> ReplanRecord:
        self.lookup_calls += 1
        return await super().get(job_id, replan_id)

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        self.decision_calls += 1
        return await super().decide(
            job_id,
            replan_id,
            choice,
            expected_replan_version=expected_replan_version,
            expected_job_version=expected_job_version,
        )


class ForbiddenReplanExecutor:
    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        raise AssertionError("V3 replan must not analyze")

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        raise AssertionError("V3 replan must not execute")


def test_v3_replan_create_decide_and_execute_fail_before_reserve_or_lookup() -> None:
    planning = InMemoryPlanningJobRepository(clock=lambda: NOW)
    replans = RecordingReplanRepository()
    service = ReplanApplicationService(planning, replans, ForbiddenReplanExecutor())
    command = AdjustActivityTime(ACTIVITY_ID, datetime.min.time(), datetime.max.time())

    async def scenario() -> None:
        job = (await planning.get_or_create(request())).job
        application_request = ReplanApplicationRequest(
            job.job_id,
            REPLAN_REQUEST_ID,
            BASELINE_PLAN_ID,
            command,
        )
        with pytest.raises(ReplanApplicationError, match="replan_scope_not_supported"):
            await service.create(application_request)
        with pytest.raises(ReplanApplicationError, match="replan_scope_not_supported"):
            await service.decide(
                job.job_id,
                REPLAN_ID,
                ReplanChoice.APPROVE,
                expected_replan_version=1,
            )
        with pytest.raises(ReplanApplicationError, match="replan_scope_not_supported"):
            await service.execute(job.job_id, REPLAN_ID)

    asyncio.run(scenario())
    assert replans.reserve_calls == 0
    assert replans.lookup_calls == 0
    assert replans.decision_calls == 0
