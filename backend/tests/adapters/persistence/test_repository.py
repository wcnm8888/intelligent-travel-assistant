"""Offline contract tests for the SQLite planning-job repository adapter."""

from __future__ import annotations

import ast
import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
)
from intelligent_travel_assistant.application.repositories import (
    AcceptanceEvidence,
    AcceptanceRecord,
    AcceptanceStatus,
    PlanningJob,
    PlanningJobRepository,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
)
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    SourceRecord,
    TripPlanRequest,
    TripPlanResponse,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures"
REPOSITORY_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "intelligent_travel_assistant"
    / "adapters"
    / "persistence"
    / "repository.py"
)
JOB_ID = UUID("a0000000-0000-4000-8000-000000000001")
TRACE_ID_ONE = UUID("b0000000-0000-4000-8000-000000000001")
TRACE_ID_TWO = UUID("b0000000-0000-4000-8000-000000000002")
ACCEPTANCE_ID = UUID("c0000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 16, 2, tzinfo=UTC)


class ManualClock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self) -> None:
        self.value += timedelta(seconds=1)


class SequentialIds:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _result(name: str) -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / f"synthetic_hangzhou_{name}.json").read_text(encoding="utf-8")
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


def _open_database(path: Path) -> SqliteDatabase:
    database = SqliteDatabase(SqliteConnectionConfig(path=path))
    MigrationRunner().run(database.open())
    return database


def _repository(
    database: SqliteDatabase,
    clock: ManualClock,
    *identifiers: UUID,
) -> SqlitePlanningJobRepository:
    factory: Callable[[], UUID] = SequentialIds(*identifiers)
    return SqlitePlanningJobRepository(database, clock=clock, id_factory=factory)


def _create_job(repository: SqlitePlanningJobRepository) -> PlanningJob:
    return asyncio.run(repository.get_or_create(_request())).job


def _advance_for_result(
    repository: SqlitePlanningJobRepository,
    clock: ManualClock,
    job: PlanningJob,
    status: PlanningStatus,
) -> PlanningJob:
    paths = {
        PlanningStatus.NEEDS_INPUT: (PlanningStatus.NORMALIZING,),
        PlanningStatus.FAILED: (PlanningStatus.NORMALIZING,),
        PlanningStatus.PARTIAL: (
            PlanningStatus.NORMALIZING,
            PlanningStatus.COLLECTING,
        ),
        PlanningStatus.READY: (
            PlanningStatus.NORMALIZING,
            PlanningStatus.COLLECTING,
            PlanningStatus.PLANNING,
            PlanningStatus.VALIDATING,
        ),
        PlanningStatus.CONFLICT: (
            PlanningStatus.NORMALIZING,
            PlanningStatus.COLLECTING,
            PlanningStatus.PLANNING,
            PlanningStatus.VALIDATING,
        ),
    }
    for target in paths[status]:
        clock.advance()
        job = asyncio.run(repository.advance(job.job_id, target, expected_version=job.version))
    return job


def test_get_or_create_is_idempotent_and_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    clock = ManualClock()
    database = _open_database(path)
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE)
    try:
        first = asyncio.run(repository.get_or_create(_request()))
        second = asyncio.run(repository.get_or_create(_request()))
        assert first.created is True
        assert second.created is False
        assert second.job == first.job
        assert isinstance(repository, PlanningJobRepository)
    finally:
        database.close()

    reopened = _open_database(path)
    try:
        restored = asyncio.run(SqlitePlanningJobRepository(reopened).get(first.job.job_id))
        assert restored == first.job
        row = reopened.connection.execute(
            "SELECT expires_at FROM planning_jobs WHERE job_id = ?",
            (str(first.job.job_id),),
        ).fetchone()
        assert row is not None
        assert datetime.fromisoformat(row[0]) == NOW + timedelta(days=30)
    finally:
        reopened.close()


