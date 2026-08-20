"""F-004B1 V3 loopback composition on isolated schema-v2 SQLite files."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from tests.browser_multicity_support import (
    configure_browser_environment,
    create_browser_app,
    request_payload,
    settings,
)

from intelligent_travel_assistant.app import create_app


def wait_for_status(
    client: TestClient,
    job_id: str,
    expected_status: str,
) -> httpx2.Response:
    for _ in range(100):
        response = client.get(f"/api/trip-plans/{job_id}")
        if response.json()["status"] == expected_status:
            return response
        time.sleep(0.01)
    raise AssertionError(f"synthetic terminal status not reached: {expected_status}")


def test_v3_create_restart_idempotency_retry_and_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "multicity-longitudinal.sqlite3"
    configure_browser_environment(monkeypatch, path, city_count=2, scenario="partial")
    request = request_payload(2)

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request)
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        terminal = wait_for_status(client, job_id, "partial")

    with TestClient(create_app(settings=settings(path))) as restarted:
        restored = restarted.get(f"/api/trip-plans/{job_id}")
        repeated = restarted.post("/api/trip-plans", json=request)
        retried = restarted.post(f"/api/trip-plans/{job_id}/retry")
        deleted = restarted.delete(f"/api/trip-plans/{job_id}")
        missing = restarted.get(f"/api/trip-plans/{job_id}")

    assert terminal.status_code == 200
    assert restored.json() == terminal.json()
    assert repeated.status_code == 202 and repeated.json() == terminal.json()
    assert retried.status_code == 202
    assert retried.json()["attempt"] == 2
    assert retried.json()["status"] == "normalizing"
    assert deleted.status_code == 204 and missing.status_code == 404

    with sqlite3.connect(path) as inspection:
        assert inspection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]
        assert inspection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone() == (0,)


def test_v3_synthetic_retry_publishes_a_second_attempt_with_fresh_source_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "multicity-synthetic-retry.sqlite3"
    configure_browser_environment(monkeypatch, path, city_count=2, scenario="partial")

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request_payload(2))
        first = wait_for_status(client, created.json()["job_id"], "partial")
        retried = client.post(f"/api/trip-plans/{created.json()['job_id']}/retry")
        second = wait_for_status(client, created.json()["job_id"], "partial")

    assert first.json()["attempt"] == 1
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    assert second.json()["attempt"] == 2
    assert first.json()["sources"][0]["source_id"] != second.json()["sources"][0]["source_id"]
    with sqlite3.connect(path) as inspection:
        assert inspection.execute("SELECT COUNT(*) FROM source_records").fetchone() == (2,)


@pytest.mark.parametrize("city_count", (2, 3))
def test_v3_two_and_three_city_terminal_results_restart_on_schema_v2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    city_count: int,
) -> None:
    path = tmp_path / f"multicity-{city_count}.sqlite3"
    configure_browser_environment(monkeypatch, path, city_count=city_count, scenario="ready")

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request_payload(city_count))
        terminal = wait_for_status(client, created.json()["job_id"], "ready")

    with TestClient(create_app(settings=settings(path))) as restarted:
        restored = restarted.get(f"/api/trip-plans/{created.json()['job_id']}")

    assert terminal.status_code == 200
    assert terminal.json()["response_version"] == "3"
    assert len(terminal.json()["resolved_destinations"]) == city_count
    assert len(terminal.json()["plan"]["intercity_segments"]) == city_count - 1
    assert restored.json() == terminal.json()


@pytest.mark.parametrize("scenario", ("ready", "partial", "conflict", "needs_input", "failed"))
def test_v3_five_terminal_states_round_trip_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    path = tmp_path / f"multicity-{scenario}.sqlite3"
    configure_browser_environment(monkeypatch, path, city_count=2, scenario=scenario)

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request_payload(2))
        terminal = wait_for_status(client, created.json()["job_id"], scenario)

    with TestClient(create_app(settings=settings(path))) as restarted:
        restored = restarted.get(f"/api/trip-plans/{created.json()['job_id']}")

    assert terminal.status_code == 200
    assert terminal.json()["status"] == scenario
    assert restored.json() == terminal.json()


def test_browser_composition_rejects_missing_existing_and_non_temp_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ITA_BROWSER_SQLITE_PATH", raising=False)
    monkeypatch.setenv("ITA_MULTICITY_SCENARIO", "ready")
    monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", "2")
    with pytest.raises(RuntimeError, match="synthetic_browser_sqlite_path_required"):
        create_browser_app()

    existing = tmp_path / "existing.sqlite3"
    existing.touch()
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(existing.resolve()))
    with pytest.raises(RuntimeError, match="synthetic_browser_sqlite_path_unsafe"):
        create_browser_app()

    project_path = Path(__file__).resolve().parent / "forbidden.sqlite3"
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(project_path))
    with pytest.raises(RuntimeError, match="synthetic_browser_sqlite_path_unsafe"):
        create_browser_app()
