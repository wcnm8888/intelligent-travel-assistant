"""Stable F-001 trip-planning request, result, and state contracts.

These models describe data exchanged across project boundaries. They do not
implement planning, provider access, persistence, or deterministic validators.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    Field,
    StringConstraints,
    WithJsonSchema,
    field_serializer,
    field_validator,
    model_validator,
)

from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.contracts.errors import ApiError
from intelligent_travel_assistant.domain import MAX_ROUTE_DISTANCE_METERS

ShortText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120),
]
LongText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=500),
]
CityText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=2, max_length=30),
]
Adcode = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^\d{6}$"),
]
PositiveMinutes = Annotated[int, Field(strict=True, ge=1, le=1440)]
SourceIds = Annotated[tuple[UUID, ...], Field(max_length=20)]
NonEmptySourceIds = Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]
MoneyAmount = Annotated[
    Decimal,
    Field(ge=Decimal("0"), decimal_places=2),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^(0|[1-9]\d*)(\.\d{1,2})?$",
            "examples": ["100.00"],
        }
    ),
]


class PlanningStatus(StrEnum):
    """Observable F-001 planning states."""

    DRAFT = "draft"
    NORMALIZING = "normalizing"
    NEEDS_INPUT = "needs_input"
    COLLECTING = "collecting"
    PLANNING = "planning"
    ENRICHING_ROUTES = "enriching_routes"
    VALIDATING = "validating"
    READY = "ready"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    FAILED = "failed"


ALLOWED_PLANNING_TRANSITIONS: Final[Mapping[PlanningStatus, frozenset[PlanningStatus]]] = (
    MappingProxyType(
        {
            PlanningStatus.DRAFT: frozenset({PlanningStatus.NORMALIZING}),
            PlanningStatus.NORMALIZING: frozenset(
                {
                    PlanningStatus.NEEDS_INPUT,
                    PlanningStatus.COLLECTING,
                    PlanningStatus.FAILED,
                }
            ),
            PlanningStatus.NEEDS_INPUT: frozenset(),
            PlanningStatus.COLLECTING: frozenset(
                {
                    PlanningStatus.PLANNING,
                    PlanningStatus.PARTIAL,
                    PlanningStatus.FAILED,
                }
            ),
            PlanningStatus.PLANNING: frozenset(
                {
                    PlanningStatus.NEEDS_INPUT,
                    PlanningStatus.ENRICHING_ROUTES,
                    PlanningStatus.VALIDATING,
                    PlanningStatus.FAILED,
                }
            ),
            PlanningStatus.ENRICHING_ROUTES: frozenset(
                {
                    PlanningStatus.VALIDATING,
                    PlanningStatus.PARTIAL,
                    PlanningStatus.FAILED,
                }
            ),
            PlanningStatus.VALIDATING: frozenset(
                {
                    PlanningStatus.READY,
                    PlanningStatus.PARTIAL,
                    PlanningStatus.CONFLICT,
                    PlanningStatus.PLANNING,
                    PlanningStatus.FAILED,
                }
            ),
            PlanningStatus.READY: frozenset(),
            PlanningStatus.PARTIAL: frozenset({PlanningStatus.NORMALIZING}),
            PlanningStatus.CONFLICT: frozenset(),
            PlanningStatus.FAILED: frozenset({PlanningStatus.NORMALIZING}),
        }
    )
)


class Pace(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    INTENSIVE = "intensive"


class TransportMode(StrEnum):
    WALKING = "walking"
    PUBLIC_TRANSIT = "public_transit"


class RouteMode(StrEnum):
    WALKING = "walking"
    PUBLIC_TRANSIT = "public_transit"


class ProviderName(StrEnum):
    DEEPSEEK = "deepseek"
    AMAP = "amap"
    QWEATHER = "qweather"
    USER = "user"
    SYSTEM = "system"


class CoordinateSystem(StrEnum):
    PROVIDER_NATIVE = "provider_native"
    WGS84 = "wgs84"
    UNKNOWN = "unknown"


class DataFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN_VALIDITY = "unknown_validity"


class CostConfidence(StrEnum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class CostCategory(StrEnum):
    ACCOMMODATION = "accommodation"
    INTERCITY_TRANSPORT = "intercity_transport"
    LOCAL_TRANSPORT = "local_transport"
    TICKET = "ticket"
    MEAL = "meal"
    OTHER = "other"


class BudgetAssessment(StrEnum):
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"
    INDETERMINATE = "budget_indeterminate"


class ViolationSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class Money(ContractModel):
    """CNY amount encoded as a decimal string in JSON."""

    amount: MoneyAmount
    currency: Literal["CNY"] = "CNY"

    @field_validator("amount", mode="before")
    @classmethod
    def reject_binary_float_and_integer(cls, value: object) -> object:
        if isinstance(value, Decimal | str) and not isinstance(value, bool):
            return value
        raise ValueError("amount must be supplied as a decimal string")

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")


class TravelerPreferences(ContractModel):
    interests: Annotated[tuple[ShortText, ...], Field(max_length=5)] = ()
    free_text: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, max_length=200),
    ] = ""
    hard_constraints: Annotated[tuple[LongText, ...], Field(max_length=10)] = ()


class AccommodationRequirement(ContractModel):
    area_or_poi: ShortText
    one_night_cost: Money | None = None


class DailyTimeWindow(ContractModel):
    day_offset: Literal[0, 1]
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def require_positive_window(self) -> DailyTimeWindow:
        if self.end_time <= self.start_time:
            raise ValueError("day window end must be after start")
        return self


class TripPlanRequest(ContractModel):
    """POST /api/trip-plans request body."""

    client_request_id: UUID
    city: CityText
    start_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    total_budget: Money
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    pace: Pace = Pace.BALANCED
    transport_modes: Annotated[tuple[TransportMode, ...], Field(min_length=1, max_length=2)]
    accommodation: AccommodationRequirement
    day_windows: Annotated[tuple[DailyTimeWindow, ...], Field(min_length=2, max_length=2)]
    intercity_transport_cost: Money | None = None
    meal_budget_per_person_per_day: Money = Field(
        default_factory=lambda: Money(amount=Decimal("100.00"))
    )

    @model_validator(mode="after")
    def require_both_unique_day_windows(self) -> TripPlanRequest:
        if {item.day_offset for item in self.day_windows} != {0, 1}:
            raise ValueError("day windows must contain day offsets 0 and 1 exactly once")
        return self


class Coordinates(ContractModel):
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    coordinate_system: CoordinateSystem


class SourceRecord(ContractModel):
    source_id: UUID
    provider: ProviderName
    source_type: ShortText
    provider_record_id: ShortText | None = None
    fetched_at: datetime
    valid_until: datetime | None = None
    freshness: DataFreshness
    reference_url: AnyHttpUrl | None = None
    attributions: Annotated[tuple[LongText, ...], Field(max_length=10)] = ()
    warnings: Annotated[tuple[LongText, ...], Field(max_length=10)] = ()

    @field_validator("fetched_at", "valid_until")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value


class LocationRef(ContractModel):
    location_id: UUID
    provider: ProviderName
    provider_place_id: ShortText | None = None
    name: ShortText
    category: ShortText
    address: LongText | None = None
    city_adcode: Adcode
    coordinates: Coordinates | None = None
    source_ids: NonEmptySourceIds


class CostItem(ContractModel):
    cost_id: UUID
    category: CostCategory
    confidence: CostConfidence
    amount: Money | None
    description: ShortText
    source_ids: SourceIds = ()

    @model_validator(mode="after")
    def preserve_unknown_amount_semantics(self) -> CostItem:
        if self.confidence is CostConfidence.UNKNOWN and self.amount is not None:
            raise ValueError("unknown costs must not have an amount")
        if self.confidence is not CostConfidence.UNKNOWN and self.amount is None:
            raise ValueError("known costs must have an amount")
        if self.confidence is CostConfidence.VERIFIED and not self.source_ids:
            raise ValueError("verified costs must cite at least one source")
        return self


class RouteLeg(ContractModel):
    route_id: UUID
    origin_location_id: UUID
    destination_location_id: UUID
    mode: RouteMode
    distance_meters: int = Field(strict=True, ge=0, le=MAX_ROUTE_DISTANCE_METERS)
    duration_minutes: PositiveMinutes
    fare: CostItem | None = None
    source_ids: NonEmptySourceIds


class WeatherAlert(ContractModel):
    alert_id: ShortText
    title: ShortText
    severity: ShortText | None = None
    issued_at: datetime | None = None
    description: LongText
    source_ids: NonEmptySourceIds

    @field_validator("issued_at")
    @classmethod
    def require_alert_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value


class WeatherSnapshot(ContractModel):
    forecast_date: date
    location_id: UUID
    condition_day: ShortText
    condition_night: ShortText
    temperature_min_celsius: Decimal
    temperature_max_celsius: Decimal
    alerts: Annotated[tuple[WeatherAlert, ...], Field(max_length=20)] = ()
    source_ids: NonEmptySourceIds


class ItineraryItem(ContractModel):
    item_id: UUID
    location_id: UUID
    title: ShortText
    start_time: time
    end_time: time
    cost_items: Annotated[tuple[CostItem, ...], Field(max_length=20)] = ()
    source_ids: NonEmptySourceIds


class PlanDay(ContractModel):
    local_date: date
    accommodation_location_id: UUID
    activities: Annotated[tuple[ItineraryItem, ...], Field(max_length=3)]
    routes: Annotated[tuple[RouteLeg, ...], Field(max_length=4)]
    weather: WeatherSnapshot | None = None


class ResolvedDestination(ContractModel):
    city_name: ShortText
    adcode: Adcode
    center: Coordinates | None = None
    source_ids: NonEmptySourceIds


class BudgetSummary(ContractModel):
    budget: Money
    known_total: Money
    unknown_count: int = Field(strict=True, ge=0)
    assessment: BudgetAssessment
    cost_items: Annotated[tuple[CostItem, ...], Field(max_length=50)]


class Uncertainty(ContractModel):
    code: ShortText
    message: LongText
    affected_refs: Annotated[tuple[UUID, ...], Field(max_length=20)] = ()
    source_ids: SourceIds = ()


class ConstraintViolation(ContractModel):
    code: ShortText
    severity: ViolationSeverity
    message: LongText
    affected_refs: Annotated[tuple[UUID, ...], Field(max_length=20)] = ()


class TripPlan(ContractModel):
    plan_id: UUID
    city_adcode: Adcode
    start_date: date
    end_date: date
    locations: Annotated[tuple[LocationRef, ...], Field(min_length=1, max_length=20)]
    days: Annotated[tuple[PlanDay, ...], Field(min_length=2, max_length=2)]
    budget_summary: BudgetSummary


class TripRequestSummary(ContractModel):
    city: CityText
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    budget: Money


class TripPlanResponse(ContractModel):
    """Job resource returned by POST, GET, and retry endpoints."""

    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    status: PlanningStatus
    attempt: int = Field(strict=True, ge=1, le=3)
    request_summary: TripRequestSummary
    resolved_destination: ResolvedDestination | None = None
    plan: TripPlan | None = None
    violations: Annotated[tuple[ConstraintViolation, ...], Field(max_length=50)] = ()
    warnings: Annotated[tuple[LongText, ...], Field(max_length=50)] = ()
    uncertainties: Annotated[tuple[Uncertainty, ...], Field(max_length=50)] = ()
    sources: Annotated[tuple[SourceRecord, ...], Field(max_length=100)] = ()
    errors: Annotated[tuple[ApiError, ...], Field(max_length=20)] = ()
    retryable: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_response_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value