def test_idempotency_conflict_is_stable_and_safe(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "idempotency.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:
        request = _request()
        asyncio.run(repository.get_or_create(request))
        changed = request.model_copy(update={"city": "苏州"})

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(repository.get_or_create(changed))

        assert raised.value.code is PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT
        assert str(request.client_request_id) not in str(raised.value)
        assert database.connection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone()[0] == 1
    finally:
        database.close()


def test_concurrent_same_request_has_one_creator(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "concurrent-create.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:

        async def create_concurrently() -> list[PlanningJobReservation]:
            return await asyncio.gather(*(repository.get_or_create(_request()) for _ in range(20)))

        reservations = asyncio.run(create_concurrently())

        assert sum(reservation.created for reservation in reservations) == 1
        assert {reservation.job.job_id for reservation in reservations} == {JOB_ID}
        assert database.connection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone()[0] == 1
        assert (
            database.connection.execute("SELECT COUNT(*) FROM planning_attempts").fetchone()[0] == 1
        )
    finally:
        database.close()


@pytest.mark.parametrize(
    ("fixture_name", "status"),
    (
        ("ready", PlanningStatus.READY),
        ("partial", PlanningStatus.PARTIAL),
        ("conflict", PlanningStatus.CONFLICT),
        ("needs_input", PlanningStatus.NEEDS_INPUT),
        ("failed", PlanningStatus.FAILED),
    ),
)
def test_terminal_results_round_trip_through_typed_hydration(
    tmp_path: Path,
    fixture_name: str,
    status: PlanningStatus,
) -> None:
    path = tmp_path / f"{fixture_name}.sqlite3"
    clock = ManualClock()
    database = _open_database(path)
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE)
    expected_result = _result(fixture_name)
    try:
        job = _advance_for_result(repository, clock, _create_job(repository), status)
        clock.advance()
        stored = asyncio.run(
            repository.record_result(
                job.job_id,
                expected_result,
                expected_version=job.version,
            )
        )
        assert stored.status is status
        assert stored.result == expected_result
    finally:
        database.close()

    reopened = _open_database(path)
    try:
        restored = asyncio.run(SqlitePlanningJobRepository(reopened).get(JOB_ID))
        assert restored == stored
        assert restored.result == expected_result
        if status is PlanningStatus.PARTIAL:
            assert restored.result is not None
            assert restored.result.plan is not None
            unknown_costs = tuple(
                item
                for item in restored.result.plan.budget_summary.cost_items
                if item.confidence.value == "unknown"
            )
            assert unknown_costs
            assert all(item.amount is None for item in unknown_costs)
    finally:
        reopened.close()


def test_expected_version_prevents_stale_cross_connection_update(tmp_path: Path) -> None:
    path = tmp_path / "version.sqlite3"
    first_database = _open_database(path)
    second_database = _open_database(path)
    first = _repository(first_database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    second = SqlitePlanningJobRepository(second_database, clock=ManualClock())
    try:
        created = _create_job(first)
        stale = asyncio.run(second.get(created.job_id))
        updated = asyncio.run(
            first.advance(
                created.job_id,
                PlanningStatus.NORMALIZING,
                expected_version=created.version,
            )
        )

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(
                second.advance(
                    stale.job_id,
                    PlanningStatus.NORMALIZING,
                    expected_version=stale.version,
                )
            )

        assert raised.value.code is PlanningJobRepositoryErrorCode.VERSION_CONFLICT
        assert asyncio.run(second.get(created.job_id)) == updated
    finally:
        second_database.close()
        first_database.close()


def test_concurrent_updates_have_one_winner_and_one_version_conflict(
    tmp_path: Path,
) -> None:
    database = _open_database(tmp_path / "concurrent-update.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:
        created = _create_job(repository)

        async def update_concurrently() -> tuple[object, object]:
            first, second = await asyncio.gather(
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
            return first, second

        outcomes = asyncio.run(update_concurrently())

        assert sum(isinstance(outcome, PlanningJob) for outcome in outcomes) == 1
        errors = [
            outcome for outcome in outcomes if isinstance(outcome, PlanningJobRepositoryError)
        ]
        assert len(errors) == 1
        assert errors[0].code is PlanningJobRepositoryErrorCode.VERSION_CONFLICT
        restored = asyncio.run(repository.get(created.job_id))
        assert restored.status is PlanningStatus.NORMALIZING
        assert restored.version == created.version + 1
    finally:
        database.close()


def test_retry_preserves_old_attempt_and_appends_plan_version(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "retry.sqlite3")
    clock = ManualClock()
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE, TRACE_ID_TWO)
    try:
        job = _advance_for_result(
            repository,
            clock,
            _create_job(repository),
            PlanningStatus.PARTIAL,
        )
        job = asyncio.run(
            repository.record_result(
                job.job_id,
                _result("partial"),
                expected_version=job.version,
            )
        )
        first_version = job.version
        clock.advance()
        job = asyncio.run(repository.retry(job.job_id, expected_version=job.version))
        assert job.attempt == 2
        assert job.trace_id == TRACE_ID_TWO
        assert job.status is PlanningStatus.NORMALIZING
        assert job.result is None
        assert job.version == first_version + 1

        for target in (
            PlanningStatus.COLLECTING,
            PlanningStatus.PLANNING,
            PlanningStatus.VALIDATING,
        ):
            clock.advance()
            job = asyncio.run(repository.advance(job.job_id, target, expected_version=job.version))
        job = asyncio.run(
            repository.record_result(
                job.job_id,
                _result("ready"),
                expected_version=job.version,
            )
        )

        attempts = database.connection.execute(
            "SELECT attempt, trace_id FROM planning_attempts WHERE job_id = ? ORDER BY attempt",
            (str(job.job_id),),
        ).fetchall()
        versions = database.connection.execute(
            """
            SELECT version_number, attempt
            FROM plan_versions
            WHERE job_id = ?
            ORDER BY version_number
            """,
            (str(job.job_id),),
        ).fetchall()
        assert [tuple(row) for row in attempts] == [
            (1, str(TRACE_ID_ONE)),
            (2, str(TRACE_ID_TWO)),
        ]
        assert [tuple(row) for row in versions] == [(1, 1), (2, 2)]
        assert job.result == _result("ready")
    finally:
        database.close()


def test_result_write_rolls_back_when_source_identity_collides(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "rollback.sqlite3")
    clock = ManualClock()
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE, TRACE_ID_TWO)
    try:
        job = _advance_for_result(
            repository,
            clock,
            _create_job(repository),
            PlanningStatus.PARTIAL,
        )
        partial = _result("partial")
        job = asyncio.run(
            repository.record_result(job.job_id, partial, expected_version=job.version)
        )
        job = asyncio.run(repository.retry(job.job_id, expected_version=job.version))
        job = asyncio.run(
            repository.advance(
                job.job_id,
                PlanningStatus.COLLECTING,
                expected_version=job.version,
            )
        )
        version_before = job.version

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(
                repository.record_result(
                    job.job_id,
                    partial,
                    expected_version=job.version,
                )
            )

        assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
        restored = asyncio.run(repository.get(job.job_id))
        assert restored.status is PlanningStatus.COLLECTING
        assert restored.version == version_before
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?",
                (str(job.job_id),),
            ).fetchone()[0]
            == 1
        )
    finally:
        database.close()


