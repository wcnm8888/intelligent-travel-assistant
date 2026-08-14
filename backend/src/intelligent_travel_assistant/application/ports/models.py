"""Provider-neutral values crossing application port boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from intelligent_travel_assistant.domain import Coordinates, Money, RouteMode


class PlanningToolName(StrEnum):
    RESOLVE_CITY = "resolve_city"
    SEARCH_POIS = "search_pois"
    GET_WEATHER_FORECAST = "get_weather_forecast"
    GET_CURRENT_WEATHER_ALERTS = "get_current_weather_alerts"
    CALCULATE_ROUTES = "calculate_routes"


class CandidateValidationCode(StrEnum):
    JSON_INVALID = "candidate_json_invalid"
    SCHEMA_INVALID = "candidate_schema_invalid"
    REFERENCE_INVALID = "candidate_reference_invalid"
    UNSAFE_TEXT = "candidate_unsafe_text"
    OUTPUT_TRUNCATED = "candidate_output_truncated"


@dataclass(frozen=True, slots=True)
class CityResolutionRequest:
    city_text: str


@dataclass(frozen=True, slots=True)
class CityResolution:
    city_name: str
    adcode: str
    citycode: str
    center: Coordinates | None


@dataclass(frozen=True, slots=True)
class PoiSearchRequest:
    city_adcode: str
    keywords: tuple[str, ...]
    categories: tuple[str, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class PoiCandidate:
    location_id: UUID
    name: str
    category: str
    city_adcode: str
    address: str | None
    coordinates: Coordinates | None


@dataclass(frozen=True, slots=True)
class PoiSearchResult:
    candidates: tuple[PoiCandidate, ...]


@dataclass(frozen=True, slots=True)
class RouteCalculationRequest:
    origin_location_id: UUID
    destination_location_id: UUID
    origin: Coordinates
    destination: Coordinates
    origin_citycode: str
    destination_citycode: str
    mode: RouteMode


@dataclass(frozen=True, slots=True)
class WeatherForecastRequest:
    location_id: UUID
    coordinates: Coordinates
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class DailyWeather:
    forecast_date: date
    condition_day: str
    condition_night: str
    temperature_min_celsius: Decimal
    temperature_max_celsius: Decimal


@dataclass(frozen=True, slots=True)
class WeatherForecastResult:
    location_id: UUID
    days: tuple[DailyWeather, ...]


@dataclass(frozen=True, slots=True)
class CurrentWeatherAlertsRequest:
    location_id: UUID
    coordinates: Coordinates


@dataclass(frozen=True, slots=True)
class WeatherAlert:
    alert_id: str
    title: str
    severity: str | None
    issued_at: datetime | None
    description: str


@dataclass(frozen=True, slots=True)
class WeatherAlertsResult:
    location_id: UUID
    alerts: tuple[WeatherAlert, ...]


@dataclass(frozen=True, slots=True)
class PlanningLocation:
    location_id: UUID
    name: str
    category: str
    city_adcode: str


@dataclass(frozen=True, slots=True)
class PlanningObservation:
    kind: str
    summary: str
    source_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class PlanningDayWindow:
    day_offset: int
    start_time: time
    end_time: time


@dataclass(frozen=True, slots=True)
class PlanningContext:
    city_name: str
    city_adcode: str
    start_date: date
    end_date: date
    travelers: int
    budget: Money
    interests: tuple[str, ...]
    hard_constraints: tuple[str, ...]
    allowed_tools: tuple[PlanningToolName, ...]
    locations: tuple[PlanningLocation, ...]
    observations: tuple[PlanningObservation, ...]
    free_text: str = ""
    route_mode: RouteMode = RouteMode.WALKING
    day_windows: tuple[PlanningDayWindow, ...] = ()
    accommodation: PlanningLocation | None = None
    activity_source_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelTextOutput:
    content: str
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class PlanCandidateRepairRequest:
    context: PlanningContext
    invalid_output: str
    validation_code: CandidateValidationCode


@dataclass(frozen=True, slots=True)
class CandidateActivity:
    location_id: UUID
    local_date: date
    title: str
    start_time: time
    end_time: time
    source_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class CandidateDay:
    local_date: date
    activities: tuple[CandidateActivity, ...]


@dataclass(frozen=True, slots=True)
class PlanCandidate:
    intent_summary: str
    days: tuple[CandidateDay, ...]
    explanation: str
    warnings: tuple[str, ...]
