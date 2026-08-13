"""Behavior tests for the local backend health boundary."""

from ipaddress import IPv4Address

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from intelligent_travel_assistant.app import SERVICE_NAME, HealthResponse, create_app
from intelligent_travel_assistant.settings import Settings


def make_test_settings() -> Settings:
    return Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
        }
    )


def test_health_returns_stable_contract() -> None:
    with TestClient(create_app(make_test_settings())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok", "service": SERVICE_NAME}


def test_health_does_not_require_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("DEEPSEEK_API_KEY", "AMAP_API_KEY", "QWEATHER_API_KEY"):
        monkeypatch.delenv(variable, raising=False)

    with TestClient(create_app(make_test_settings())) as client:
        response = client.get("/api/health")

    assert response.status_code == 200


def test_health_schema_rejects_an_unapproved_status() -> None:
    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "degraded", "service": SERVICE_NAME})


def test_unknown_route_uses_fastapi_not_found_boundary() -> None:
    with TestClient(create_app(make_test_settings())) as client:
        response = client.get("/api/not-a-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_settings_default_to_local_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("APP_ENV", "API_HOST", "API_PORT"):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings.model_validate({})

    assert settings.app_env == "local"
    assert settings.api_host == IPv4Address("127.0.0.1")
    assert settings.api_port == 8000


@pytest.mark.parametrize("invalid_port", [0, 65536])
def test_settings_reject_invalid_ports(invalid_port: int) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"api_port": invalid_port})