def test_private_material_is_rejected_before_any_persistence(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "privacy.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:
        request = _request()
        unsafe_preferences = request.preferences.model_copy(
            update={"free_text": "api_key=do-not-store-this"}
        )
        unsafe_request = request.model_copy(update={"preferences": unsafe_preferences})

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(repository.get_or_create(unsafe_request))

        assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
        assert database.connection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone()[0] == 0
    finally:
        database.close()


def test_private_source_url_rolls_back_terminal_result(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "source-privacy.sqlite3")
    clock = ManualClock()
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE)
    try:
        result = _result("partial")
        source_payload = result.sources[0].model_dump(mode="json")
        source_payload["reference_url"] = "https://example.test/data?token=do-not-store"
        unsafe_source = SourceRecord.model_validate(source_payload)
        unsafe_result = replace(
            result,
            sources=(unsafe_source, *result.sources[1:]),
        )
        job = _advance_for_result(
            repository,
            clock,
            _create_job(repository),
            PlanningStatus.PARTIAL,
        )

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(
                repository.record_result(
                    job.job_id,
                    unsafe_result,
                    expected_version=job.version,
                )
            )

        assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
        assert asyncio.run(repository.get(job.job_id)).status is PlanningStatus.COLLECTING
        assert database.connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0] == 0
    finally:
        database.close()


