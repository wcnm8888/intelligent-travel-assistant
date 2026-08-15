"""Offline contracts for QWeather JWT forecast and current-alert adapters."""

from __future__ import annotations

import ast
import base64
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intelligent_travel_assistant.adapters.providers.qweather import (
    QWEATHER_REFERENCE_URL,
    QWEATHER_TIMEOUT_SECONDS,
    QWeatherAdapter,
    QWeatherAdapterConfig,
)
from intelligent_travel_assistant.application.ports import (
    CurrentWeatherAlertsRequest,
    WeatherForecastRequest,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderErrorCategory,
    ProviderResultStatus,
)

LOCATION_ID = UUID("90000000-0000-4000-8000-000000000040")
FIXED_NOW = datetime(2026, 8, 14, 7, 0, tzinfo=UTC)
FIXED_SOURCE_ID = UUID("70000000-0000-4000-8000-000000000040")
API_HOST = "unit-test.qweatherapi.com"
PROJECT_ID = "TESTPROJECT01"
CREDENTIAL_ID = "TESTCRED01"
COORDINATES = Coordinates(
    Decimal("120.155070"),
    Decimal("30.274085"),
    CoordinateSystem.PROVIDER_NATIVE,
)
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
PRIVATE_KEY_PEM = PRIVATE_KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)


def _forecast_request() -> WeatherForecastRequest:
    return WeatherForecastRequest(
        LOCATION_ID,
        COORDINATES,
        date(2026, 8, 15),
        date(2026, 8, 16),
    )


def _alert_request() -> CurrentWeatherAlertsRequest:
    return CurrentWeatherAlertsRequest(LOCATION_ID, COORDINATES)


def _day(
    local_date: date,
    *,
    minimum: object = 25.25,
    maximum: object = 34.5,
    minimum_unit: object = "°C",
    maximum_unit: object = "°C",
    condition_day: object = "多云",
    condition_night: object = "阵雨",
    start_time: object | None = None,
) -> dict[str, object]:
    start = start_time or f"{local_date.isoformat()}T00:00+08:00"
    end = f"{(local_date + timedelta(days=1)).isoformat()}T00:00+08:00"
    return {
        "forecastStartTime": start,
        "forecastEndTime": end,
        "temperatureMin": {"value": minimum, "unit": minimum_unit},
        "temperatureMax": {"value": maximum, "unit": maximum_unit},
        "daytime": {"condition": {"text": condition_day, "code": "101"}},
        "nighttime": {"condition": {"text": condition_night, "code": "305"}},
    }


def _forecast_response(*days: object) -> dict[str, object]:
    return {
        "metadata": {
            "tag": "forecast-test-tag",
            "attributions": ["https://developer.qweather.com/attribution.html"],
        },
        "days": list(days) if days else [_day(date(2026, 8, 15)), _day(date(2026, 8, 16))],
    }


def _alert(
    alert_id: object = "alert-001",
    *,
    headline: object = "杭州市暴雨橙色预警",
    severity: object = "severe",
    issued_time: object = "2026-08-14T14:30+08:00",
    expire_time: object = "2026-08-14T20:00+08:00",
    description: object = "预计未来三小时部分地区有强降雨。",
) -> dict[str, object]:
    return {
        "id": alert_id,
        "issuedTime": issued_time,
        "severity": severity,
        "headline": headline,
        "description": description,
        "expireTime": expire_time,
    }


def _alert_response(*alerts: object, zero_result: bool = False) -> dict[str, object]:
    return {
        "metadata": {
            "tag": "alert-test-tag",
            "zeroResult": zero_result,
            "attributions": ["https://developer.qweather.com/attribution.html"],
        },
        "alerts": list(alerts) if alerts else ([] if zero_result else [_alert()]),
    }


def _adapter(transport: httpx2.MockTransport) -> QWeatherAdapter:
    return QWeatherAdapter(
        QWeatherAdapterConfig(
            api_host=API_HOST,
            project_id=PROJECT_ID,
            credential_id=CREDENTIAL_ID,
            private_key_pem=PRIVATE_KEY_PEM,
        ),
        transport=transport,
        clock=lambda: FIXED_NOW,
        source_id_factory=lambda: FIXED_SOURCE_ID,
    )


