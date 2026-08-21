"""QWeather JWT adapter for daily forecasts and active weather alerts."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Final
from uuid import UUID, uuid4

import httpx2
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intelligent_travel_assistant.application.ports import (
    CurrentWeatherAlertsRequest,
    DailyWeather,
    WeatherAlert,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.tooling.resilience import (
    parse_retry_after_seconds,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    SourceRecord,
)

QWEATHER_TIMEOUT_SECONDS: Final = 6.0
QWEATHER_JWT_CLOCK_SKEW_SECONDS: Final = 30
QWEATHER_JWT_LIFETIME_SECONDS: Final = 900
MAX_RESPONSE_BYTES: Final = 1_000_000
MAX_FORECAST_DAYS: Final = 10
MAX_ALERTS: Final = 100

_HOST = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+qweatherapi\.com$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_COORDINATE_QUANTUM: Final = Decimal("0.01")
QWEATHER_REFERENCE_URL: Final = "https://www.qweather.com"


@dataclass(frozen=True, slots=True)
class QWeatherAdapterConfig:
    """Explicit JWT material; file/environment loading belongs to Step 32."""

    api_host: str
    project_id: str
    credential_id: str
    private_key_pem: bytes = field(repr=False)
    timeout_seconds: float = QWEATHER_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if (
            not isinstance(self.api_host, str)
            or len(self.api_host) > 253
            or _HOST.fullmatch(self.api_host) is None
        ):
            raise ValueError("qweather_api_host_invalid")
        if not _valid_identifier(self.project_id):
            raise ValueError("qweather_project_id_invalid")
        if not _valid_identifier(self.credential_id):
            raise ValueError("qweather_credential_id_invalid")
        _load_private_key(self.private_key_pem)
        if self.timeout_seconds != QWEATHER_TIMEOUT_SECONDS:
            raise ValueError("qweather_timeout_unapproved")


class QWeatherAdapter:
    """One JWT-authenticated HTTP attempt per explicitly invoked port call."""

    __slots__ = (
        "_clock",
        "_config",
        "_private_key",
        "_source_id_factory",
        "_transport",
    )

    def __init__(
        self,
        config: QWeatherAdapterConfig,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        source_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._config = config
        self._private_key = _load_private_key(config.private_key_pem)
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._source_id_factory = source_id_factory

    async def get_weather_forecast(
        self,
        request: WeatherForecastRequest,
    ) -> ProviderResult[WeatherForecastResult]:
        coordinates = _forecast_request_coordinates(request)
        if coordinates is None:
            return _unavailable(ProviderErrorCategory.SCHEMA)
        latitude, longitude = coordinates
        response = await self._get_json(
            f"/weather/v1/daily/{latitude}/{longitude}",
            {"days": "7", "localTime": "true", "lang": "zh"},
        )
        if isinstance(response, ProviderError):
            return _unavailable(response)
        value, fetched_at = response
        attributions = _response_attributions(value)
        if isinstance(attributions, ProviderErrorCategory):
            return _unavailable(attributions)
        parsed = _parse_forecast(value, request=request)
        if isinstance(parsed, ProviderErrorCategory):
            return _unavailable(parsed)
        days, error_category = parsed
        warnings = ["和风天气预报响应没有固定有效期。"]
        status = ProviderResultStatus.OK
        error = None
        if error_category is not None:
            status = ProviderResultStatus.PARTIAL
            error = ProviderError(error_category)
            warnings.append("和风天气预报只覆盖了部分请求日期或包含已忽略的坏记录。")
        return self._available(
            WeatherForecastResult(request.location_id, days),
            fetched_at=fetched_at,
            source_type="qweather_daily_forecast",
            warnings=tuple(warnings),
            status=status,
            error=error,
            attributions=attributions,
        )

    async def get_current_weather_alerts(
        self,
        request: CurrentWeatherAlertsRequest,
    ) -> ProviderResult[WeatherAlertsResult]:
        coordinates = _alert_request_coordinates(request)
        if coordinates is None:
            return _unavailable(ProviderErrorCategory.SCHEMA)
        latitude, longitude = coordinates
        response = await self._get_json(
            f"/weatheralert/v1/current/{latitude}/{longitude}",
            {"localTime": "true", "lang": "zh"},
        )
        if isinstance(response, ProviderError):
            return _unavailable(response)
        value, fetched_at = response
        attributions = _response_attributions(value)
        if isinstance(attributions, ProviderErrorCategory):
            return _unavailable(attributions)
        parsed = _parse_alerts(value, fetched_at=fetched_at)
        if isinstance(parsed, ProviderErrorCategory):
            return _unavailable(parsed)
        alerts, valid_until, error_category = parsed
        warnings = ["预警数据可能延迟或过期，紧急情况应以官方发布为准。"]
        if valid_until is None:
            warnings.append("和风天气当前预警响应没有固定有效期。")
        status = ProviderResultStatus.OK
        error = None
        if error_category is not None:
            status = ProviderResultStatus.PARTIAL
            error = ProviderError(error_category)
            warnings.append("和风天气当前预警响应不完整或包含已忽略的坏记录。")
        return self._available(
            WeatherAlertsResult(request.location_id, alerts),
            fetched_at=fetched_at,
            valid_until=valid_until,
            source_type="qweather_current_alerts",
            warnings=tuple(warnings),
            status=status,
            error=error,
            attributions=attributions,
        )

    async def _get_json(
        self,
        path: str,
        params: dict[str, str],
    ) -> tuple[dict[str, object], datetime] | ProviderError:
        issued_at = self._clock()
        if not _aware_datetime(issued_at):
            return ProviderError(ProviderErrorCategory.SCHEMA)
        token = _jwt_token(
            self._private_key,
            credential_id=self._config.credential_id,
            project_id=self._config.project_id,
            issued_at=issued_at,
        )
        try:
            async with httpx2.AsyncClient(
                base_url=f"https://{self._config.api_host}",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=self._config.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.get(path, params=params)
        except httpx2.TimeoutException:
            return ProviderError(ProviderErrorCategory.TIMEOUT)
        except httpx2.RequestError:
            return ProviderError(ProviderErrorCategory.UNKNOWN)

        http_error = _http_error(
            response.status_code,
            retry_after=response.headers.get("Retry-After"),
            now=self._clock() if response.status_code == 429 else None,
        )
        if http_error is not None:
            return http_error
        if len(response.content) > MAX_RESPONSE_BYTES:
            return ProviderError(ProviderErrorCategory.SCHEMA)
        try:
            value = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return ProviderError(ProviderErrorCategory.SCHEMA)
        if not isinstance(value, dict):
            return ProviderError(ProviderErrorCategory.SCHEMA)
        fetched_at = self._clock()
        if not _aware_datetime(fetched_at):
            return ProviderError(ProviderErrorCategory.SCHEMA)
        return value, fetched_at

    def _available[T](
        self,
        data: T,
        *,
        fetched_at: datetime,
        valid_until: datetime | None = None,
        source_type: str,
        warnings: tuple[str, ...],
        status: ProviderResultStatus,
        error: ProviderError | None,
        attributions: tuple[str, ...],
    ) -> ProviderResult[T]:
        source = SourceRecord(
            source_id=self._source_id_factory(),
            provider=Provider.QWEATHER,
            source_type=source_type,
            fetched_at=fetched_at,
            valid_until=valid_until,
            reference_url=QWEATHER_REFERENCE_URL,
            attributions=attributions,
        )
        return ProviderResult(
            status,
            Provider.QWEATHER,
            data,
            fetched_at,
            valid_until,
            warnings,
            error,
            (source,),
        )


def _response_attributions(
    value: dict[str, object],
) -> tuple[str, ...] | ProviderErrorCategory:
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        return ProviderErrorCategory.SCHEMA
    raw = metadata.get("attributions")
    if (
        not isinstance(raw, list)
        or not 1 <= len(raw) <= 10
        or any(
            not isinstance(item, str)
            or not item.strip()
            or len(item) > 500
            or _CONTROL.search(item) is not None
            for item in raw
        )
    ):
        return ProviderErrorCategory.SCHEMA
    return tuple(raw)


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _load_private_key(value: object) -> Ed25519PrivateKey:
    if not isinstance(value, bytes) or not value or len(value) > 16_384:
        raise ValueError("qweather_private_key_invalid")
    try:
        key = serialization.load_pem_private_key(value, password=None)
    except (TypeError, ValueError) as error:
        raise ValueError("qweather_private_key_invalid") from error
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("qweather_private_key_invalid")
    return key


def _jwt_token(
    private_key: Ed25519PrivateKey,
    *,
    credential_id: str,
    project_id: str,
    issued_at: datetime,
) -> str:
    issued_timestamp = int(issued_at.timestamp()) - QWEATHER_JWT_CLOCK_SKEW_SECONDS
    header = _base64url_json({"alg": "EdDSA", "kid": credential_id})
    payload = _base64url_json(
        {
            "sub": project_id,
            "iat": issued_timestamp,
            "exp": issued_timestamp + QWEATHER_JWT_LIFETIME_SECONDS,
        }
    )
    unsigned = f"{header}.{payload}"
    signature = _base64url(private_key.sign(unsigned.encode("ascii")))
    return f"{unsigned}.{signature}"


def _base64url_json(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return _base64url(encoded)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _forecast_request_coordinates(request: object) -> tuple[str, str] | None:
    if (
        not isinstance(request, WeatherForecastRequest)
        or not isinstance(request.location_id, UUID)
        or not _provider_coordinates(request.coordinates)
        or not _plain_date(request.start_date)
        or not _plain_date(request.end_date)
        or not 1 <= (request.end_date - request.start_date).days <= 6
    ):
        return None
    return _coordinate_path(request.coordinates)


def _alert_request_coordinates(request: object) -> tuple[str, str] | None:
    if (
        not isinstance(request, CurrentWeatherAlertsRequest)
        or not isinstance(request.location_id, UUID)
        or not _provider_coordinates(request.coordinates)
    ):
        return None
    return _coordinate_path(request.coordinates)


def _provider_coordinates(value: object) -> bool:
    return (
        isinstance(value, Coordinates)
        and value.coordinate_system is CoordinateSystem.PROVIDER_NATIVE
    )


def _coordinate_path(value: Coordinates) -> tuple[str, str] | None:
    try:
        latitude = value.latitude.quantize(_COORDINATE_QUANTUM, rounding=ROUND_HALF_UP)
        longitude = value.longitude.quantize(_COORDINATE_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return format(latitude, "f"), format(longitude, "f")


def _plain_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _parse_forecast(
    value: dict[str, object],
    *,
    request: WeatherForecastRequest,
) -> tuple[tuple[DailyWeather, ...], ProviderErrorCategory | None] | ProviderErrorCategory:
    if not _valid_metadata(value.get("metadata"), require_zero_result=False):
        return ProviderErrorCategory.SCHEMA
    raw_days = value.get("days")
    if not isinstance(raw_days, list) or len(raw_days) > MAX_FORECAST_DAYS:
        return ProviderErrorCategory.SCHEMA
    if not raw_days:
        return ProviderErrorCategory.EMPTY_RESULT

    parsed_by_date: dict[date, DailyWeather] = {}
    ignored_invalid = False
    for raw_day in raw_days:
        parsed = _parse_day(raw_day)
        if parsed is None:
            ignored_invalid = True
            continue
        if parsed.forecast_date in parsed_by_date:
            ignored_invalid = True
            continue
        parsed_by_date[parsed.forecast_date] = parsed

    expected_dates = tuple(
        request.start_date + timedelta(days=offset)
        for offset in range((request.end_date - request.start_date).days + 1)
    )
    selected = tuple(parsed_by_date[item] for item in expected_dates if item in parsed_by_date)
    if not selected:
        return (
            ProviderErrorCategory.SCHEMA if ignored_invalid else ProviderErrorCategory.EMPTY_RESULT
        )
    if ignored_invalid:
        return selected, ProviderErrorCategory.SCHEMA
    if len(selected) != len(expected_dates):
        return selected, ProviderErrorCategory.EMPTY_RESULT
    return selected, None


def _parse_day(value: object) -> DailyWeather | None:
    if not isinstance(value, dict):
        return None
    start = _parse_datetime(value.get("forecastStartTime"))
    end = _parse_datetime(value.get("forecastEndTime"))
    minimum = _temperature(value.get("temperatureMin"))
    maximum = _temperature(value.get("temperatureMax"))
    condition_day = _condition(value.get("daytime"))
    condition_night = _condition(value.get("nighttime"))
    if (
        start is None
        or end is None
        or end <= start
        or end - start > timedelta(days=2)
        or minimum is None
        or maximum is None
        or minimum > maximum
        or condition_day is None
        or condition_night is None
    ):
        return None
    return DailyWeather(start.date(), condition_day, condition_night, minimum, maximum)


def _temperature(value: object) -> Decimal | None:
    if not isinstance(value, dict) or value.get("unit") != "°C":
        return None
    raw = value.get("value")
    if not isinstance(raw, (int, float, Decimal)) or isinstance(raw, bool):
        return None
    try:
        parsed = Decimal(str(raw))
    except InvalidOperation:
        return None
    if not parsed.is_finite() or not Decimal("-100") <= parsed <= Decimal("100"):
        return None
    return parsed


def _condition(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    condition = value.get("condition")
    if not isinstance(condition, dict):
        return None
    text = condition.get("text")
    return text if _valid_text(text, max_length=200) else None


def _parse_alerts(
    value: dict[str, object],
    *,
    fetched_at: datetime,
) -> (
    tuple[tuple[WeatherAlert, ...], datetime | None, ProviderErrorCategory | None]
    | ProviderErrorCategory
):
    metadata = value.get("metadata")
    if not _valid_metadata(metadata, require_zero_result=True):
        return ProviderErrorCategory.SCHEMA
    assert isinstance(metadata, dict)
    zero_result = metadata["zeroResult"]
    raw_alerts = value.get("alerts")
    if not isinstance(raw_alerts, list) or len(raw_alerts) > MAX_ALERTS:
        return ProviderErrorCategory.SCHEMA
    if zero_result:
        return ((), None, None) if not raw_alerts else ProviderErrorCategory.SCHEMA
    if not raw_alerts:
        return (), None, ProviderErrorCategory.EMPTY_RESULT

    alerts: list[WeatherAlert] = []
    expiry_times: list[datetime] = []
    alert_ids: set[str] = set()
    ignored_invalid = False
    for raw_alert in raw_alerts:
        parsed_alert = _parse_alert(raw_alert)
        if parsed_alert is None:
            ignored_invalid = True
            continue
        alert, expires_at = parsed_alert
        if expires_at <= fetched_at or alert.alert_id in alert_ids:
            ignored_invalid = True
            continue
        alert_ids.add(alert.alert_id)
        alerts.append(alert)
        expiry_times.append(expires_at)
    if not alerts:
        return ProviderErrorCategory.SCHEMA
    return (
        tuple(alerts),
        min(expiry_times),
        ProviderErrorCategory.SCHEMA if ignored_invalid else None,
    )


def _parse_alert(value: object) -> tuple[WeatherAlert, datetime] | None:
    if not isinstance(value, dict):
        return None
    alert_id = value.get("id")
    title = value.get("headline")
    severity = value.get("severity")
    description = value.get("description")
    issued_raw = value.get("issuedTime")
    expires_at = _parse_datetime(value.get("expireTime"))
    if (
        not _valid_text(alert_id, max_length=200)
        or not _valid_text(title, max_length=300)
        or not (severity is None or _valid_text(severity, max_length=100))
        or not _valid_description(description)
        or expires_at is None
    ):
        return None
    issued_at = None
    if issued_raw is not None:
        issued_at = _parse_datetime(issued_raw)
        if issued_at is None:
            return None
    assert isinstance(alert_id, str)
    assert isinstance(title, str)
    assert severity is None or isinstance(severity, str)
    assert isinstance(description, str)
    return WeatherAlert(alert_id, title, severity, issued_at, description), expires_at


def _valid_metadata(value: object, *, require_zero_result: bool) -> bool:
    if not isinstance(value, dict) or not _valid_text(value.get("tag"), max_length=256):
        return False
    if require_zero_result and not isinstance(value.get("zeroResult"), bool):
        return False
    return True


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value or len(value) > 100:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if _aware_datetime(parsed) else None


def _aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _valid_text(value: object, *, max_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= max_length
        and "\n" not in value
        and "\r" not in value
        and _CONTROL.search(value) is None
    )


def _valid_description(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and len(value) <= 20_000
        and _CONTROL.search(value) is None
    )


def _http_error_category(status_code: int) -> ProviderErrorCategory | None:
    if status_code == 200:
        return None
    if status_code in {400, 404, 405, 422}:
        return ProviderErrorCategory.SCHEMA
    if status_code in {401, 402, 403}:
        return ProviderErrorCategory.AUTH
    if status_code == 429:
        return ProviderErrorCategory.RATE_LIMITED
    if 500 <= status_code <= 599:
        return ProviderErrorCategory.SERVER
    return ProviderErrorCategory.UNKNOWN


def _http_error(
    status_code: int,
    *,
    retry_after: str | None,
    now: datetime | None,
) -> ProviderError | None:
    category = _http_error_category(status_code)
    if category is None:
        return None
    if category is ProviderErrorCategory.RATE_LIMITED and now is not None:
        return ProviderError(
            category,
            retry_after_seconds=parse_retry_after_seconds(retry_after, now=now),
        )
    return ProviderError(category)


def _unavailable[T](error: ProviderErrorCategory | ProviderError) -> ProviderResult[T]:
    normalized = error if isinstance(error, ProviderError) else ProviderError(error)
    return ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        Provider.QWEATHER,
        None,
        None,
        None,
        (),
        normalized,
        (),
    )
