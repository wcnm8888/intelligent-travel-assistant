"""Deterministic provider-port fakes with no external side effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from intelligent_travel_assistant.application.ports.models import (
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    ModelTextOutput,
    PlanningContext,
    PlanRepairBrief,
    PoiSearchRequest,
    PoiSearchResult,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.domain import Provider, ProviderResult, RouteLeg


class FakeOperation(StrEnum):
    RESOLVE_CITY = "resolve_city"
    SEARCH_POIS = "search_pois"
    CALCULATE_ROUTES = "calculate_routes"
    GET_WEATHER_FORECAST = "get_weather_forecast"
    GET_CURRENT_WEATHER_ALERTS = "get_current_weather_alerts"
    GENERATE_PLAN_CANDIDATE = "generate_plan_candidate"
    REPAIR_PLAN_CANDIDATE = "repair_plan_candidate"


type FakeRequest = (
    CityResolutionRequest
    | PoiSearchRequest
    | RouteCalculationRequest
    | WeatherForecastRequest
    | CurrentWeatherAlertsRequest
    | PlanningContext
    | PlanRepairBrief
)


@dataclass(frozen=True, slots=True)
class FakeCall:
    """Immutable invocation snapshot; request DTOs are frozen as well."""

    sequence: int
    operation: FakeOperation
    request: FakeRequest


class FakeScriptError(RuntimeError):
    """Stable, safe failure for invalid or depleted test configuration."""

    __slots__ = ("code", "operation")

    def __init__(self, code: str, operation: FakeOperation) -> None:
        self.code = code
        self.operation = operation
        super().__init__(f"{code}: {operation.value}")


class _Script[T]:
    __slots__ = ("_cursor", "_results", "operation", "provider")

    def __init__(
        self,
        operation: FakeOperation,
        provider: Provider,
        results: tuple[ProviderResult[T], ...] | None,
    ) -> None:
        self.operation = operation
        self.provider = provider
        self._results = results
        self._cursor = 0
        if results is not None:
            for result in results:
                _require_synthetic_result(result, provider=provider, operation=operation)

    def take(self) -> ProviderResult[T]:
        if self._results is None:
            raise FakeScriptError("fake_script_unconfigured", self.operation)
        if self._cursor >= len(self._results):
            raise FakeScriptError("fake_script_exhausted", self.operation)
        result = self._results[self._cursor]
        self._cursor += 1
        return result


class _CallRecorder:
    __slots__ = ("_calls",)

    def __init__(self) -> None:
        self._calls: list[FakeCall] = []

    @property
    def calls(self) -> tuple[FakeCall, ...]:
        return tuple(self._calls)

    def _record(self, operation: FakeOperation, request: FakeRequest) -> None:
        self._calls.append(FakeCall(len(self._calls) + 1, operation, request))


class FakeAmapAdapter(_CallRecorder):
    """Programmable Amap port fake; scripts are isolated per operation."""

    __slots__ = ("_calculate_routes", "_resolve_city", "_search_pois")
    is_synthetic: ClassVar[bool] = True

    def __init__(
        self,
        *,
        resolve_city_results: tuple[ProviderResult[CityResolution], ...] | None = None,
        search_pois_results: tuple[ProviderResult[PoiSearchResult], ...] | None = None,
        calculate_routes_results: tuple[ProviderResult[RouteLeg], ...] | None = None,
    ) -> None:
        super().__init__()
        self._resolve_city = _Script(
            FakeOperation.RESOLVE_CITY,
            Provider.AMAP,
            resolve_city_results,
        )
        self._search_pois = _Script(
            FakeOperation.SEARCH_POIS,
            Provider.AMAP,
            search_pois_results,
        )
        self._calculate_routes = _Script(
            FakeOperation.CALCULATE_ROUTES,
            Provider.AMAP,
            calculate_routes_results,
        )

    async def resolve_city(
        self,
        request: CityResolutionRequest,
    ) -> ProviderResult[CityResolution]:
        self._record(FakeOperation.RESOLVE_CITY, request)
        return self._resolve_city.take()

    async def search_pois(
        self,
        request: PoiSearchRequest,
    ) -> ProviderResult[PoiSearchResult]:
        self._record(FakeOperation.SEARCH_POIS, request)
        return self._search_pois.take()

    async def calculate_routes(
        self,
        request: RouteCalculationRequest,
    ) -> ProviderResult[RouteLeg]:
        self._record(FakeOperation.CALCULATE_ROUTES, request)
        return self._calculate_routes.take()


class FakeQWeatherAdapter(_CallRecorder):
    """Programmable QWeather port fake; scripts are isolated per operation."""

    __slots__ = ("_weather_alerts", "_weather_forecast")
    is_synthetic: ClassVar[bool] = True

    def __init__(
        self,
        *,
        weather_forecast_results: tuple[ProviderResult[WeatherForecastResult], ...] | None = None,
        weather_alert_results: tuple[ProviderResult[WeatherAlertsResult], ...] | None = None,
    ) -> None:
        super().__init__()
        self._weather_forecast = _Script(
            FakeOperation.GET_WEATHER_FORECAST,
            Provider.QWEATHER,
            weather_forecast_results,
        )
        self._weather_alerts = _Script(
            FakeOperation.GET_CURRENT_WEATHER_ALERTS,
            Provider.QWEATHER,
            weather_alert_results,
        )

    async def get_weather_forecast(
        self,
        request: WeatherForecastRequest,
    ) -> ProviderResult[WeatherForecastResult]:
        self._record(FakeOperation.GET_WEATHER_FORECAST, request)
        return self._weather_forecast.take()

    async def get_current_weather_alerts(
        self,
        request: CurrentWeatherAlertsRequest,
    ) -> ProviderResult[WeatherAlertsResult]:
        self._record(FakeOperation.GET_CURRENT_WEATHER_ALERTS, request)
        return self._weather_alerts.take()


class FakeDeepSeekAdapter(_CallRecorder):
    """Programmable DeepSeek port fake without model or transport behavior."""

    __slots__ = ("_generation", "_repair")
    is_synthetic: ClassVar[bool] = True

    def __init__(
        self,
        *,
        generation_results: tuple[ProviderResult[ModelTextOutput], ...] | None = None,
        repair_results: tuple[ProviderResult[ModelTextOutput], ...] | None = None,
    ) -> None:
        super().__init__()
        self._generation = _Script(
            FakeOperation.GENERATE_PLAN_CANDIDATE,
            Provider.DEEPSEEK,
            generation_results,
        )
        self._repair = _Script(
            FakeOperation.REPAIR_PLAN_CANDIDATE,
            Provider.DEEPSEEK,
            repair_results,
        )

    async def generate_plan_candidate(
        self,
        request: PlanningContext,
    ) -> ProviderResult[ModelTextOutput]:
        self._record(FakeOperation.GENERATE_PLAN_CANDIDATE, request)
        return self._generation.take()

    async def repair_plan_candidate(
        self,
        request: PlanRepairBrief,
    ) -> ProviderResult[ModelTextOutput]:
        self._record(FakeOperation.REPAIR_PLAN_CANDIDATE, request)
        return self._repair.take()


def _require_synthetic_result[T](
    result: ProviderResult[T],
    *,
    provider: Provider,
    operation: FakeOperation,
) -> None:
    if result.provider is not provider:
        raise FakeScriptError("fake_result_provider_mismatch", operation)
    has_synthetic_warning = any("synthetic" in warning.casefold() for warning in result.warnings)
    sources_are_synthetic = all(
        record.source_type.casefold().startswith("synthetic_") for record in result.source_records
    )
    if not has_synthetic_warning or not sources_are_synthetic:
        raise FakeScriptError("fake_result_not_synthetic", operation)
