"""Provider-neutral F-009 ports; provider payloads never cross this module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from intelligent_travel_assistant.contracts.f009 import Gcj02Point, PoiOption, PoiPurpose
from intelligent_travel_assistant.contracts.trip_planning import TransportMode


class F009ProviderFailureKind(StrEnum):
    AUTH = "auth"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    SERVER = "server"
    SCHEMA = "schema"
    EMPTY_RESULT = "empty_result"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class F009ProviderFailure:
    kind: F009ProviderFailureKind
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class F009ProviderOutcome[T]:
    data: T | None
    failure: F009ProviderFailure | None = None

    def __post_init__(self) -> None:
        if (self.data is None) == (self.failure is None):
            raise ValueError("f009 provider outcome must contain data or failure")


@dataclass(frozen=True, slots=True)
class F009CityFact:
    city_name: str
    city_adcode: str
    citycode: str
    center: Gcj02Point | None


@dataclass(frozen=True, slots=True)
class F009PoiQuery:
    city_adcode: str
    purpose: PoiPurpose
    keywords: str
    district_adcode: str | None
    center: Gcj02Point | None
    radius_m: int | None
    category_codes: tuple[str, ...]
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class F009MapPinFact:
    label: str
    city_adcode: str
    district_adcode: str
    coordinate: Gcj02Point


@dataclass(frozen=True, slots=True)
class F009RouteQuery:
    origin_location_id: UUID
    destination_location_id: UUID
    origin_provider_place_id: str | None
    destination_provider_place_id: str | None
    origin: Gcj02Point
    destination: Gcj02Point
    origin_citycode: str
    destination_citycode: str
    mode: TransportMode


@dataclass(frozen=True, slots=True)
class F009RouteFact:
    distance_meters: int
    duration_minutes: int
    points: tuple[Gcj02Point, ...]


@dataclass(frozen=True, slots=True)
class F009NarrativeDay:
    local_date: date
    location_ids: tuple[UUID, ...]
    pace_note: str
    stop_narratives: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class F009Narrative:
    days: tuple[F009NarrativeDay, ...]
    global_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class F009NarrativeRequest:
    days: tuple[tuple[date, tuple[tuple[UUID, str, str], ...]], ...]
    pace: str
    uncertainties: tuple[str, ...]


class F009NarrativeProvider(Protocol):
    async def generate(
        self, request: F009NarrativeRequest
    ) -> F009ProviderOutcome[F009Narrative]: ...

    async def repair(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]: ...


@dataclass(frozen=True, slots=True)
class F014AdvisorRequest:
    user_message: str
    confirmed_preferences: tuple[tuple[str, str], ...]
    candidates: tuple[tuple[int, UUID, str, str], ...]
    conversation: tuple[tuple[str, str], ...] = ()
    recommendation_requested: bool = False


@dataclass(frozen=True, slots=True)
class F014AdvisorDraft:
    role: str
    question: str
    preference_values: tuple[tuple[str, str], ...] = ()
    candidate_indices: tuple[int, ...] = ()
    candidate_reasons: tuple[str, ...] = ()


class F014AdvisorProvider(Protocol):
    async def generate(
        self, request: F014AdvisorRequest
    ) -> F009ProviderOutcome[F014AdvisorDraft]: ...

    async def repair(
        self, request: F014AdvisorRequest
    ) -> F009ProviderOutcome[F014AdvisorDraft]: ...


class F009MapProvider(Protocol):
    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]: ...

    async def search_pois(
        self, query: F009PoiQuery
    ) -> F009ProviderOutcome[tuple[PoiOption, ...]]: ...

    async def reverse_geocode(
        self, coordinate: Gcj02Point
    ) -> F009ProviderOutcome[F009MapPinFact]: ...

    async def calculate_route(
        self, query: F009RouteQuery
    ) -> F009ProviderOutcome[F009RouteFact]: ...
