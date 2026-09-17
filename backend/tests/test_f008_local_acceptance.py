"""F-008 controlled dual-mode acceptance, not real Provider UAT."""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.browser_f008_production_support import create_production_app
from tests.browser_f008_production_support import (
    request_payload as production_request_payload,
)
from tests.browser_f008_support import create_f008_app, request_payload

START = date(2026, 9, 4)


@pytest.mark.parametrize("mode", ("memory", "sqlite"))
def test_recovery_commit_restart_delete_and_zero_live_sqlite(mode: str, tmp_path: Path) -> None:
    path = tmp_path / "f008-step12-owned" / "offline.sqlite3"
    app = create_f008_app(mode, START, path)
    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=request_payload(START))
        assert created.status_code == 202
        url = f"/api/trip-plans/{created.json()['job_id']}"
        old = client.get(url).json()
        assert old["status"] == "ready"
        payload = {
            "replan_request_id": str(uuid4()),
            "baseline_plan_id": old["plan"]["plan_id"],
            "command": {
                "operation": "adjust_activity_time",
                "target_activity_id": old["plan"]["days"][0]["activities"][0]["item_id"],
                "start_time": "10:30:00",
                "end_time": "11:30:00",
            },
        }
        first = client.post(f"{url}/replans", json=payload)
        first_url = f"{url}/replans/{first.json()['replan_id']}"
        assert first.json()["status"] == "awaiting_confirmation"
        client.post(f"{first_url}/decision", json={"choice": "approve"})
        failed = client.get(first_url).json()
        assert failed["status"] == "failed" and failed["errors"][0]["retryable"]
        assert client.get(url).json() == old
        payload["replan_request_id"] = str(uuid4())
        second = client.post(f"{url}/replans", json=payload)
        second_url = f"{url}/replans/{second.json()['replan_id']}"
        client.post(f"{second_url}/decision", json={"choice": "approve"})
        completed = client.get(second_url).json()
        current = client.get(url).json()
        assert completed["status"] == "completed"
        assert current["plan"]["plan_id"] != old["plan"]["plan_id"]
        assert current["plan"]["days"][0]["activities"][0]["start_time"] == "10:30:00"
        assert client.get(first_url).json() == failed
        assert app.state.f008_executor.execution_calls == 2
        if mode == "memory":
            assert app.state.planning_persistence.database is None
            assert not path.exists() and app.state.f008_sqlite_attempts == 0
            assert all(
                not adapter.calls
                for adapter in (
                    app.state.provider_adapters.deepseek,
                    app.state.provider_adapters.amap,
                    app.state.provider_adapters.qweather,
                )
            )
    restarted = create_f008_app(mode, START, path, allow_reopen=True)
    with TestClient(restarted) as client:
        restored = client.get(url)
        if mode == "memory":
            assert restored.status_code == 404
            assert client.get(first_url).status_code == 404
            assert not path.exists() and restarted.state.f008_sqlite_attempts == 0
        else:
            assert restored.json() == current
            assert client.get(second_url).json() == completed
            assert client.delete(url).status_code == 204
            assert client.get(url).status_code == 404
    if mode == "sqlite":
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
            assert [
                tuple(row)
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ] == [(1,), (2,)]


@pytest.mark.parametrize("mode", ("memory", "sqlite"))
@pytest.mark.parametrize(
    ("scenario", "status", "code"),
    (
        ("needs_input", "needs_input", "data_missing"),
        ("conflict", "conflict", "version_conflict"),
        ("stop", "failed", "provider_unauthorized"),
    ),
)
def test_terminal_recovery_matrix_preserves_original(
    mode: str, scenario: str, status: str, code: str, tmp_path: Path
) -> None:
    app = create_f008_app(
        mode, START, tmp_path / "f008-step12-owned" / "offline.sqlite3", scenario=scenario
    )
    with TestClient(app) as client:
        job = client.post("/api/trip-plans", json=request_payload(START)).json()
        url = f"/api/trip-plans/{job['job_id']}"
        old: dict[str, Any] = client.get(url).json()
        replan = client.post(
            f"{url}/replans",
            json={
                "replan_request_id": str(uuid4()),
                "baseline_plan_id": old["plan"]["plan_id"],
                "command": {
                    "operation": "adjust_activity_time",
                    "target_activity_id": old["plan"]["days"][0]["activities"][0]["item_id"],
                    "start_time": "10:30:00",
                    "end_time": "11:30:00",
                },
            },
        ).json()
        replan_url = f"{url}/replans/{replan['replan_id']}"
        client.post(f"{replan_url}/decision", json={"choice": "approve"})
        terminal = client.get(replan_url).json()
        assert terminal["status"] == status and terminal["errors"][0]["code"] == code
        assert client.get(url).json() == old


def test_formal_default_composition_is_memory_only_and_restart_returns_404(
    tmp_path: Path,
) -> None:
    root = tmp_path / "r5-formal-restart"
    application = create_production_app(root)
    with TestClient(application) as client:
        created = client.post("/api/trip-plans", json=production_request_payload())
        assert created.status_code == 202
        url = f"/api/trip-plans/{created.json()['job_id']}"
        result = client.get(url)
        assert result.status_code == 200
        assert result.json()["status"] in {"ready", "partial"}
        assert application.state.planning_persistence.database is None
        assert application.state.replan_repository is not None
        assert application.state.replan_application_service is not None
        assert application.state.route_attempt_limiter is not None

    restarted = create_production_app(root)
    with TestClient(restarted) as client:
        missing = client.get(url)
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "job_not_found"
        assert restarted.state.planning_persistence.database is None
