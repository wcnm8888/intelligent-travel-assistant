"""Offline configuration, credential isolation and startup-check tests."""

from __future__ import annotations

import socket
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pydantic import ValidationError

from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    StartupConfigurationError,
    build_provider_adapters,
)
from intelligent_travel_assistant.settings import (
    PROJECT_ROOT,
    SETTINGS_ENV_FILE,
    Settings,
    default_local_sqlite_database_path,
)

PROVIDER_ENVIRONMENT = (
    "DEEPSEEK_API_KEY",
    "AMAP_API_KEY",
    "QWEATHER_API_HOST",
    "QWEATHER_PROJECT_ID",
    "QWEATHER_CREDENTIAL_ID",
    "QWEATHER_PRIVATE_KEY_PATH",
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "api_host": IPv4Address("127.0.0.1"),
        "api_port": 8000,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _write_private_key(path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def test_empty_provider_configuration_starts_health_with_disabled_report() -> None:
    application = create_app(_settings())

    with TestClient(application) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert application.state.provider_adapters.report.deepseek is ProviderActivationState.DISABLED
    assert application.state.provider_adapters.report.amap is ProviderActivationState.DISABLED
    assert application.state.provider_adapters.report.qweather is ProviderActivationState.DISABLED
    assert application.state.planning_job_executor is None


def test_test_composition_never_consults_local_dotenv() -> None:
    assert SETTINGS_ENV_FILE is None

    application = create_app()

    assert application.state.provider_adapters.report.deepseek is ProviderActivationState.DISABLED
    assert application.state.provider_adapters.report.amap is ProviderActivationState.DISABLED
    assert application.state.provider_adapters.report.qweather is ProviderActivationState.DISABLED
    assert application.state.planning_job_executor is None
    assert application.state.sqlite_database is None


def test_sqlite_database_path_must_be_absolute() -> None:
    with pytest.raises(ValidationError, match="sqlite database path must be absolute"):
        _settings(sqlite_database_path=Path("relative/travel-plans.sqlite3"))


def test_sqlite_database_path_must_stay_outside_the_project_tree() -> None:
    with pytest.raises(
        ValidationError,
        match="sqlite database path must be outside the project tree",
    ):
        _settings(sqlite_database_path=(PROJECT_ROOT / "travel-plans.sqlite3").resolve())


def test_default_local_sqlite_path_stays_outside_source_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    local_app_data = (tmp_path / "local-app-data").resolve()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    path = default_local_sqlite_database_path()

    assert path == local_app_data / "IntelligentTravelAssistant" / "travel-plans.sqlite3"
    assert not path.exists()


def test_test_suite_denies_non_loopback_network() -> None:
    with pytest.raises(AssertionError, match="^real_network_disabled_in_tests$"):
        socket.create_connection(("example.invalid", 443), timeout=0.01)


def test_complete_configuration_builds_all_adapters_without_network(tmp_path: Path) -> None:
    private_key_path = tmp_path / "qweather-ed25519.pem"
    _write_private_key(private_key_path)
    settings = _settings(
        deepseek_api_key="deepseek-local-test-value",
        amap_api_key="amap-local-test-value",
        qweather_api_host="example.qweatherapi.com",
        qweather_project_id="project_test",
        qweather_credential_id="credential_test",
        qweather_private_key_path=private_key_path,
    )

    adapters = build_provider_adapters(settings)

    assert adapters.report.deepseek is ProviderActivationState.READY
    assert adapters.report.amap is ProviderActivationState.READY
    assert adapters.report.qweather is ProviderActivationState.READY
    assert adapters.deepseek is not None
    assert adapters.amap is not None
    assert adapters.qweather is not None

    application = create_app(settings=settings)
    assert application.state.planning_job_executor is not None


@pytest.mark.parametrize(
    "configured_field",
    [
        {"qweather_api_host": "example.qweatherapi.com"},
        {"qweather_project_id": "project_test"},
        {"qweather_credential_id": "credential_test"},
        {"qweather_private_key_path": Path("C:/private/qweather.pem")},
    ],
)
def test_partial_qweather_configuration_fails_with_stable_code(
    configured_field: dict[str, object],
) -> None:
    with pytest.raises(
        StartupConfigurationError,
        match="^qweather_configuration_incomplete$",
    ):
        build_provider_adapters(_settings(**configured_field))


def test_relative_private_key_path_is_rejected_without_echoing_path() -> None:
    sensitive_path = Path("private/hidden/qweather.pem")
    settings = _settings(
        qweather_api_host="example.qweatherapi.com",
        qweather_project_id="project_test",
        qweather_credential_id="credential_test",
        qweather_private_key_path=sensitive_path,
    )

    with pytest.raises(StartupConfigurationError) as captured:
        build_provider_adapters(settings)

    assert str(captured.value) == "qweather_private_key_path_invalid"
    assert str(sensitive_path) not in str(captured.value)


def test_invalid_private_key_does_not_escape_into_startup_error(tmp_path: Path) -> None:
    private_key_path = tmp_path / "sensitive-account-name.pem"
    private_material = b"not-a-private-key"
    private_key_path.write_bytes(private_material)
    settings = _settings(
        qweather_api_host="example.qweatherapi.com",
        qweather_project_id="project_test",
        qweather_credential_id="credential_test",
        qweather_private_key_path=private_key_path,
    )

    with pytest.raises(StartupConfigurationError) as captured:
        build_provider_adapters(settings)

    rendered = str(captured.value)
    assert rendered == "qweather_configuration_invalid"
    assert str(private_key_path) not in rendered
    assert private_material.decode() not in rendered


def test_missing_private_key_does_not_echo_absolute_path(tmp_path: Path) -> None:
    private_key_path = (tmp_path / "missing-account.pem").resolve()
    settings = _settings(
        qweather_api_host="example.qweatherapi.com",
        qweather_project_id="project_test",
        qweather_credential_id="credential_test",
        qweather_private_key_path=private_key_path,
    )

    with pytest.raises(StartupConfigurationError) as captured:
        build_provider_adapters(settings)

    assert str(captured.value) == "qweather_private_key_unavailable"
    assert str(private_key_path) not in str(captured.value)


def test_oversized_private_key_is_rejected_before_parsing(tmp_path: Path) -> None:
    private_key_path = tmp_path / "oversized.pem"
    private_key_path.write_bytes(b"x" * 16_385)
    settings = _settings(
        qweather_api_host="example.qweatherapi.com",
        qweather_project_id="project_test",
        qweather_credential_id="credential_test",
        qweather_private_key_path=private_key_path,
    )

    with pytest.raises(
        StartupConfigurationError,
        match="^qweather_private_key_invalid$",
    ):
        build_provider_adapters(settings)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("deepseek_api_key", " whitespace ", "deepseek_configuration_invalid"),
        ("amap_api_key", "line\nbreak", "amap_configuration_invalid"),
    ],
)
def test_invalid_api_key_fails_with_provider_safe_code(
    field: str,
    value: str,
    expected_code: str,
) -> None:
    with pytest.raises(StartupConfigurationError) as captured:
        build_provider_adapters(_settings(**{field: value}))

    assert str(captured.value) == expected_code
    assert value not in str(captured.value)


