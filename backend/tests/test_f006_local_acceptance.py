"""F-006 combinational offline journeys across all four planning contracts."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
)
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.services import (
    ConfigurationMissingPlanningJobExecutor,
)
from tests.api.test_multiday_trip_plans_api import legacy_payload, v2_payload
from tests.api.test_sqlite_multiday_trip_plans_api import payload as v2_browser_payload
from tests.browser_booked_rail_support import (
    create_browser_app as create_v4_app,
)
from tests.browser_booked_rail_support import request_payload as v4_payload
from tests.browser_multicity_support import (
    create_browser_app as create_v3_app,
)
from tests.browser_multicity_support import request_payload as v3_payload
from tests.browser_multiday_support import create_browser_app as create_v2_app
from tests.browser_support import create_browser_app as create_legacy_app

_TERMINAL = frozenset({"ready", "partial", "needs_input", "conflict", "failed"})


def _wait_for_terminal(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = client.get(f"/api/trip-plans/{job_id}")
        body = cast(dict[str, Any], response.json())
        if body["status"] in _TERMINAL:
            return body
        time.sleep(0.01)
    raise AssertionError("synthetic journey did not reach a terminal state")


def _configuration_missing_app() -> FastAPI:
    repository = InMemoryPlanningJobRepository()
    return create_app(
        planning_job_repository=repository,
        planning_job_executor=ConfigurationMissingPlanningJobExecutor(repository),
    )


CONFIGURATION_CASES: tuple[tuple[str, Callable[[], dict[str, Any]], str | None], ...] = (
    ("legacy-configuration-missing", legacy_payload, None),
    ("v2-configuration-missing", lambda: v2_payload(3), "2"),
    ("v3-configuration-missing", lambda: v3_payload(2), "3"),
    ("v4-configuration-missing", lambda: v4_payload(2), "4"),
)


@pytest.mark.parametrize(
    ("case_id", "payload_factory", "response_version"),
    CONFIGURATION_CASES,
    ids=[case[0] for case in CONFIGURATION_CASES],
)
def test_all_versions_fail_safely_without_provider_configuration(
    case_id: str,
    payload_factory: Callable[[], dict[str, Any]],
    response_version: str | None,
) -> None:
    with TestClient(_configuration_missing_app()) as client:
        created = client.post("/api/trip-plans", json=payload_factory())
        body = _wait_for_terminal(client, created.json()["job_id"])

    assert case_id
    assert created.status_code == 202
    assert body["status"] == "failed"
    assert body["plan"] is None
    assert body["sources"] == []
    assert body["retryable"] is False
    assert body["errors"] == [
        {
            "code": "configuration_missing",
            "message": "本机服务配置不完整，无法生成旅行计划。",
            "field": None,
            "provider": None,
            "diagnostic_code": "required_provider_configuration_missing",
            "retryable": False,
        }
    ]
    if response_version is None:
        assert "response_version" not in body
    else:
        assert body["response_version"] == response_version


LEGACY_TERMINAL_CASES = tuple(
    (f"legacy-{status}", status)
    for status in ("ready", "partial", "needs_input", "conflict", "failed")
)


@pytest.mark.parametrize(
    ("case_id", "status"),
    LEGACY_TERMINAL_CASES,
    ids=[case[0] for case in LEGACY_TERMINAL_CASES],
)
def test_legacy_synthetic_journeys_cover_every_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    status: str,
) -> None:
    monkeypatch.setenv("ITA_SYNTHETIC_SCENARIO", status)
    with TestClient(create_legacy_app()) as client:
        created = client.post("/api/trip-plans", json=legacy_payload())
        body = _wait_for_terminal(client, created.json()["job_id"])

    assert case_id
    assert body["status"] == status
    assert "response_version" not in body


SQLITE_CASES = (
    ("v2-ready-3-day", "2", 3, "ready"),
    ("v3-partial-2-city", "3", 2, "partial"),
    ("v3-ready-3-city", "3", 3, "ready"),
    ("v4-partial-2-city", "4", 2, "partial"),
    ("v4-partial-3-city", "4", 3, "partial"),
)


@pytest.mark.parametrize(
    ("case_id", "version", "size", "status"),
    SQLITE_CASES,
    ids=[case[0] for case in SQLITE_CASES],
)
def test_versioned_synthetic_journeys_round_trip_on_schema_v2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    version: str,
    size: int,
    status: str,
) -> None:
    database = tmp_path / f"{case_id}.sqlite3"
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(database.resolve()))
    if version == "2":
        monkeypatch.setenv("ITA_BROWSER_START_DATE", "2026-08-15")
        monkeypatch.setenv("ITA_MULTIDAY_DAYS", str(size))
        monkeypatch.setenv("ITA_MULTIDAY_SCENARIO", status)
        app, payload = create_v2_app(), v2_browser_payload(size)
    elif version == "3":
        monkeypatch.setenv("ITA_BROWSER_START_DATE", "2026-08-21")
        monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", str(size))
        monkeypatch.setenv("ITA_MULTICITY_SCENARIO", status)
        app, payload = create_v3_app(), v3_payload(size)
    else:
        monkeypatch.setenv("ITA_BROWSER_START_DATE", "2026-08-21")
        monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", str(size))
        app, payload = create_v4_app(), v4_payload(size)

    with TestClient(app) as client:
        created = client.post("/api/trip-plans", json=payload)
        body = _wait_for_terminal(client, created.json()["job_id"])
        restored = client.get(f"/api/trip-plans/{created.json()['job_id']}").json()

    assert created.status_code == 202
    assert body == restored
    assert body["response_version"] == version
    assert body["status"] == status
    with sqlite3.connect(database) as inspection:
        assert inspection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]
    if version in {"3", "4"} and status == "partial":
        assert body["plan"]["budget_summary"]["unknown_count"] > 0
        assert all(
            segment["fare"]["amount"] is None for segment in body["plan"]["intercity_segments"]
        )
        assert any(source["freshness"] == "unknown_validity" for source in body["sources"])


def test_combinational_matrix_is_bounded_and_covers_frozen_axes() -> None:
    case_ids = {
        *(case[0] for case in CONFIGURATION_CASES),
        *(case[0] for case in LEGACY_TERMINAL_CASES),
        *(case[0] for case in SQLITE_CASES),
    }

    assert len(case_ids) == 14
    assert {"legacy", "v2", "v3", "v4"} <= {case_id.split("-", 1)[0] for case_id in case_ids}
    assert {"ready", "partial", "needs_input", "conflict", "failed"} <= {
        token for case_id in case_ids for token in case_id.split("-")
    }