def _decode_segment(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(value + padding)
    parsed = json.loads(decoded)
    return cast(dict[str, object], parsed)


@pytest.mark.anyio
async def test_forecast_uses_current_daily_endpoint_jwt_and_filters_requested_dates() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(
            200,
            json=_forecast_response(
                _day(date(2026, 8, 14)),
                _day(date(2026, 8, 15)),
                _day(date(2026, 8, 16)),
                _day(date(2026, 8, 17)),
            ),
        )

    result = await _adapter(httpx2.MockTransport(handler)).get_weather_forecast(_forecast_request())

    assert result.status is ProviderResultStatus.OK
    assert result.provider is Provider.QWEATHER
    assert result.data is not None
    assert result.data.location_id == LOCATION_ID
    assert tuple(item.forecast_date for item in result.data.days) == (
        date(2026, 8, 15),
        date(2026, 8, 16),
    )
    assert result.data.days[0].temperature_min_celsius == Decimal("25.25")
    assert result.data.days[0].temperature_max_celsius == Decimal("34.5")
    assert result.data.days[0].condition_day == "多云"
    assert result.data.days[0].condition_night == "阵雨"
    assert result.fetched_at == FIXED_NOW
    assert result.valid_until is None
    assert result.error is None
    assert result.source_records[0].source_id == FIXED_SOURCE_ID
    assert result.source_records[0].source_type == "qweather_daily_forecast"
    assert result.source_records[0].reference_url == QWEATHER_REFERENCE_URL
    assert result.source_records[0].attributions == (
        "https://developer.qweather.com/attribution.html",
    )

    assert len(observed) == 1
    request = observed[0]
    assert request.method == "GET"
    assert request.url.host == API_HOST
    assert request.url.path == "/weather/v1/daily/30.27/120.16"
    assert dict(request.url.params) == {"days": "7", "localTime": "true", "lang": "zh"}
    assert "key" not in request.url.params

    scheme, token = request.headers["Authorization"].split(" ", 1)
    assert scheme == "Bearer"
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    assert _decode_segment(encoded_header) == {"alg": "EdDSA", "kid": CREDENTIAL_ID}
    assert _decode_segment(encoded_payload) == {
        "sub": PROJECT_ID,
        "iat": int(FIXED_NOW.timestamp()) - 30,
        "exp": int(FIXED_NOW.timestamp()) + 870,
    }
    signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
    PRIVATE_KEY.public_key().verify(
        signature,
        f"{encoded_header}.{encoded_payload}".encode("ascii"),
    )


@pytest.mark.anyio
async def test_current_alert_request_uses_latitude_then_longitude_and_maps_alert() -> None:
    observed: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(200, json=_alert_response())

    result = await _adapter(httpx2.MockTransport(handler)).get_current_weather_alerts(
        _alert_request()
    )

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.location_id == LOCATION_ID
    assert len(result.data.alerts) == 1
    alert = result.data.alerts[0]
    assert alert.alert_id == "alert-001"
    assert alert.title == "杭州市暴雨橙色预警"
    assert alert.severity == "severe"
    assert alert.issued_at == datetime.fromisoformat("2026-08-14T14:30+08:00")
    assert alert.description == "预计未来三小时部分地区有强降雨。"
    assert result.valid_until == datetime.fromisoformat("2026-08-14T20:00+08:00")
    assert result.source_records[0].valid_until == result.valid_until
    assert result.source_records[0].source_type == "qweather_current_alerts"
    assert result.source_records[0].reference_url == QWEATHER_REFERENCE_URL
    assert result.source_records[0].attributions == (
        "https://developer.qweather.com/attribution.html",
    )

    assert len(observed) == 1
    request = observed[0]
    assert request.url.path == "/weatheralert/v1/current/30.27/120.16"
    assert dict(request.url.params) == {"localTime": "true", "lang": "zh"}
    assert request.headers["Authorization"].startswith("Bearer ")


@pytest.mark.anyio
async def test_zero_result_is_a_successful_empty_current_alert_snapshot() -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(200, json=_alert_response(zero_result=True))
        )
    ).get_current_weather_alerts(_alert_request())

    assert result.status is ProviderResultStatus.OK
    assert result.data is not None
    assert result.data.alerts == ()
    assert result.error is None
    assert result.source_records


