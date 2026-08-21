"""Provider-neutral values crossing application port boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.domain import Coordinates, Money, RouteMode

_UNSAFE_DISPLAY_LABEL: Final = re.compile(
    r"ignore\s+(?:all\s+)?previous\s+instructions|<\|(?:system|assistant|tool)\|>|"
    r"assistant\s+to=|system\s+prompt|tool[_ -]?(?:call|result)|arbitrary_http|"
    r"(?:system|assistant|developer)\s*:",
    re.IGNORECASE,
)
_SAFE_DISPLAY_LABEL: Final = re.compile(
    r"(?:city:[0-9]{6}|location:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}|observation:[a-z0-9_:-]{1,64})"
)
_SAFE_TOKEN: Final = re.compile(r"[a-z0-9_:-]{1,64}")


class PlanningToolName(StrEnum):
    RESOLVE_CITY = "resolve_city"
    SEARCH_POIS = "search_pois"
    GET_WEATHER_FORECAST = "get_weather_forecast"
    GET_CURRENT_WEATHER_ALERTS = "get_current_weather_alerts"
    CALCULATE_ROUTES = "calculate_routes"


class CandidateValidationCode(StrEnum):
    JSON_INVALID = "candidate_json_invalid"
    SCHEMA_INVALID = "candidate_schema_invalid"
    DATE_INVALID = "candidate_date_invalid"
    TIME_INVALID = "candidate_time_invalid"
    POI_REFERENCE_INVALID = "candidate_poi_reference_invalid"
    SOURCE_REFERENCE_INVALID = "candidate_source_reference_invalid"
    UNSAFE_TEXT = "candidate_unsafe_text"
    OUTPUT_TRUNCATED = "candidate_output_truncated"


class CandidateTimeFailureCode(StrEnum):
    """Safe, closed-set reasons for locally rejected candidate schedules."""

    ACTIVITY_OUTSIDE_DAY_WINDOW = "activity_outside_day_window"
    ACCOMMODATION_TO_FIRST_GAP_NOT_POSITIVE = "accommodation_to_first_gap_not_positive"
    BETWEEN_LOCATIONS_GAP_NOT_POSITIVE = "between_locations_gap_not_positive"
    LAST_TO_ACCOMMODATION_GAP_NOT_POSITIVE = "last_to_accommodation_gap_not_positive"
    DAY_SCHEDULE_CAPACITY_EXCEEDED = "day_schedule_capacity_exceeded"


class ActivitySelectionKind(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class ActivityDurationClass(StrEnum):
    SHORT = "short"
    STANDARD = "standard"
    LONG = "long"
    UNKNOWN = "unknown"


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
    request_version: str | None = None
    expected_dates: tuple[date, ...] = ()
    city_adcodes: tuple[str, ...] = ()
    day_city_indices: tuple[tuple[int, int, int], ...] = ()
    accommodations: tuple[PlanningLocation, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelTextOutput:
    content: str
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class PlanRepairLocation:
    location_id: UUID
    display_label: str | None
    category: str | None
    city_adcode: str


@dataclass(frozen=True, slots=True)
class PlanRepairBrief:
    request_version: str | None
    expected_dates: tuple[date, ...]
    day_windows: tuple[PlanningDayWindow, ...]
    day_city_indices: tuple[tuple[int, int, int], ...]
    city_adcodes: tuple[str, ...]
    locations: tuple[PlanRepairLocation, ...]
    activity_source_ids: tuple[UUID, ...]
    validation_code: CandidateValidationCode
    validation_time_failure: CandidateTimeFailureCode | None = None
    affected_refs: tuple[UUID, ...] = ()
    command_category: str | None = None


def bounded_display_label(value: object) -> str | None:
    """Admit only project-generated opaque aliases, never external free text."""

    if not isinstance(value, str) or _SAFE_DISPLAY_LABEL.fullmatch(value) is None:
        return None
    return value


def bounded_project_token(value: object) -> str | None:
    """Admit project-owned enum-like tokens, never free Provider text."""

    if (
        not isinstance(value, str)
        or _SAFE_TOKEN.fullmatch(value) is None
        or _UNSAFE_DISPLAY_LABEL.search(value) is not None
    ):
        return None
    return value


@dataclass(frozen=True, slots=True)
class ActivitySelection:
    location_id: UUID
    local_date: date
    title: str
    priority_rank: int
    selection_kind: ActivitySelectionKind
    duration_class: ActivityDurationClass
    source_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ProposalDay:
    local_date: date
    selections: tuple[ActivitySelection, ...]
    departure_city_index: int | None = None
    arrival_city_index: int | None = None
    overnight_city_index: int | None = None


@dataclass(frozen=True, slots=True)
class PlanProposal:
    intent_summary: str
    days: tuple[ProposalDay, ...]
    explanation: str
    warnings: tuple[str, ...]


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
