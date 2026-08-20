"""F-004A SQLite typed JSON hydration without migration v3."""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid5

import pytest

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
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanRequestV2,
    TripPlanResponseV2,
    TripPlanV2,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures"
NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)


def request(day_count: int = 3) -> TripPlanRequestV2:
    payload = copy.deepcopy(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8"))[
            "request"
        ]
    )
    start = date.fromisoformat(str(payload["start_date"]))
    payload["request_version"] = "2"
    payload["end_date"] = (start + timedelta(days=day_count - 1)).isoformat()
    payload["day_windows"] = [
        {"day_offset": offset, "start_time": "09:00:00", "end_time": "18:00:00"}
        for offset in range(day_count)
    ]
    return TripPlanRequestV2.model_validate(payload)


def response(
    day_count: int = 3,
    *,
    fixture: str = "ready",
    plan_id: UUID | None = None,
    source_namespace: UUID | None = None,
) -> TripPlanResponseV2:
    payload = copy.deepcopy(
        json.loads(
            (FIXTURE_ROOT / f"synthetic_hangzhou_{fixture}.json").read_text(encoding="utf-8")
        )["response"]
    )
    if source_namespace is not None:
        replacements = {
            source["source_id"]: str(uuid5(source_namespace, source["source_id"]))
            for source in payload["sources"]
        }

        def remap(value: object) -> object:
            if isinstance(value, str):
                return replacements.get(value, value)
            if isinstance(value, list):
                return [remap(item) for item in value]
            if isinstance(value, dict):
                return {key: remap(item) for key, item in value.items()}
            return value

        payload = remap(payload)
        assert isinstance(payload, dict)
    summary = payload["request_summary"]
    plan = payload["plan"]
    start = date.fromisoformat(str(summary["start_date"]))
    end = start + timedelta(days=day_count - 1)
    payload["response_version"] = "2"
    summary["request_version"] = "2"
    summary["end_date"] = end.isoformat()
    if plan is not None:
        plan["plan_format_version"] = "2"
        plan["end_date"] = end.isoformat()
        if plan_id is not None:
            plan["plan_id"] = str(plan_id)
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


def result(value: TripPlanResponseV2) -> PlanningJobResult:
    return PlanningJobResult(
        value.status,
        value.resolved_destination,
        value.plan,
        value.violations,
        value.warnings,
        value.uncertainties,
        value.sources,
        value.errors,
        value.retryable,
    )


def open_repository(path: Path) -> tuple[SqliteDatabase, SqlitePlanningJobRepository]:
    database = SqliteDatabase(SqliteConnectionConfig(path=path))
    MigrationRunner().run(database.open())
    return database, SqlitePlanningJobRepository(database, clock=lambda: NOW)


async def advance_to_validating(
    repository: SqlitePlanningJobRepository, job: PlanningJob
) -> PlanningJob:
    path = (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.ENRICHING_ROUTES,
        PlanningStatus.VALIDATING,
    )
    start = path.index(job.status) + 1 if job.status in path else 0
    for status in path[start:]:
        job = await repository.advance(job.job_id, status, expected_version=job.version)
    return job


def test_v2_draft_and_terminal_plan_survive_sqlite_restart(tmp_path: Path) -> None:
    path = tmp_path / "multiday.sqlite3"
    database, repository = open_repository(path)

    async def publish() -> PlanningJob:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(response()),
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
    finally:
        restarted_database.close()

    assert isinstance(restored.request, TripPlanRequestV2)
    assert restored.result is not None
    assert isinstance(restored.result.plan, TripPlanV2)
    assert restored.result.plan.plan_format_version == "2"
    assert len(restored.result.plan.days) == 3
    assert [row[0] for row in migrations] == [1, 2]


def test_v2_retry_appends_attempt_and_plan_version_then_survives_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiday-retry.sqlite3"
    database, repository = open_repository(path)
    first_plan_id = UUID("92000000-0000-4000-8000-000000000001")
    second_plan_id = UUID("92000000-0000-4000-8000-000000000002")

    async def publish() -> tuple[PlanningJob, PlanningJob]:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        first = await repository.record_result(
            job.job_id,
            result(response(fixture="partial", plan_id=first_plan_id)),
            expected_version=job.version,
        )
        retried = await repository.retry(first.job_id, expected_version=first.version)
        retried = await advance_to_validating(repository, retried)
        second = await repository.record_result(
            retried.job_id,
            result(
                response(
                    fixture="partial",
                    plan_id=second_plan_id,
                    source_namespace=retried.trace_id,
                )
            ),
            expected_version=retried.version,
        )
        return first, second

    first, second = asyncio.run(publish())
    database.close()

    restarted_database, restarted = open_repository(path)
    try:
        restored = asyncio.run(restarted.get(second.job_id))
        attempts = restarted_database.connection.execute(
            "SELECT attempt, trace_id FROM planning_attempts WHERE job_id = ? ORDER BY attempt",
            (str(second.job_id),),
        ).fetchall()
        plan_versions = restarted_database.connection.execute(
            "SELECT version_number, plan_id FROM plan_versions "
            "WHERE job_id = ? ORDER BY version_number",
            (str(second.job_id),),
        ).fetchall()
    finally:
        restarted_database.close()

    assert first.attempt == 1
    assert second.attempt == 2
    assert first.trace_id != second.trace_id
    assert restored.attempt == 2
    assert restored.status is PlanningStatus.PARTIAL
    assert restored.result is not None and restored.result.plan is not None
    assert restored.result.plan.plan_id == second_plan_id
    assert [(row[0], row[1]) for row in attempts] == [
        (1, str(first.trace_id)),
        (2, str(second.trace_id)),
    ]
    assert [(row[0], row[1]) for row in plan_versions] == [
        (1, str(first_plan_id)),
        (2, str(second_plan_id)),
    ]


@pytest.mark.parametrize(
    ("column", "mutate"),
    [
        ("request_json", lambda value: {**value, "request_version": "3"}),
        (
            "plan_json",
            lambda value: {
                key: item for key, item in value.items() if key != "plan_format_version"
            },
        ),
    ],
)
def test_unknown_request_version_and_plan_format_mismatch_fail_closed(
    tmp_path: Path,
    column: str,
    mutate: Callable[[dict[str, object]], dict[str, object]],
) -> None:
    path = tmp_path / f"corrupt-{column}.sqlite3"
    database, repository = open_repository(path)

    async def publish() -> PlanningJob:
        job = (await repository.get_or_create(request())).job
        job = await advance_to_validating(repository, job)
        return await repository.record_result(
            job.job_id,
            result(response()),
            expected_version=job.version,
        )

    stored = asyncio.run(publish())
    table = "planning_jobs" if column == "request_json" else "plan_versions"
    raw = database.connection.execute(
        f"SELECT {column} FROM {table} WHERE job_id = ?", (str(stored.job_id),)
    ).fetchone()[0]
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    changed = mutate(payload)
    database.connection.execute(
        f"UPDATE {table} SET {column} = ? WHERE job_id = ?",
        (json.dumps(changed, ensure_ascii=False), str(stored.job_id)),
    )

    try:
        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(repository.get(stored.job_id))
    finally:
        database.close()

    assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
