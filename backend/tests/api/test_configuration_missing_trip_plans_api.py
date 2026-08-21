"""F-006 same-URI zero-call failure projection for all planning request versions."""

from __future__ import annotations

from collections.abc import Callable
from ipaddress import IPv4Address
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.api.test_multiday_trip_plans_api import legacy_payload, v2_payload
from tests.contracts.test_booked_rail_trip_planning_contracts import (
    request_payload as v4_payload,
)
from tests.contracts.test_multicity_trip_planning_contracts import (
    request_payload as v3_payload,
)

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.services import (
    ConfigurationMissingPlanningJobExecutor,
)
from intelligent_travel_assistant.settings import Settings

SAFE_MESSAGE = "本机服务配置不完整，无法生成旅行计划。"
SAFE_DIAGNOSTIC = "required_provider_configuration_missing"


def test_production_composition_dispatches_the_zero_call_executor() -> None:
    application = create_app(
        settings=Settings.model_validate(
            {
                "app_env": "test",
                "api_host": IPv4Address("127.0.0.1"),
                "api_port": 8000,
            }
        )
    )

    with TestClient(application) as client:
        created = client.post("/api/trip-plans", json=legacy_payload())
        fetched = client.get(f"/api/trip-plans/{created.json()['job_id']}")

    assert isinstance(
        application.state.planning_job_executor,
        ConfigurationMissingPlanningJobExecutor,
    )
    assert created.status_code == 202
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "failed"
    assert fetched.json()["errors"][0]["code"] == "configuration_missing"


@pytest.mark.parametrize(
    ("payload_factory", "response_version", "destination_key"),
    (
        (legacy_payload, None, "resolved_destination"),
        (lambda: v2_payload(3), "2", "resolved_destination"),
        (v3_payload, "3", "resolved_destinations"),
        (v4_payload, "4", "resolved_destinations"),
    ),
)
def test_configuration_missing_post_get_idempotency_and_retry_keep_existing_shape(
    payload_factory: Callable[[], dict[str, Any]],
    response_version: str | None,
    destination_key: str,
) -> None:
    repository = InMemoryPlanningJobRepository()
    executor = ConfigurationMissingPlanningJobExecutor(repository)
    application = create_app(
        planning_job_repository=repository,
        planning_job_executor=executor,
    )

    with TestClient(application) as client:
        created = client.post("/api/trip-plans", json=payload_factory())
        job_id = created.json()["job_id"]
        fetched = client.get(f"/api/trip-plans/{job_id}")
        repeated = client.post("/api/trip-plans", json=payload_factory())
        retry = client.post(f"/api/trip-plans/{job_id}/retry")

    assert created.status_code == 202
    assert created.json()["status"] == "draft"
    assert fetched.status_code == 200
    assert repeated.status_code == 202
    assert fetched.json() == repeated.json()
    body = fetched.json()
    assert body["status"] == "failed"
    assert body["attempt"] == 1
    assert body["plan"] is None
    assert body[destination_key] in (None, [])
    assert body["violations"] == []
    assert body["warnings"] == []
    assert body["uncertainties"] == []
    assert body["sources"] == []
    assert body["retryable"] is False
    assert body["errors"] == [
        {
            "code": "configuration_missing",
            "message": SAFE_MESSAGE,
            "field": None,
            "provider": None,
            "diagnostic_code": SAFE_DIAGNOSTIC,
            "retryable": False,
        }
    ]
    if response_version is None:
        assert "response_version" not in body
    else:
        assert body["response_version"] == response_version
    assert set(created.json()) == set(body)
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "retry_not_allowed"
