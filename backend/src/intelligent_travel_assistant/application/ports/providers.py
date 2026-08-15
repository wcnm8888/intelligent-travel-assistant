"""Narrow provider capabilities required by the F-001 application layer."""

from __future__ import annotations

from typing import Protocol

from intelligent_travel_assistant.application.ports.models import (
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    ModelTextOutput,
    PlanCandidateRepairRequest,
    PlanningContext,
    PoiSearchRequest,
    PoiSearchResult,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.domain import ProviderResult, RouteLeg


class AmapPort(Protocol):
    async def resolve_city(
        self, request: CityResolutionRequest
    ) -> ProviderResult[CityResolution]: ...

    async def search_pois(self, request: PoiSearchRequest) -> ProviderResult[PoiSearchResult]: ...

    async def calculate_routes(
        self, request: RouteCalculationRequest
    ) -> ProviderResult[RouteLeg]: ...


class QWeatherPort(Protocol):
    async def get_weather_forecast(
        self, request: WeatherForecastRequest
    ) -> ProviderResult[WeatherForecastResult]: ...

    async def get_current_weather_alerts(
        self, request: CurrentWeatherAlertsRequest
    ) -> ProviderResult[WeatherAlertsResult]: ...


class DeepSeekPort(Protocol):
    async def generate_plan_candidate(
        self, request: PlanningContext
    ) -> ProviderResult[ModelTextOutput]: ...

    async def repair_plan_candidate(
        self, request: PlanCandidateRepairRequest
    ) -> ProviderResult[ModelTextOutput]: ...