def test_acceptance_record_round_trips_as_safe_structured_sqlite_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "acceptance.sqlite3"
    database = _open_database(path)
    clock = ManualClock()
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE)
    try:
        job = _advance_for_result(
            repository,
            clock,
            _create_job(repository),
            PlanningStatus.PARTIAL,
        )
        clock.advance()
        job = asyncio.run(
            repository.record_result(
                job.job_id,
                _result("partial"),
                expected_version=job.version,
            )
        )
        record = AcceptanceRecord(
            acceptance_id=ACCEPTANCE_ID,
            job_id=job.job_id,
            attempt=job.attempt,
            plan_version=1,
            case_id="f002.step5.partial.persistence",
            status=AcceptanceStatus.PARTIAL,
            observed_at=clock.value,
            environment="local_test",
            evidence=AcceptanceEvidence(
                check_codes=("partial_preserved", "unknown_amount_null"),
                limitation_codes=("provider_not_called",),
            ),
        )

        assert asyncio.run(repository.record_acceptance(record)) == record
        row = database.connection.execute(
            "SELECT * FROM acceptance_records WHERE acceptance_id = ?",
            (str(record.acceptance_id),),
        ).fetchone()
        assert row is not None
        assert row[1:8] == (
            str(job.job_id),
            1,
            1,
            "f002.step5.partial.persistence",
            "partial",
            clock.value.isoformat(),
            "local_test",
        )
        assert json.loads(row[8]) == {
            "check_codes": ["partial_preserved", "unknown_amount_null"],
            "limitation_codes": ["provider_not_called"],
        }
        serialized = row[8].lower()
        for forbidden in ("authorization", "cookie", "private_key", "prompt", "token"):
            assert forbidden not in serialized
    finally:
        database.close()