@pytest.mark.anyio
async def test_missing_forecast_day_returns_partial_without_inventing_data() -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(
                200,
                json=_forecast_response(_day(date(2026, 8, 15))),
            )
        )
    ).get_weather_forecast(_forecast_request())

    assert result.status is ProviderResultStatus.PARTIAL
    assert result.data is not None
    assert tuple(item.forecast_date for item in result.data.days) == (date(2026, 8, 15),)
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.EMPTY_RESULT


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"metadata": {}, "days": []},
        {"metadata": {"tag": "tag"}, "days": "not-a-list"},
        _forecast_response(
            *[_day(date(2026, 8, 15) + timedelta(days=index)) for index in range(11)]
        ),
        _forecast_response(_day(date(2026, 8, 15)), _day(date(2026, 8, 15))),
        _forecast_response(_day(date(2026, 8, 15), start_time="2026-08-15T00:00")),
        _forecast_response(_day(date(2026, 8, 15), minimum_unit="°F")),
        _forecast_response(_day(date(2026, 8, 15), maximum_unit="K")),
        _forecast_response(_day(date(2026, 8, 15), minimum="NaN")),
        _forecast_response(_day(date(2026, 8, 15), minimum=40, maximum=30)),
        _forecast_response(_day(date(2026, 8, 15), condition_day=[])),
        _forecast_response(_day(date(2026, 8, 15), condition_night="")),
    ],
)
async def test_malformed_forecast_responses_never_form_a_false_complete_result(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).get_weather_forecast(_forecast_request())

    assert result.status is not ProviderResultStatus.OK
    assert result.error is not None
    assert result.error.category in {
        ProviderErrorCategory.SCHEMA,
        ProviderErrorCategory.EMPTY_RESULT,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "attributions",
    [None, [], [""], ["unsafe\ncontrol"], ["x" * 501], [1]],
)
async def test_forecast_rejects_missing_or_unsafe_attribution_metadata(
    attributions: object,
) -> None:
    response = _forecast_response()
    metadata = cast(dict[str, object], response["metadata"])
    if attributions is None:
        metadata.pop("attributions")
    else:
        metadata["attributions"] = attributions

    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).get_weather_forecast(_forecast_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
async def test_one_bad_alert_is_ignored_as_partial_and_duplicate_ids_are_not_admitted() -> None:
    response = _alert_response(
        _alert(),
        _alert("bad-alert", issued_time="not-a-time"),
        _alert(),
    )
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).get_current_weather_alerts(_alert_request())

    assert result.status is ProviderResultStatus.PARTIAL
    assert result.data is not None
    assert tuple(item.alert_id for item in result.data.alerts) == ("alert-001",)
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
async def test_expired_alert_is_not_admitted_as_current() -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(
                200,
                json=_alert_response(_alert(expire_time="2026-08-14T14:59+08:00")),
            )
        )
    ).get_current_weather_alerts(_alert_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        {},
        {"metadata": {"tag": "tag", "zeroResult": "false"}, "alerts": []},
        {"metadata": {"tag": "tag", "zeroResult": False}, "alerts": "bad"},
        _alert_response(_alert(alert_id="")),
        _alert_response(_alert(headline=[])),
        _alert_response(_alert(severity=[])),
        _alert_response(_alert(description="")),
        _alert_response(_alert(issued_time="2026-08-14T14:30")),
        _alert_response(_alert(expire_time=None)),
        _alert_response(_alert(), zero_result=True),
    ],
)
async def test_malformed_alert_responses_are_safely_rejected(
    response: dict[str, object],
) -> None:
    result = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, json=response))
    ).get_current_weather_alerts(_alert_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status_code", "category"),
    [
        (400, ProviderErrorCategory.SCHEMA),
        (401, ProviderErrorCategory.AUTH),
        (403, ProviderErrorCategory.AUTH),
        (404, ProviderErrorCategory.SCHEMA),
        (405, ProviderErrorCategory.SCHEMA),
        (429, ProviderErrorCategory.RATE_LIMITED),
        (500, ProviderErrorCategory.SERVER),
        (418, ProviderErrorCategory.UNKNOWN),
    ],
)
async def test_http_failures_use_safe_project_categories(
    status_code: int,
    category: ProviderErrorCategory,
) -> None:
    result = await _adapter(
        httpx2.MockTransport(
            lambda request: httpx2.Response(
                status_code,
                content=b"private key and bearer must not escape",
            )
        )
    ).get_weather_forecast(_forecast_request())

    assert result.status is ProviderResultStatus.UNAVAILABLE
    assert result.error is not None
    assert result.error.category is category
    assert "private key" not in repr(result)
    assert "bearer" not in repr(result).lower()


