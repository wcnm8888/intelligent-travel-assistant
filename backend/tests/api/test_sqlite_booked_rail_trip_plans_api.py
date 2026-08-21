"""F-004C V4 loopback HTTP longitudinal checks on an isolated schema-v2 SQLite file."""

from __future__ import annotations

import copy
import sqlite3
import time
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx2
import pytest
from fastapi.testclient import TestClient
from tests.browser_booked_rail_support import (
    create_browser_app,
    disabled_providers,
    request_payload,
)
from tests.browser_multicity_support import settings
from tests.contracts.test_multicity_trip_planning_contracts import (
    request_payload as v3_request_payload,
)

from intelligent_travel_assistant.app import create_app


class _NoopExecutor:
    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def execute(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


def persisted_text(path: Path) -> str:
    with sqlite3.connect(path) as inspection:
        values: list[str] = []
        for query in (
            "SELECT request_json FROM planning_jobs",
            "SELECT result_metadata_json FROM planning_attempts",
            "SELECT plan_json FROM plan_versions",
            "SELECT provider_record_id, reference_url, attributions_json, warnings_json "
            "FROM source_records",
        ):
            values.extend(
                value
                for row in inspection.execute(query).fetchall()
                for value in row
                if value is not None
            )
    return "\n".join(values).lower()


def wait_for_status(client: TestClient, job_id: str, expected_status: str) -> httpx2.Response:
    for _ in range(100):
        response = client.get(f"/api/trip-plans/{job_id}")
        if response.json()["status"] == expected_status:
            return response
        time.sleep(0.01)
    raise AssertionError(f"synthetic terminal status not reached: {expected_status}")


@pytest.mark.parametrize("city_count", (2, 3))
def test_v4_create_restart_idempotency_retry_delete_and_v3_compatibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    city_count: int,
) -> None:
    path = tmp_path / f"booked-rail-{city_count}-city.sqlite3"
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(path.resolve()))
    monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", str(city_count))
    request = request_payload(city_count)
    old_v3_request = v3_request_payload(2)
    old_v3_request["client_request_id"] = "44444444-4444-4444-8444-444444444444"

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request)
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        terminal = wait_for_status(client, job_id, "partial")
    persisted_v4 = persisted_text(path)

    noop = _NoopExecutor()
    with TestClient(
        create_app(
            settings=settings(path),
            planning_job_executor=noop,
            provider_adapters=disabled_providers(),
        )
    ) as restarted:
        restored = restarted.get(f"/api/trip-plans/{job_id}")
        repeated = restarted.post("/api/trip-plans", json=request)
        old_v3 = restarted.post("/api/trip-plans", json=old_v3_request)
        retried = restarted.post(f"/api/trip-plans/{job_id}/retry")
        deleted = restarted.delete(f"/api/trip-plans/{job_id}")
        missing = restarted.get(f"/api/trip-plans/{job_id}")

    with TestClient(
        create_app(
            settings=settings(path),
            planning_job_executor=_NoopExecutor(),
            provider_adapters=disabled_providers(),
        )
    ) as second_restart:
        restored_v3 = second_restart.get(f"/api/trip-plans/{old_v3.json()['job_id']}")

    assert terminal.status_code == 200
    assert terminal.json()["response_version"] == "4"
    assert len(terminal.json()["resolved_destinations"]) == city_count
    assert len(terminal.json()["plan"]["intercity_segments"]) == city_count - 1
    assert [item["service_number"] for item in terminal.json()["plan"]["intercity_segments"]] == [
        "G1234",
        "D2281",
    ][: city_count - 1]
    assert all(
        item["fare"]["amount"] is None for item in terminal.json()["plan"]["intercity_segments"]
    )
    assert restored.json() == terminal.json()
    assert repeated.status_code == 202 and repeated.json() == terminal.json()
    assert old_v3.status_code == 202 and restored_v3.json() == old_v3.json()
    assert restored_v3.json()["response_version"] == "3"
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    assert deleted.status_code == 204 and missing.status_code == 404
    assert noop.job_ids == [UUID(old_v3.json()["job_id"]), UUID(job_id)]

    with sqlite3.connect(path) as inspection:
        assert inspection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]
        assert inspection.execute(
            "SELECT COUNT(*) FROM planning_jobs WHERE job_id = ?", (job_id,)
        ).fetchone() == (0,)
    for prohibited in (
        "passenger_name",
        "id_card",
        "phone",
        "email",
        "order_number",
        "seat_number",
        "ticket_qr",
        "cookie",
        "authorization",
    ):
        assert prohibited not in persisted_v4


def test_v4_synthetic_retry_reaches_a_second_terminal_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "booked-rail-retry.sqlite3"
    monkeypatch.setenv("ITA_BROWSER_SQLITE_PATH", str(path.resolve()))
    monkeypatch.setenv("ITA_MULTICITY_CITY_COUNT", "2")

    with TestClient(create_browser_app()) as client:
        created = client.post("/api/trip-plans", json=request_payload(2))
        first = wait_for_status(client, created.json()["job_id"], "partial")
        retried = client.post(f"/api/trip-plans/{created.json()['job_id']}/retry")
        second = wait_for_status(client, created.json()["job_id"], "partial")

    assert first.json()["attempt"] == 1
    assert retried.status_code == 202 and retried.json()["attempt"] == 2
    assert second.json()["attempt"] == 2
    assert first.json()["trace_id"] != second.json()["trace_id"]
    assert first.json()["sources"][0]["source_id"] != second.json()["sources"][0]["source_id"]


def test_v4_forbidden_preferences_are_rejected_before_sqlite_write(tmp_path: Path) -> None:
    path = tmp_path / "booked-rail-private-sentinel.sqlite3"
    executor = _NoopExecutor()
    app = create_app(
        settings=settings(path),
        planning_job_executor=executor,
        provider_adapters=disabled_providers(),
    )
    sentinel = "SYNTHETIC_V4_PRIVATE_SENTINEL"

    with TestClient(app) as client:
        free_text = request_payload(2)
        cast(dict[str, object], free_text["preferences"])["free_text"] = sentinel
        hard_constraints = copy.deepcopy(request_payload(2))
        hard_constraints["client_request_id"] = "55555555-5555-4555-8555-555555555555"
        cast(dict[str, object], hard_constraints["preferences"])["hard_constraints"] = [sentinel]
        responses = (
            client.post("/api/trip-plans", json=free_text),
            client.post("/api/trip-plans", json=hard_constraints),
        )

    with sqlite3.connect(path) as inspection:
        job_count = inspection.execute("SELECT COUNT(*) FROM planning_jobs").fetchone()[0]

    assert [response.status_code for response in responses] == [422, 422]
    assert job_count == 0
    assert executor.job_ids == []
    assert sentinel.casefold() not in persisted_text(path)