def test_acceptance_record_rejects_invalid_plan_version_and_private_material(
    tmp_path: Path,
) -> None:
    database = _open_database(tmp_path / "acceptance-invalid.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:
        job = _create_job(repository)
        with pytest.raises(ValueError, match="acceptance_evidence_invalid"):
            AcceptanceEvidence(check_codes=("authorization:bearer-secret",))
        record = AcceptanceRecord(
            acceptance_id=ACCEPTANCE_ID,
            job_id=job.job_id,
            attempt=job.attempt,
            plan_version=1,
            case_id="f002.step5.invalid_version",
            status=AcceptanceStatus.NOT_RUN,
            observed_at=NOW,
            environment="local_test",
            evidence=AcceptanceEvidence(check_codes=("not_run",)),
        )

        with pytest.raises(PlanningJobRepositoryError) as invalid:
            asyncio.run(repository.record_acceptance(record))

        assert invalid.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
        assert (
            database.connection.execute("SELECT COUNT(*) FROM acceptance_records").fetchone()[0]
            == 0
        )
    finally:
        database.close()


def test_delete_cascades_job_owned_versions_sources_and_acceptance(
    tmp_path: Path,
) -> None:
    database = _open_database(tmp_path / "delete.sqlite3")
    clock = ManualClock()
    repository = _repository(database, clock, JOB_ID, TRACE_ID_ONE)
    try:
        job = _advance_for_result(
            repository,
            clock,
            _create_job(repository),
            PlanningStatus.PARTIAL,
        )
        clock.advance()
        job = asyncio.run(
            repository.record_result(job.job_id, _result("partial"), expected_version=job.version)
        )
        acceptance = AcceptanceRecord(
            acceptance_id=ACCEPTANCE_ID,
            job_id=job.job_id,
            attempt=job.attempt,
            plan_version=1,
            case_id="f002.step5.delete",
            status=AcceptanceStatus.PASS,
            observed_at=clock.value,
            environment="local_test",
            evidence=AcceptanceEvidence(check_codes=("cascade_verified",)),
        )
        asyncio.run(repository.record_acceptance(acceptance))

        asyncio.run(repository.delete(job.job_id))

        for table in (
            "planning_jobs",
            "planning_attempts",
            "plan_versions",
            "source_records",
            "plan_version_sources",
            "acceptance_records",
        ):
            assert database.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        with pytest.raises(PlanningJobRepositoryError) as missing:
            asyncio.run(repository.get(job.job_id))
        assert missing.value.code is PlanningJobRepositoryErrorCode.JOB_NOT_FOUND
    finally:
        database.close()


def test_cleanup_expired_honors_exact_boundary_limit_and_retains_newer_jobs(
    tmp_path: Path,
) -> None:
    database = _open_database(tmp_path / "cleanup.sqlite3")
    repository = _repository(
        database,
        ManualClock(),
        JOB_ID,
        TRACE_ID_ONE,
        UUID("a0000000-0000-4000-8000-000000000002"),
        TRACE_ID_TWO,
        UUID("a0000000-0000-4000-8000-000000000003"),
        UUID("b0000000-0000-4000-8000-000000000003"),
    )
    try:
        first = _create_job(repository)
        second_request = _request().model_copy(
            update={"client_request_id": UUID("11111111-1111-4111-8111-111111111112")}
        )
        third_request = _request().model_copy(
            update={"client_request_id": UUID("11111111-1111-4111-8111-111111111113")}
        )
        second = asyncio.run(repository.get_or_create(second_request)).job
        third = asyncio.run(repository.get_or_create(third_request)).job
        database.connection.execute(
            "UPDATE planning_jobs SET expires_at = ? WHERE job_id IN (?, ?)",
            (NOW.isoformat(), str(first.job_id), str(second.job_id)),
        )
        database.connection.execute(
            "UPDATE planning_jobs SET expires_at = ? WHERE job_id = ?",
            ((NOW + timedelta(microseconds=1)).isoformat(), str(third.job_id)),
        )

        assert asyncio.run(repository.cleanup_expired(NOW, limit=1)) == 1
        assert asyncio.run(repository.cleanup_expired(NOW, limit=1)) == 1
        assert asyncio.run(repository.cleanup_expired(NOW, limit=1)) == 0
        assert asyncio.run(repository.get(third.job_id)) == third
    finally:
        database.close()


def test_corrupt_json_fails_closed_without_leaking_database_details(tmp_path: Path) -> None:
    database = _open_database(tmp_path / "corrupt.sqlite3")
    repository = _repository(database, ManualClock(), JOB_ID, TRACE_ID_ONE)
    try:
        job = _create_job(repository)
        database.connection.execute(
            "UPDATE planning_jobs SET request_json = ? WHERE job_id = ?",
            ("{not-json", str(job.job_id)),
        )

        with pytest.raises(PlanningJobRepositoryError) as raised:
            asyncio.run(repository.get(job.job_id))

        assert raised.value.code is PlanningJobRepositoryErrorCode.RESULT_INVALID
        assert "sqlite" not in str(raised.value).lower()
        assert str(tmp_path) not in str(raised.value)
    finally:
        database.close()


def test_repository_source_has_no_provider_network_or_environment_access() -> None:
    tree = ast.parse(
        REPOSITORY_SOURCE.read_text(encoding="utf-8"),
        filename=str(REPOSITORY_SOURCE),
    )
    forbidden_roots = {
        "dotenv",
        "fastapi",
        "httpx",
        "os",
        "requests",
        "socket",
        "urllib",
    }
    observed: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = (node.module,)
        else:
            modules = ()
        observed.extend(module for module in modules if module.split(".", 1)[0] in forbidden_roots)

    assert observed == []
    assert ".env.local" not in REPOSITORY_SOURCE.read_text(encoding="utf-8")
