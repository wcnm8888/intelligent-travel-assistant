"""Offline API integration tests for the app-owned SQLite Repository."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
)
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResult,
)
from intelligent_travel_assistant.bootstrap import StartupConfigurationError
from intelligent_travel_assistant.contracts import (
    PlanningStatus,
    TripPlanResponse,
)
from intelligent_travel_assistant.settings import Settings

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
FUTURE_MIGRATION_TIMESTAMP = datetime(2026, 8, 16, tzinfo=UTC).isoformat()


def _settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


def _payload() -> dict[str, object]:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    assert isinstance(payload, dict)
    return payload


def _partial_result() -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_partial.json").read_text(encoding="utf-8")
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


class PublishPartialOnceExecutor:
    def __init__(self) -> None:
        self.repository: PlanningJobRepository | None = None
        self._published = False

    async def execute(self, job_id: UUID) -> None:
        if self._published:
            return
        self._published = True
        repository = self.repository
        if repository is None:
            raise RuntimeError("test_repository_not_attached")
        job = await repository.get(job_id)
        for status in (PlanningStatus.NORMALIZING, PlanningStatus.COLLECTING):
            job = await repository.advance(
                job.job_id,
                status,
                expected_version=job.version,
            )
        await repository.record_result(
            job.job_id,
            _partial_result(),
            expected_version=job.version,
        )


def test_app_lifespan_creates_migrates_and_closes_only_the_temp_database(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lifecycle" / "travel-plans.sqlite3"
    application = create_app(settings=_settings(path))
    database = application.state.sqlite_database
    assert database is not None
    assert not path.exists()

    with TestClient(application) as client:
        assert path.is_file()
        _ = database.connection
        with sqlite3.connect(path) as inspection:
            assert inspection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert client.get("/api/health").status_code == 200

    with pytest.raises(RuntimeError, match="sqlite_database_not_open"):
        _ = database.connection


def test_post_and_get_survive_application_restart_without_contract_changes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "restart.sqlite3"
    payload = _payload()
    first_application = create_app(settings=_settings(path))
    with TestClient(first_application) as first_client:
        created = first_client.post("/api/trip-plans", json=payload)
        assert created.status_code == 202
        created_body = created.json()

    second_application = create_app(settings=_settings(path))
    with TestClient(second_application) as second_client:
        restored = second_client.get(f"/api/trip-plans/{created_body['job_id']}")
        repeated = second_client.post("/api/trip-plans", json=payload)

    assert restored.status_code == 200
    assert restored.json() == created_body
    assert repeated.status_code == 202
    assert repeated.json() == created_body
    assert "version" not in repeated.json()
    assert "request_fingerprint" not in repeated.json()


def test_delete_is_persistent_and_releases_the_client_request_id(tmp_path: Path) -> None:
    path = tmp_path / "delete-api.sqlite3"
    payload = _payload()
    with TestClient(create_app(settings=_settings(path))) as client:
        created = client.post("/api/trip-plans", json=payload)
        job_id = created.json()["job_id"]
        deleted = client.delete(f"/api/trip-plans/{job_id}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    with TestClient(create_app(settings=_settings(path))) as restarted:
        assert restarted.get(f"/api/trip-plans/{job_id}").status_code == 404
        recreated = restarted.post("/api/trip-plans", json=payload)
    assert recreated.status_code == 202
    assert recreated.json()["job_id"] != job_id


def test_startup_cleanup_deletes_expired_job_and_retains_unexpired_job(
    tmp_path: Path,
) -> None:
    path = tmp_path / "startup-cleanup.sqlite3"
    first_payload = _payload()
    second_payload = _payload()
    second_payload["client_request_id"] = "11111111-1111-4111-8111-111111111112"
    with TestClient(create_app(settings=_settings(path))) as client:
        expired_id = client.post("/api/trip-plans", json=first_payload).json()["job_id"]
        retained_id = client.post("/api/trip-plans", json=second_payload).json()["job_id"]

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE planning_jobs SET expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", expired_id),
        )
        connection.execute(
            "UPDATE planning_jobs SET expires_at = ? WHERE job_id = ?",
            ("2999-01-01T00:00:00+00:00", retained_id),
        )

    with TestClient(create_app(settings=_settings(path))) as restarted:
        expired = restarted.get(f"/api/trip-plans/{expired_id}")
        retained = restarted.get(f"/api/trip-plans/{retained_id}")

    assert expired.status_code == 404
    assert retained.status_code == 200


def test_sqlite_api_preserves_idempotency_conflict(tmp_path: Path) -> None:
    path = tmp_path / "idempotency-conflict.sqlite3"
    original = _payload()
    changed = _payload()
    changed["city"] = "苏州"

    with TestClient(create_app(settings=_settings(path))) as client:
        first = client.post("/api/trip-plans", json=original)
        conflict = client.post("/api/trip-plans", json=changed)

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert "request_fingerprint" not in conflict.text
    assert str(original["client_request_id"]) not in conflict.text


def test_concurrent_duplicate_posts_create_one_persistent_job(tmp_path: Path) -> None:
    path = tmp_path / "concurrent-create.sqlite3"
    application = create_app(settings=_settings(path))
    payload = _payload()
    with TestClient(application) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = tuple(
                pool.map(
                    lambda _index: client.post("/api/trip-plans", json=payload),
                    range(16),
                )
            )

        assert {response.status_code for response in responses} == {202}
        assert len({response.json()["job_id"] for response in responses}) == 1
        with sqlite3.connect(path) as inspection:
            assert inspection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone()[0] == 1
            assert inspection.execute("SELECT COUNT(*) FROM planning_attempts").fetchone()[0] == 1


def test_second_retry_conflicts_after_first_retry_wins(tmp_path: Path) -> None:
    path = tmp_path / "retry-conflict.sqlite3"
    executor = PublishPartialOnceExecutor()
    application = create_app(
        settings=_settings(path),
        planning_job_executor=executor,
    )
    executor.repository = application.state.planning_job_repository

    with TestClient(application) as client:
        created = client.post("/api/trip-plans", json=_payload())
        job_id = created.json()["job_id"]
        terminal = client.get(f"/api/trip-plans/{job_id}")
        first_retry = client.post(f"/api/trip-plans/{job_id}/retry")
        second_retry = client.post(f"/api/trip-plans/{job_id}/retry")
        restored = client.get(f"/api/trip-plans/{job_id}")

    assert terminal.json()["status"] == "partial"
    assert first_retry.status_code == 202
    assert first_retry.json()["attempt"] == 2
    assert second_retry.status_code == 409
    assert second_retry.json()["error"]["code"] == "retry_not_allowed"
    assert restored.json()["status"] == "normalizing"
    assert restored.json()["attempt"] == 2


def test_future_database_version_prevents_application_startup(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    database = SqliteDatabase(SqliteConnectionConfig(path=path))
    try:
        connection = database.open()
        MigrationRunner().run(connection)
        connection.execute(
            """
            INSERT INTO schema_migrations(version, name, checksum, applied_at)
            VALUES (?, ?, ?, ?)
            """,
            (2, "future", "f" * 64, FUTURE_MIGRATION_TIMESTAMP),
        )
    finally:
        database.close()

    application = create_app(settings=_settings(path))
    with pytest.raises(
        StartupConfigurationError,
        match="^sqlite_persistence_unavailable$",
    ):
        with TestClient(application):
            pass

    owned_database = application.state.sqlite_database
    assert owned_database is not None
    with pytest.raises(RuntimeError, match="sqlite_database_not_open"):
        _ = owned_database.connection
