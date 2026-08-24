"""F-004A version 2 API restart behavior on an isolated schema-v2 SQLite file."""

from __future__ import annotations

import copy
import json
import sqlite3
import time
from datetime import date, timedelta
from ipaddress import IPv4Address
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from tests.browser_multiday_support import create_browser_app

from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.settings import Settings

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def settings(path: Path) -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": path.resolve(),
        }
    )


def payload(day_count: int = 7) -> dict[str, object]:
    value = copy.deepcopy(
        json.loads((FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8"))[
            "request"
        ]
    )
    assert isinstance(value, dict)
    start = date.fromisoformat(str(value["start_date"]))
    value["request_version"] = "2"
    value["end_date"] = (start + timedelta(days=day_count - 1)).isoformat()
    value["day_windows"] = [
        {"day_offset": offset, "start_time": "09:00:00", "end_time": "18:00:00"}
        for offset in range(day_count)
    ]
    return value


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
    raise AssertionError(f"job did not reach {expected_status}")


def configure_browser_environment(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    *,
    day_count: int = 3,
    scenario: str = "ready",
) -> None:
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(path.resolve()))
    monkeypatch.setenv("ITA_BROWSER_START_DATE", "2026-08-15")
    monkeypatch.setenv("ITA_MULTIDAY_DAYS", str(day_count))
    monkeypatch.setenv("ITA_MULTIDAY_SCENARIO", scenario)


def test_browser_support_rejects_database_paths_outside_the_temporary_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_browser_environment(
        monkeypatch,
        Path(__file__).resolve().parents[2] / "unsafe-browser.sqlite3",
    )

    with pytest.raises(RuntimeError, match="synthetic_browser_sqlite_path_unsafe"):
        create_browser_app()


def test_browser_support_rejects_an_existing_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "existing.sqlite3"
    path.write_bytes(b"")
    configure_browser_environment(monkeypatch, path)

    with pytest.raises(RuntimeError, match="synthetic_browser_sqlite_path_unsafe"):
        create_browser_app()


def test_v2_post_get_idempotency_and_delete_survive_application_restarts(
    tmp_path: Path,
) -> None:
    path = tmp_path / "multiday-api.sqlite3"
    request = payload()

    with TestClient(create_app(settings=settings(path))) as client:
        created = client.post("/api/trip-plans", json=request)
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        terminal_body = client.get(f"/api/trip-plans/{job_id}").json()

    with TestClient(create_app(settings=settings(path))) as restarted:
        restored = restarted.get(f"/api/trip-plans/{job_id}")
        repeated = restarted.post("/api/trip-plans", json=request)
        deleted = restarted.delete(f"/api/trip-plans/{job_id}")

    with TestClient(create_app(settings=settings(path))) as after_delete:
        missing = after_delete.get(f"/api/trip-plans/{job_id}")

    assert restored.status_code == 200
    assert terminal_body["status"] == "failed"
    assert terminal_body["errors"][0]["code"] == "configuration_missing"
    assert restored.json() == terminal_body
    assert repeated.status_code == 202
    assert repeated.json() == terminal_body
    assert deleted.status_code == 204
    assert missing.status_code == 404
    with sqlite3.connect(path) as inspection:
        assert inspection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]


def test_two_three_and_seven_day_terminal_results_round_trip_through_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for day_count, scenario in ((2, "ready"), (3, "ready"), (7, "partial")):
        path = tmp_path / f"terminal-{day_count}.sqlite3"
        configure_browser_environment(
            monkeypatch,
            path,
            day_count=day_count,
            scenario=scenario,
        )
        request = payload(day_count)

        with TestClient(create_browser_app()) as client:
            created = client.post("/api/trip-plans", json=request)
            assert created.status_code == 202
            job_id = created.json()["job_id"]
            terminal = wait_for_status(client, job_id, scenario)

        with TestClient(create_app(settings=settings(path))) as restarted:
            restored = restarted.get(f"/api/trip-plans/{job_id}")
            repeated = restarted.post("/api/trip-plans", json=request)
            deleted = restarted.delete(f"/api/trip-plans/{job_id}")

        assert terminal.status_code == 200
        assert terminal.json()["status"] == scenario
        assert terminal.json()["response_version"] == "2"
        assert terminal.json()["plan"]["plan_format_version"] == "2"
        assert len(terminal.json()["plan"]["days"]) == day_count
        assert restored.status_code == 200
        assert restored.json() == terminal.json()
        assert repeated.status_code == 202
        assert repeated.json() == terminal.json()
        assert deleted.status_code == 204
        with sqlite3.connect(path) as inspection:
            assert inspection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall() == [(1,), (2,)]
            assert inspection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone() == (0,)


@pytest.mark.parametrize("scenario", ("ready", "partial", "conflict", "needs_input", "failed"))
def test_v2_five_terminal_states_round_trip_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    path = tmp_path / f"terminal-{scenario}.sqlite3"
    configure_browser_environment(monkeypatch, path, day_count=3, scenario=scenario)
    request = payload(3)

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request)
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        terminal = wait_for_status(client, job_id, scenario)

    with TestClient(create_app(settings=settings(path))) as restarted:
        restored = restarted.get(f"/api/trip-plans/{job_id}")

    assert terminal.status_code == 200
    assert terminal.json()["response_version"] == "2"
    assert terminal.json()["status"] == scenario
    assert restored.status_code == 200
    assert restored.json() == terminal.json()
    if terminal.json()["plan"] is not None:
        assert terminal.json()["plan"]["plan_format_version"] == "2"
        assert len(terminal.json()["plan"]["days"]) == 3