@pytest.mark.anyio
async def test_transport_json_and_size_failures_are_safe() -> None:
    def timeout(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("sensitive token", request=request)

    first = await _adapter(httpx2.MockTransport(timeout)).get_weather_forecast(_forecast_request())
    second = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, content=b"not-json"))
    ).get_weather_forecast(_forecast_request())
    third = await _adapter(
        httpx2.MockTransport(lambda request: httpx2.Response(200, content=b"x" * 1_000_001))
    ).get_current_weather_alerts(_alert_request())

    assert first.error is not None
    assert first.error.category is ProviderErrorCategory.TIMEOUT
    assert second.error is not None
    assert second.error.category is ProviderErrorCategory.SCHEMA
    assert third.error is not None
    assert third.error.category is ProviderErrorCategory.SCHEMA
    assert "sensitive" not in repr((first, second, third))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "port_request",
    [
        replace(
            _forecast_request(),
            coordinates=Coordinates(Decimal("120"), Decimal("30"), CoordinateSystem.WGS84),
        ),
        replace(_forecast_request(), end_date=date(2026, 8, 17)),
        cast(WeatherForecastRequest, object()),
    ],
)
async def test_invalid_forecast_requests_fail_before_transport(
    port_request: WeatherForecastRequest,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(200, json=_forecast_response())

    result = await _adapter(httpx2.MockTransport(handler)).get_weather_forecast(port_request)

    assert calls == 0
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.anyio
async def test_invalid_alert_request_fails_before_transport() -> None:
    request = replace(
        _alert_request(),
        coordinates=Coordinates(Decimal("120"), Decimal("30"), CoordinateSystem.UNKNOWN),
    )
    calls = 0

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(200, json=_alert_response())

    result = await _adapter(httpx2.MockTransport(handler)).get_current_weather_alerts(request)

    assert calls == 0
    assert result.error is not None
    assert result.error.category is ProviderErrorCategory.SCHEMA


@pytest.mark.parametrize(
    "overrides",
    [
        {"api_host": "https://unit-test.qweatherapi.com"},
        {"api_host": "unit-test.qweatherapi.com/extra"},
        {"api_host": "unit-test.qweatherapi.com.evil.example"},
        {"project_id": ""},
        {"project_id": "bad\nvalue"},
        {"credential_id": ""},
        {"private_key_pem": b"not-a-key"},
        {"timeout_seconds": QWEATHER_TIMEOUT_SECONDS + 1},
    ],
)
def test_configuration_rejects_unsafe_or_unapproved_values(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "api_host": API_HOST,
        "project_id": PROJECT_ID,
        "credential_id": CREDENTIAL_ID,
        "private_key_pem": PRIVATE_KEY_PEM,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        QWeatherAdapterConfig(**values)  # type: ignore[arg-type]


def test_configuration_repr_hides_private_key_material() -> None:
    config = QWeatherAdapterConfig(
        API_HOST,
        PROJECT_ID,
        CREDENTIAL_ID,
        PRIVATE_KEY_PEM,
    )

    assert "private_key_pem" not in repr(config)
    assert PRIVATE_KEY_PEM.decode("ascii").splitlines()[1] not in repr(config)


def test_adapter_has_no_environment_logging_retry_or_sleep_backdoor() -> None:
    source_path = (
        Path(__file__).parents[2]
        / "src"
        / "intelligent_travel_assistant"
        / "adapters"
        / "providers"
        / "qweather.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import) and node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}

    assert imports.isdisjoint({"os", "logging", "time"})
    assert calls.isdisjoint({"print", "open", "sleep"})
    assert attributes.isdisjoint({"getenv", "environ"})
    assert "X-QW-Api-Key" not in source