def test_settings_repr_hides_secret_values_and_private_key_path(tmp_path: Path) -> None:
    private_key_path = tmp_path / "account-private.pem"
    deepseek_value = "deepseek-" + "sensitive-value"
    amap_value = "amap-" + "sensitive-value"
    settings = _settings(
        sqlite_database_path=(tmp_path / "private-travel-plans.sqlite3").resolve(),
        deepseek_api_key=deepseek_value,
        amap_api_key=amap_value,
        qweather_api_host="account.qweatherapi.com",
        qweather_project_id="sensitive_project",
        qweather_credential_id="sensitive_credential",
        qweather_private_key_path=private_key_path,
    )

    rendered = repr(settings)

    for sensitive in (
        deepseek_value,
        amap_value,
        "account.qweatherapi.com",
        "sensitive_project",
        "sensitive_credential",
        str(private_key_path),
        str((tmp_path / "private-travel-plans.sqlite3").resolve()),
    ):
        assert sensitive not in rendered


def test_settings_load_provider_values_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    private_key_path = tmp_path / "qweather.pem"
    values = {
        "DEEPSEEK_API_KEY": "deepseek-environment-value",
        "AMAP_API_KEY": "amap-environment-value",
        "QWEATHER_API_HOST": "account.qweatherapi.com",
        "QWEATHER_PROJECT_ID": "project_environment",
        "QWEATHER_CREDENTIAL_ID": "credential_environment",
        "QWEATHER_PRIVATE_KEY_PATH": str(private_key_path),
    }
    for variable, value in values.items():
        monkeypatch.setenv(variable, value)

    settings = Settings()

    assert settings.deepseek_api_key is not None
    assert settings.deepseek_api_key.get_secret_value() == values["DEEPSEEK_API_KEY"]
    assert settings.amap_api_key is not None
    assert settings.amap_api_key.get_secret_value() == values["AMAP_API_KEY"]
    assert settings.qweather_api_host == values["QWEATHER_API_HOST"]
    assert settings.qweather_project_id == values["QWEATHER_PROJECT_ID"]
    assert settings.qweather_credential_id == values["QWEATHER_CREDENTIAL_ID"]
    assert settings.qweather_private_key_path == private_key_path


def test_empty_environment_values_leave_providers_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in PROVIDER_ENVIRONMENT:
        monkeypatch.setenv(variable, "")

    adapters = build_provider_adapters(Settings())

    assert adapters.report.deepseek is ProviderActivationState.DISABLED
    assert adapters.report.amap is ProviderActivationState.DISABLED
    assert adapters.report.qweather is ProviderActivationState.DISABLED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deepseek_model", "deepseek-drift"),
        ("deepseek_base_url", "https://example.invalid"),
    ],
)
def test_settings_reject_unapproved_deepseek_contract(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _settings(**{field: value})
