"""F-004C V4 fingerprint, typed Repository, SQLite v2, and replan guards."""

from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from tests.application.test_multicity_planning_job_repository import (
    ACTIVITY_ID,
    BASELINE_PLAN_ID,
    REPLAN_ID,
    REPLAN_REQUEST_ID,
    ForbiddenReplanExecutor,
    RecordingReplanRepository,
)
from tests.contracts.test_booked_rail_trip_planning_contracts import (
    request_payload,
    response_payload,
)
from tests.contracts.test_multicity_trip_planning_contracts import (
    response_payload as v3_response_payload,
)

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationError,
    ReplanApplicationRequest,
    ReplanApplicationService,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobResultV3,
    PlanningJobResultV4,
    request_fingerprint,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequestV4,
    TripPlanResponseV3,
    TripPlanResponseV4,
    TripPlanV4,
)
from intelligent_travel_assistant.domain import AdjustActivityTime, ReplanChoice

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)


async def advance_to_validating(
    repository: PlanningJobRepository,
    job: PlanningJob,
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


def request(*, client_request_id: UUID | None = None) -> TripPlanRequestV4:
    payload = request_payload()
    if client_request_id is not None:
        payload["client_request_id"] = str(client_request_id)
    return TripPlanRequestV4.model_validate(payload)


def result(*, unknown_fare: bool = False, retryable: bool = False) -> PlanningJobResultV4:
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
    response = TripPlanResponseV4.model_validate(payload)
    return PlanningJobResultV4(
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


def test_v4_fingerprint_normalizes_service_number_and_excludes_client_id() -> None:
    first = request()
    same = request(client_request_id=UUID("f4000000-0000-4000-8000-000000000010"))
    changed_payload = copy.deepcopy(request_payload())
    segments = changed_payload["intercity_segments"]
    assert isinstance(segments, list) and isinstance(segments[0], dict)
    segments[0]["service_number"] = "G1235"
    changed = TripPlanRequestV4.model_validate(changed_payload)

    assert request_fingerprint(first) == request_fingerprint(same)
    assert request_fingerprint(first) != request_fingerprint(changed)


def test_memory_repository_round_trips_v4_and_rejects_cross_version_result() -> None:
    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)

    async def scenario() -> tuple[PlanningJob, PlanningJobRepositoryErrorCode]:
        created = (await repository.get_or_create(request())).job
        validating = await advance_to_validating(repository, created)
        v3_response = TripPlanResponseV3.model_validate(v3_response_payload())
        wrong = PlanningJobResultV3(
            v3_response.status,
            v3_response.resolved_destinations,
            v3_response.plan,
            v3_response.violations,
            v3_response.warnings,
            v3_response.uncertainties,
            v3_response.sources,
            v3_response.errors,
            v3_response.retryable,
        )
        with pytest.raises(PlanningJobRepositoryError) as raised:
            await repository.record_result(
                validating.job_id,
                wrong,
                expected_version=validating.version,
            )
        stored = await repository.record_result(
            validating.job_id,
            result(),
            expected_version=validating.version,
        )
        return stored, raised.value.code

    stored, code = asyncio.run(scenario())
    assert code is PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH
    assert isinstance(stored.request, TripPlanRequestV4)
    assert isinstance(stored.result, PlanningJobResultV4)
    assert isinstance(stored.result.plan, TripPlanV4)


def test_v4_schema_v2_round_trip_restart_retry_and_delete(tmp_path: Path) -> None:
    path = tmp_path / "booked-rail.sqlite3"
    database = SqliteDatabase(SqliteConnectionConfig(path=path))
    MigrationRunner().run(database.open())
    repository = SqlitePlanningJobRepository(database, clock=lambda: NOW)

    async def publish() -> PlanningJob:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(unknown_fare=True, retryable=True),
            expected_version=job.version,
        )

    stored = asyncio.run(publish())
    database.close()
    restarted_database = SqliteDatabase(SqliteConnectionConfig(path=path))
    MigrationRunner().run(restarted_database.open())
    restarted = SqlitePlanningJobRepository(restarted_database, clock=lambda: NOW)
    try:
        restored = asyncio.run(restarted.get(stored.job_id))
        retried = asyncio.run(restarted.retry(stored.job_id, expected_version=restored.version))
        migrations = restarted_database.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        asyncio.run(restarted.delete(stored.job_id))
    finally:
        restarted_database.close()

    assert isinstance(restored.request, TripPlanRequestV4)
    assert isinstance(restored.result, PlanningJobResultV4)
    assert isinstance(restored.result.plan, TripPlanV4)
    assert restored.result.plan.intercity_segments[0].service_number == "G1234"
    assert retried.attempt == 2 and retried.result is None
    assert [row[0] for row in migrations] == [1, 2]


def test_v4_replan_create_decide_execute_fail_before_repository_or_executor() -> None:
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
