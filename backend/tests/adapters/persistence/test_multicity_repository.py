"""F-004B1 V3 typed JSON round-trip on unchanged SQLite schema version 2."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from tests.application.test_multicity_planning_job_repository import request, result

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobResultV3,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanRequestV3,
    TripPlanV3,
)

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)


def open_repository(path: Path) -> tuple[SqliteDatabase, SqlitePlanningJobRepository]:
    database = SqliteDatabase(SqliteConnectionConfig(path=path))
    MigrationRunner().run(database.open())
    return database, SqlitePlanningJobRepository(database, clock=lambda: NOW)


async def advance_to_validating(
    repository: SqlitePlanningJobRepository, job: PlanningJob
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


def test_v3_request_and_terminal_plan_survive_schema_v2_restart(tmp_path: Path) -> None:
    path = tmp_path / "multicity.sqlite3"
    database, repository = open_repository(path)

    async def publish() -> PlanningJob:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(),
            expected_version=job.version,
        )

    stored = asyncio.run(publish())
    database.close()
    restarted_database, restarted = open_repository(path)
    try:
        restored = asyncio.run(restarted.get(stored.job_id))
        migrations = restarted_database.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        request_json = restarted_database.connection.execute(
            "SELECT request_json FROM planning_jobs WHERE job_id = ?",
            (str(stored.job_id),),
        ).fetchone()[0]
    finally:
        restarted_database.close()

    assert isinstance(restored.request, TripPlanRequestV3)
    assert isinstance(restored.result, PlanningJobResultV3)
    assert isinstance(restored.result.plan, TripPlanV3)
    assert len(restored.result.resolved_destinations) == 2
    assert [row[0] for row in migrations] == [1, 2]
    with pytest.raises(ValidationError):
        TypeAdapter(TripPlanRequest | TripPlanRequestV2).validate_json(request_json)


def test_v3_retry_and_delete_use_existing_attempt_and_cascade_tables(tmp_path: Path) -> None:
    path = tmp_path / "multicity-retry-delete.sqlite3"
    database, repository = open_repository(path)

    async def exercise() -> tuple[PlanningJob, PlanningJob]:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        partial = await repository.record_result(
            job.job_id,
            result(unknown_fare=True, retryable=True),
            expected_version=job.version,
        )
        retried = await repository.retry(partial.job_id, expected_version=partial.version)
        return partial, retried

    partial, retried = asyncio.run(exercise())
    attempts = database.connection.execute(
        "SELECT attempt FROM planning_attempts WHERE job_id = ? ORDER BY attempt",
        (str(partial.job_id),),
    ).fetchall()
    asyncio.run(repository.delete(retried.job_id))
    counts = {
        table: database.connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE job_id = ?", (str(partial.job_id),)
        ).fetchone()[0]
        for table in (
            "planning_jobs",
            "planning_attempts",
            "plan_versions",
            "source_records",
        )
    }
    database.close()

    assert [row[0] for row in attempts] == [1, 2]
    assert retried.status is PlanningStatus.NORMALIZING and retried.result is None
    assert counts == {table: 0 for table in counts}


def test_v3_plan_format_corruption_fails_closed_without_rewriting_record(tmp_path: Path) -> None:
    path = tmp_path / "multicity-corrupt.sqlite3"
    database, repository = open_repository(path)

    async def publish() -> PlanningJob:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(),
            expected_version=job.version,
        )

    stored = asyncio.run(publish())
    row = database.connection.execute(
        "SELECT plan_json FROM plan_versions WHERE job_id = ? AND version_number = 1",
        (str(stored.job_id),),
    ).fetchone()
    payload = json.loads(row[0])
    payload["plan_format_version"] = "2"
    corrupted = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    database.connection.execute(
        "UPDATE plan_versions SET plan_json = ? WHERE job_id = ? AND version_number = 1",
        (corrupted, str(stored.job_id)),
    )

    try:
        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(repository.get(stored.job_id))
        unchanged = database.connection.execute(
            "SELECT plan_json FROM plan_versions WHERE job_id = ? AND version_number = 1",
            (str(stored.job_id),),
        ).fetchone()[0]
    finally:
        database.close()

    assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
    assert unchanged == corrupted


def test_v3_draft_uses_existing_thirty_day_bounded_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "multicity-cleanup.sqlite3"
    database, repository = open_repository(path)

    async def exercise() -> tuple[PlanningJob, int]:
        job = (await repository.get_or_create(request())).job
        deleted = await repository.cleanup_expired(NOW + timedelta(days=31), limit=1)
        return job, deleted

    job, deleted = asyncio.run(exercise())
    remaining = database.connection.execute(
        "SELECT COUNT(*) FROM planning_jobs WHERE job_id = ?", (str(job.job_id),)
    ).fetchone()[0]
    database.close()

    assert deleted == 1
    assert remaining == 0
