"""Offline tests for the F-002 migration runner and initial schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from intelligent_travel_assistant.adapters.persistence import (
    DEFAULT_MIGRATIONS,
    Migration,
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
)
from intelligent_travel_assistant.adapters.persistence.migrations import (
    MigrationConfigurationError,
    MigrationHistoryError,
)

JOB_ID = "00000000-0000-4000-8000-000000000001"
TRACE_ID = "00000000-0000-4000-8000-000000000002"
CLIENT_REQUEST_ID = "00000000-0000-4000-8000-000000000003"
PLAN_ID = "00000000-0000-4000-8000-000000000004"
SOURCE_ID = "00000000-0000-4000-8000-000000000005"
DECISION_ID = "00000000-0000-4000-8000-000000000006"
ACCEPTANCE_ID = "00000000-0000-4000-8000-000000000007"
FINGERPRINT = "a" * 64


def _database(path: Path) -> SqliteDatabase:
    return SqliteDatabase(SqliteConnectionConfig(path=path))


def _run_default(path: Path) -> SqliteDatabase:
    database = _database(path)
    connection = database.open()
    assert MigrationRunner().run(connection) == (1,)
    return database


def _insert_job(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO planning_jobs(
            job_id, trace_id, client_request_id, request_fingerprint, request_json,
            status, attempt, version, retryable, created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            JOB_ID,
            TRACE_ID,
            CLIENT_REQUEST_ID,
            FINGERPRINT,
            '{"city":"杭州"}',
            "draft",
            1,
            1,
            0,
            "2026-08-15T00:00:00+00:00",
            "2026-08-15T00:00:00+00:00",
            "2026-09-14T00:00:00+00:00",
        ),
    )


def test_initial_schema_is_created_and_reused(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "schema.sqlite3")
    try:
        connection = database.connection
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert table_names == {
            "schema_migrations",
            "planning_jobs",
            "planning_attempts",
            "plan_versions",
            "source_records",
            "plan_version_sources",
            "decision_records",
            "acceptance_records",
        }

        assert MigrationRunner().run(connection) == (1,)
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        assert {
            "uq_planning_jobs_client_request_id",
            "ix_planning_jobs_expires_at",
            "ix_planning_jobs_updated_at",
            "ix_planning_jobs_status",
            "ix_planning_attempts_job_attempt",
            "ix_plan_versions_job_created",
            "ix_source_records_job_freshness",
            "ix_decision_records_job_created",
            "ix_acceptance_records_job_observed",
        } <= index_names
    finally:
        database.close()


def test_schema_enforces_identity_and_status_constraints(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "constraints.sqlite3")
    try:
        connection = database.connection
        _insert_job(connection)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_job(connection)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE planning_jobs SET retryable = 2 WHERE job_id = ?",
                (JOB_ID,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE planning_jobs SET status = 'unknown' WHERE job_id = ?",
                (JOB_ID,),
            )
    finally:
        database.close()


def test_foreign_keys_and_job_cascade_cover_all_child_tables(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "cascade.sqlite3")
    try:
        connection = database.connection
        _insert_job(connection)
        connection.execute(
            """
            INSERT INTO planning_attempts(
                job_id, attempt, trace_id, status, retryable, started_at, updated_at,
                current_plan_version, result_metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                JOB_ID,
                1,
                TRACE_ID,
                "draft",
                0,
                "2026-08-15T00:00:00+00:00",
                "2026-08-15T00:00:00+00:00",
                None,
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO plan_versions(
                job_id, version_number, plan_id, attempt, trace_id, status, plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                JOB_ID,
                1,
                PLAN_ID,
                1,
                TRACE_ID,
                "ready",
                '{"plan_id":"00000000-0000-4000-8000-000000000004"}',
                "2026-08-15T00:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO source_records(
                job_id, source_id, attempt, provider, source_type, provider_record_id,
                fetched_at, valid_until, freshness, reference_url, attributions_json,
                warnings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                JOB_ID,
                SOURCE_ID,
                1,
                "system",
                "test",
                None,
                "2026-08-15T00:00:00+00:00",
                None,
                "unknown_validity",
                None,
                "[]",
                "[]",
            ),
        )
        connection.execute(
            "INSERT INTO plan_version_sources(job_id, version_number, source_id) VALUES (?, ?, ?)",
            (JOB_ID, 1, SOURCE_ID),
        )
        connection.execute(
            """
            INSERT INTO decision_records(
                decision_id, job_id, attempt, trace_id, plan_version, kind, status,
                proposal_json, validation_json, user_choice_json, created_at, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DECISION_ID,
                JOB_ID,
                1,
                TRACE_ID,
                1,
                "test",
                "validated",
                "{}",
                "{}",
                None,
                "2026-08-15T00:00:00+00:00",
                None,
            ),
        )
        connection.execute(
            """
            INSERT INTO acceptance_records(
                acceptance_id, job_id, attempt, plan_version, case_id, status,
                observed_at, environment, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ACCEPTANCE_ID,
                JOB_ID,
                1,
                1,
                "persistence-schema",
                "pass",
                "2026-08-15T00:00:00+00:00",
                "test",
                "{}",
            ),
        )

        connection.execute("DELETE FROM planning_jobs WHERE job_id = ?", (JOB_ID,))
        for table in (
            "planning_attempts",
            "plan_versions",
            "source_records",
            "plan_version_sources",
            "decision_records",
            "acceptance_records",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        database.close()


def test_migration_checksum_drift_fails_closed(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "checksum.sqlite3")
    try:
        altered = Migration(
            version=1,
            name="initial_schema",
            statements=("CREATE TABLE different(value INTEGER)",),
        )
        with pytest.raises(MigrationHistoryError, match="checksum_mismatch"):
            MigrationRunner((altered,)).run(database.connection)
    finally:
        database.close()


def test_migration_order_must_be_strictly_ascending() -> None:
    first = Migration(1, "first", ("SELECT 1",))
    second = Migration(2, "second", ("SELECT 1",))
    with pytest.raises(MigrationConfigurationError, match="strictly_ascending"):
        MigrationRunner((second, first))


def test_failed_migration_rolls_back_all_its_statements(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "rollback.sqlite3")
    try:
        broken = Migration(
            version=2,
            name="broken",
            statements=(
                "CREATE TABLE should_rollback(value INTEGER)",
                "THIS IS NOT SQL",
            ),
        )
        with pytest.raises(sqlite3.OperationalError):
            MigrationRunner((*DEFAULT_MIGRATIONS, broken)).run(database.connection)

        assert (
            database.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_rollback'"
            ).fetchone()
            is None
        )
        versions = database.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [row[0] for row in versions] == [1]
    finally:
        database.close()


def test_higher_database_version_fails_closed(tmp_path: Path) -> None:
    database = _run_default(tmp_path / "higher-version.sqlite3")
    try:
        database.connection.execute(
            (
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (2, "future", "b" * 64, "2026-08-15T00:00:00Z"),
        )
        with pytest.raises(MigrationHistoryError, match="history_gap"):
            MigrationRunner().run(database.connection)
    finally:
        database.close()
