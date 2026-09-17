"""Malformed search query combinations use the public input error envelope."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.api.test_f009_preplanning_api import SESSION_ID, FakeProvider, create_payload

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.f009 import PreplanningService


@pytest.mark.parametrize(
    "extra",
    [
        [("radius_m", "100")],
        [("center", "120.16,30.25")],
        [("category_codes", str(index)) for index in range(6)],
        [("keywords", "   ")],
    ],
)
def test_invalid_search_query_returns_422_without_provider_call(
    extra: list[tuple[str, str]],
) -> None:
    provider = FakeProvider()
    application = create_app(
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=PreplanningService(provider, id_factory=lambda: SESSION_ID),
    )
    with TestClient(application, raise_server_exceptions=False) as client:
        assert client.post("/api/preplanning-sessions", json=create_payload()).status_code == 201
        params = [("purpose", "visit")]
        if not any(key == "keywords" for key, _value in extra):
            params.append(("keywords", "西湖"))
        response = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois", params=[*params, *extra]
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "input_invalid"
        assert provider.search_calls == 0
        valid = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "visit", "keywords": "西湖"},
        )
        assert valid.status_code == 200
        assert provider.search_calls == 1
