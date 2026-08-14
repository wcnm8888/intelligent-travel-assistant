"""Cross-provider offline transport failure matrix for F-001 Step 33."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intelligent_travel_assistant.adapters.providers import (
    AmapAdapter,
    AmapAdapterConfig,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
    QWeatherAdapter,
    QWeatherAdapterConfig,
)
from intelligent_travel_assistant.application.ports import (
    CityResolutionRequest,
    PlanningContext,
    WeatherForecastRequest,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Money,
    Provider,
    ProviderErrorCategory,
    ProviderErrorCode,
    ProviderResult,
    ProviderResultStatus,
)

FIXED_NOW = datetime(2026, 8, 14, 7, 0, tzinfo=UTC)
LOCATION_ID = UUID("90000000-0000-4000-8000-000000000033")
SOURCE_ID = UUID("70000000-0000-4000-8000-000000000033")
TEST_DEEPSEEK_AUTH = "test-only-deepseek-matrix-value"
TEST_AMAP_AUTH = "test-only-amap-matrix-value"
PRIVATE_KEY_PEM = Ed25519PrivateKey.from_private_bytes(b"\x02" * 32).private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)


@dataclass(frozen=True, slots=True)
class FailureScenario:
    name: str
    expected_category: ProviderErrorCategory | None
    expected_code: ProviderErrorCode | None
    retryable: bool


SCENARIOS = (
    FailureScenario("success", None, None, False),
    FailureScenario(
        "empty",
        ProviderErrorCategory.EMPTY_RESULT,
        ProviderErrorCode.DATA_MISSING,
        False,
    ),
    FailureScenario(
        "unauthorized_401",
        ProviderErrorCategory.AUTH,
        ProviderErrorCode.UNAUTHORIZED,
        False,
    ),
    FailureScenario(
        "forbidden_403",
        ProviderErrorCategory.AUTH,
        ProviderErrorCode.UNAUTHORIZED,
        False,
    ),
    FailureScenario(
        "rate_limited",
        ProviderErrorCategory.RATE_LIMITED,
        ProviderErrorCode.RATE_LIMITED,
        True,
    ),
    FailureScenario(
        "timeout",
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCode.TIMEOUT,
        True,
    ),
    FailureScenario(
        "server_503",
        ProviderErrorCategory.SERVER,
        ProviderErrorCode.UNAVAILABLE,
        True,
    ),
    FailureScenario(
        "schema_drift",
        ProviderErrorCategory.SCHEMA,
        ProviderErrorCode.SCHEMA_INVALID,
        False,
    ),
    FailureScenario(
        "connection_failure",
        ProviderErrorCategory.UNKNOWN,
        ProviderErrorCode.UNAVAILABLE,
        False,
    ),
)
EXTERNAL_PROVIDERS = (Provider.DEEPSEEK, Provider.AMAP, Provider.QWEATHER)


@pytest.mark.anyio
@pytest.mark.parametrize("provider", EXTERNAL_PROVIDERS, ids=lambda item: item.value)
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item.name)
async def test_provider_transport_failure_matrix_is_safe_and_single_attempt(
    provider: Provider,
    scenario: FailureScenario,
) -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if scenario.name == "timeout":
            raise httpx2.ReadTimeout("sensitive upstream timeout detail", request=request)
        if scenario.name == "connection_failure":
            raise httpx2.ConnectError("sensitive upstream connection detail", request=request)
        return _response(provider, scenario.name)

    result = await _invoke(provider, httpx2.MockTransport(handler))

    assert calls == 1
    assert result.provider is provider
    if scenario.expected_category is None:
        assert result.status is ProviderResultStatus.OK
        assert result.data is not None
        assert result.error is None
    else:
        assert result.status is ProviderResultStatus.UNAVAILABLE
        assert result.data is None
        assert result.source_records == ()
        assert result.error is not None
        assert result.error.category is scenario.expected_category
        assert result.error.code is scenario.expected_code
        assert result.error.retryable is scenario.retryable
    rendered = repr(result).lower()
    assert "sensitive upstream" not in rendered
    assert TEST_DEEPSEEK_AUTH not in rendered
    assert TEST_AMAP_AUTH not in rendered
    assert "private key" not in rendered


async def _invoke(
    provider: Provider,
    transport: httpx2.MockTransport,
) -> ProviderResult[object]:
    if provider is Provider.DEEPSEEK:
        deepseek = DeepSeekAdapter(
            DeepSeekAdapterConfig(api_key=TEST_DEEPSEEK_AUTH),
            transport=transport,
            clock=lambda: FIXED_NOW,
            source_id_factory=lambda: SOURCE_ID,
        )
        return cast(ProviderResult[object], await deepseek.generate_plan_candidate(_context()))
    if provider is Provider.AMAP:
        amap = AmapAdapter(
            AmapAdapterConfig(web_service_key=TEST_AMAP_AUTH),
            transport=transport,
            clock=lambda: FIXED_NOW,
            source_id_factory=lambda: SOURCE_ID,
        )
        return cast(
            ProviderResult[object],
            await amap.resolve_city(CityResolutionRequest("杭州市")),
        )
    qweather = QWeatherAdapter(
        QWeatherAdapterConfig(
            api_host="matrix.qweatherapi.com",
            project_id="MATRIXPROJECT",
            credential_id="MATRIXCREDENTIAL",
            private_key_pem=PRIVATE_KEY_PEM,
        ),
        transport=transport,
        clock=lambda: FIXED_NOW,
        source_id_factory=lambda: SOURCE_ID,
    )
    return cast(
        ProviderResult[object],
        await qweather.get_weather_forecast(
            WeatherForecastRequest(
                LOCATION_ID,
                Coordinates(
                    Decimal("120.155070"),
                    Decimal("30.274085"),
                    CoordinateSystem.PROVIDER_NATIVE,
                ),
                date(2026, 8, 15),
                date(2026, 8, 16),
            )
        ),
    )


def _response(provider: Provider, scenario: str) -> httpx2.Response:
    status_codes = {
        "unauthorized_401": 401,
        "forbidden_403": 403,
        "rate_limited": 429,
        "server_503": 503,
    }
    if scenario in status_codes:
        return httpx2.Response(
            status_codes[scenario],
            content=b"sensitive upstream credential material",
        )
    if scenario == "schema_drift":
        return httpx2.Response(200, json={"unexpected": "shape"})
    if provider is Provider.DEEPSEEK:
        return httpx2.Response(200, json=_deepseek_response(empty=scenario == "empty"))
    if provider is Provider.AMAP:
        return httpx2.Response(200, json=_amap_response(empty=scenario == "empty"))
    return httpx2.Response(200, json=_qweather_response(empty=scenario == "empty"))


def _deepseek_response(*, empty: bool) -> dict[str, object]:
    return {
        "object": "chat.completion",
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": " " if empty else '{"intent_summary":"matrix"}',
                    "reasoning_content": None,
                },
                "finish_reason": "stop",
            }
        ],
    }


def _amap_response(*, empty: bool) -> dict[str, object]:
    geocodes: list[dict[str, object]] = []
    if not empty:
        geocodes.append(
            {
                "formatted_address": "浙江省杭州市",
                "country": "中国",
                "province": "浙江省",
                "city": "杭州市",
                "citycode": "0571",
                "district": [],
                "street": [],
                "number": [],
                "adcode": "330100",
                "location": "120.155070,30.274085",
                "level": "市",
            }
        )
    return {
        "status": "1",
        "info": "OK",
        "infocode": "10000",
        "count": str(len(geocodes)),
        "geocodes": geocodes,
    }


def _qweather_response(*, empty: bool) -> dict[str, object]:
    days: list[dict[str, object]] = []
    if not empty:
        for local_date in (date(2026, 8, 15), date(2026, 8, 16)):
            days.append(
                {
                    "forecastStartTime": f"{local_date.isoformat()}T00:00+08:00",
                    "forecastEndTime": (
                        f"{(local_date + timedelta(days=1)).isoformat()}T00:00+08:00"
                    ),
                    "temperatureMin": {"value": 25, "unit": "°C"},
                    "temperatureMax": {"value": 34, "unit": "°C"},
                    "daytime": {"condition": {"text": "多云", "code": "101"}},
                    "nighttime": {"condition": {"text": "阵雨", "code": "305"}},
                }
            )
    return {
        "metadata": {
            "tag": "matrix",
            "attributions": ["QWeather synthetic attribution"],
        },
        "days": days,
    }


def _context() -> PlanningContext:
    return PlanningContext(
        city_name="杭州市",
        city_adcode="330100",
        start_date=date(2026, 8, 15),
        end_date=date(2026, 8, 16),
        travelers=2,
        budget=Money(Decimal("4000.00")),
        interests=("历史",),
        hard_constraints=(),
        allowed_tools=(),
        locations=(),
        observations=(),
    )
