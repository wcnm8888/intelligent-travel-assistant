"""Stable F-001 trip-planning request, result, and state contracts.

These models describe data exchanged across project boundaries. They do not
implement planning, provider access, persistence, or deterministic validators.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    Discriminator,
    Field,
    StringConstraints,
    Tag,
    WithJsonSchema,
    field_serializer,
    field_validator,
    model_validator,
)

from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.contracts.errors import ApiError
from intelligent_travel_assistant.domain import (
    MAX_ROUTE_DISTANCE_METERS,
    normalize_service_number,
)

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


class IntercityMode(StrEnum):
    RAIL = "rail"
    AIR = "air"
    COACH = "coach"


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


class BookedRailTravelerPreferencesV4(ContractModel):
    """V4 allowlist: booked-rail requests may carry interests only."""

    interests: Annotated[tuple[ShortText, ...], Field(max_length=5)] = ()


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


class MultiDayTimeWindow(DailyTimeWindow):
    """Version 2 local-day window with a strict offset from zero through six."""

    day_offset: Annotated[int, Field(strict=True, ge=0, le=6)]  # type: ignore[assignment]


class TripPlanRequestV2(TripPlanRequest):
    """Strictly tagged request for one continuous 2-7 day single-city trip."""

    request_version: Literal["2"]
    end_date: date
    day_windows: Annotated[tuple[MultiDayTimeWindow, ...], Field(min_length=2, max_length=7)]

    @model_validator(mode="after")
    def require_both_unique_day_windows(self) -> TripPlanRequestV2:
        if self.end_date <= self.start_date:
            raise ValueError("trip end date must be after start date")
        day_count = self.day_count
        if not 2 <= day_count <= 7:
            raise ValueError("trip must contain between two and seven days")
        if len(self.day_windows) != day_count or {
            item.day_offset for item in self.day_windows
        } != set(range(day_count)):
            raise ValueError("day windows must exactly cover the trip offsets")
        return self

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


class PlanDayV2(PlanDay):
    """Version 2 day with one or two activities and at most three route legs."""

    activities: Annotated[tuple[ItineraryItem, ...], Field(min_length=1, max_length=2)]
    routes: Annotated[tuple[RouteLeg, ...], Field(max_length=3)]


class TripPlanV2(TripPlan):
    """Strictly tagged 2-7 day plan without changing the legacy plan shape."""

    plan_format_version: Literal["2"]
    days: Annotated[tuple[PlanDayV2, ...], Field(min_length=2, max_length=7)]

    @model_validator(mode="after")
    def require_exact_trip_dates_and_accommodation(self) -> TripPlanV2:
        if self.end_date <= self.start_date:
            raise ValueError("trip end date must be after start date")
        day_count = (self.end_date - self.start_date).days + 1
        if not 2 <= day_count <= 7 or len(self.days) != day_count:
            raise ValueError("plan days must match a two-to-seven-day trip")
        expected_dates = tuple(
            self.start_date + timedelta(days=offset) for offset in range(day_count)
        )
        if tuple(day.local_date for day in self.days) != expected_dates:
            raise ValueError("plan days must exactly cover the trip dates")
        accommodation_ids = {day.accommodation_location_id for day in self.days}
        if len(accommodation_ids) != 1:
            raise ValueError("all plan days must use one accommodation anchor")
        if any(
            day.weather is not None and day.weather.forecast_date != day.local_date
            for day in self.days
        ):
            raise ValueError("weather dates must match their plan days")
        return self


class TripRequestSummaryV2(TripRequestSummary):
    request_version: Literal["2"]


class TripPlanResponseV2(TripPlanResponse):
    """Version 2 job resource selected from the persisted request version."""

    response_version: Literal["2"]
    request_summary: TripRequestSummaryV2
    plan: TripPlanV2 | None = None


CityIndex = Annotated[int, Field(strict=True, ge=0, le=2)]
StayNights = Annotated[int, Field(strict=True, ge=1, le=6)]
_SHANGHAI_OFFSET: Final = timedelta(hours=8)
_INTERCITY_BUFFERS: Final[Mapping[IntercityMode, tuple[int, int]]] = MappingProxyType(
    {
        IntercityMode.RAIL: (60, 30),
        IntercityMode.AIR: (120, 60),
        IntercityMode.COACH: (45, 30),
    }
)
_USER_INTERCITY_SOURCE_TYPE: Final = "user_provided_intercity_segment"
_USER_INTERCITY_ATTRIBUTION: Final = "用户提供"
_USER_INTERCITY_WARNING: Final = "未核验班次、票价、余票或库存"


class CityStayV3(ContractModel):
    city: CityText
    nights: StayNights
    accommodation: AccommodationRequirement


class UserProvidedIntercitySegmentV3(ContractModel):
    from_city_index: CityIndex
    to_city_index: CityIndex
    mode: IntercityMode
    departure_station: ShortText
    arrival_station: ShortText
    departure_at: datetime
    arrival_at: datetime
    fare: Money | None = None

    @model_validator(mode="after")
    def require_adjacent_same_day_shanghai_segment(self) -> UserProvidedIntercitySegmentV3:
        if self.to_city_index != self.from_city_index + 1:
            raise ValueError("intercity segment must connect adjacent cities")
        _require_shanghai_datetime(self.departure_at)
        _require_shanghai_datetime(self.arrival_at)
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise ValueError("intercity segment must arrive later on the same local day")
        return self


class TripPlanRequestV3(ContractModel):
    """Strict standalone request for an ordered two-to-three-city trip."""

    request_version: Literal["3"]
    client_request_id: UUID
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    total_budget: Money
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    pace: Pace = Pace.BALANCED
    transport_modes: Annotated[tuple[TransportMode, ...], Field(min_length=1, max_length=2)]
    city_stays: Annotated[tuple[CityStayV3, ...], Field(min_length=2, max_length=3)]
    intercity_segments: Annotated[
        tuple[UserProvidedIntercitySegmentV3, ...], Field(min_length=1, max_length=2)
    ]
    day_windows: Annotated[tuple[MultiDayTimeWindow, ...], Field(min_length=3, max_length=7)]
    meal_budget_per_person_per_day: Money = Field(
        default_factory=lambda: Money(amount=Decimal("100.00"))
    )

    @model_validator(mode="after")
    def require_multicity_continuity(self) -> TripPlanRequestV3:
        if self.end_date <= self.start_date or not 3 <= self.day_count <= 7:
            raise ValueError("multi-city trip must contain between three and seven days")
        if len(self.day_windows) != self.day_count or {
            item.day_offset for item in self.day_windows
        } != set(range(self.day_count)):
            raise ValueError("day windows must exactly cover the trip offsets")
        normalized_cities = tuple(item.city.casefold() for item in self.city_stays)
        if len(set(normalized_cities)) != len(normalized_cities):
            raise ValueError("multi-city stays must contain unique ordered cities")
        if sum(item.nights for item in self.city_stays) != self.day_count - 1:
            raise ValueError("city stay nights must equal trip days minus one")
        if len(self.intercity_segments) != len(self.city_stays) - 1:
            raise ValueError("intercity segments must connect every adjacent city")
        for index, (segment, transfer_date) in enumerate(
            zip(self.intercity_segments, self.transfer_dates, strict=True)
        ):
            if (
                segment.from_city_index != index
                or segment.to_city_index != index + 1
                or segment.departure_at.date() != transfer_date
                or segment.arrival_at.date() != transfer_date
            ):
                raise ValueError("intercity segment order or transfer date is invalid")
        return self

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


class PlanIntercitySegmentV3(ContractModel):
    segment_id: UUID
    from_city_index: CityIndex
    to_city_index: CityIndex
    mode: IntercityMode
    departure_station_location_id: UUID
    arrival_station_location_id: UUID
    departure_at: datetime
    arrival_at: datetime
    fare: CostItem
    source_ids: NonEmptySourceIds

    @model_validator(mode="after")
    def require_safe_user_segment(self) -> PlanIntercitySegmentV3:
        if self.to_city_index != self.from_city_index + 1:
            raise ValueError("intercity segment must connect adjacent cities")
        if self.departure_station_location_id == self.arrival_station_location_id:
            raise ValueError("intercity stations must differ")
        _require_shanghai_datetime(self.departure_at)
        _require_shanghai_datetime(self.arrival_at)
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise ValueError("intercity segment must arrive later on the same local day")
        if self.fare.category is not CostCategory.INTERCITY_TRANSPORT:
            raise ValueError("intercity fare must use the intercity category")
        if self.fare.confidence not in {
            CostConfidence.USER_PROVIDED,
            CostConfidence.UNKNOWN,
        }:
            raise ValueError("intercity fare must be user-provided or unknown")
        if not set(self.fare.source_ids).issubset(self.source_ids):
            raise ValueError("intercity fare sources must belong to the segment")
        return self


class PlanDayV3(ContractModel):
    local_date: date
    departure_city_index: CityIndex
    arrival_city_index: CityIndex
    overnight_city_index: CityIndex
    intercity_segment_id: UUID | None = None
    accommodation_location_id: UUID
    activities: Annotated[tuple[ItineraryItem, ...], Field(max_length=2)]
    routes: Annotated[tuple[RouteLeg, ...], Field(max_length=3)]
    weather: WeatherSnapshot | None = None


class TripPlanV3(ContractModel):
    plan_id: UUID
    plan_format_version: Literal["3"]
    city_adcodes: Annotated[tuple[Adcode, ...], Field(min_length=2, max_length=3)]
    start_date: date
    end_date: date
    locations: Annotated[tuple[LocationRef, ...], Field(min_length=1, max_length=32)]
    intercity_segments: Annotated[
        tuple[PlanIntercitySegmentV3, ...], Field(min_length=1, max_length=2)
    ]
    days: Annotated[tuple[PlanDayV3, ...], Field(min_length=3, max_length=7)]
    budget_summary: BudgetSummary

    @model_validator(mode="after")
    def require_multicity_plan_integrity(self) -> TripPlanV3:
        if len(set(self.city_adcodes)) != len(self.city_adcodes):
            raise ValueError("plan cities must be unique and ordered")
        day_count = (self.end_date - self.start_date).days + 1
        if not 3 <= day_count <= 7 or len(self.days) != day_count:
            raise ValueError("plan days must match a three-to-seven-day trip")
        expected_dates = tuple(
            self.start_date + timedelta(days=offset) for offset in range(day_count)
        )
        if tuple(day.local_date for day in self.days) != expected_dates:
            raise ValueError("plan days must exactly cover the trip dates")
        if len(self.intercity_segments) != len(self.city_adcodes) - 1:
            raise ValueError("plan must connect every adjacent city")

        locations = {item.location_id: item for item in self.locations}
        if len(locations) != len(self.locations):
            raise ValueError("plan location ids must be unique")
        if any(item.city_adcode not in self.city_adcodes for item in self.locations):
            raise ValueError("plan location belongs to an unknown city")

        segments = {item.segment_id: item for item in self.intercity_segments}
        if len(segments) != len(self.intercity_segments):
            raise ValueError("intercity segment ids must be unique")
        for index, segment in enumerate(self.intercity_segments):
            if segment.from_city_index != index or segment.to_city_index != index + 1:
                raise ValueError("intercity segments must follow city order")
            departure_station = locations.get(segment.departure_station_location_id)
            arrival_station = locations.get(segment.arrival_station_location_id)
            if (
                departure_station is None
                or arrival_station is None
                or departure_station.city_adcode != self.city_adcodes[index]
                or arrival_station.city_adcode != self.city_adcodes[index + 1]
            ):
                raise ValueError("intercity station references do not match city order")

        referenced_segment_ids: list[UUID] = []
        current_city_index = 0
        for day in self.days:
            if day.departure_city_index != current_city_index:
                raise ValueError("each day must depart from the previous overnight city")
            self._require_day_integrity(day, locations, segments)
            current_city_index = day.overnight_city_index
            if day.intercity_segment_id is not None:
                referenced_segment_ids.append(day.intercity_segment_id)
        if tuple(referenced_segment_ids) != tuple(
            segment.segment_id for segment in self.intercity_segments
        ):
            raise ValueError("each intercity segment must be referenced exactly once in order")
        if current_city_index != len(self.city_adcodes) - 1:
            raise ValueError("plan must finish in the final ordered city")
        return self

    def _require_day_integrity(
        self,
        day: PlanDayV3,
        locations: Mapping[UUID, LocationRef],
        segments: Mapping[UUID, PlanIntercitySegmentV3],
    ) -> None:
        indices = (
            day.departure_city_index,
            day.arrival_city_index,
            day.overnight_city_index,
        )
        if any(index >= len(self.city_adcodes) for index in indices):
            raise ValueError("day city index is outside the trip")
        accommodation = locations.get(day.accommodation_location_id)
        if (
            accommodation is None
            or accommodation.city_adcode != self.city_adcodes[day.overnight_city_index]
        ):
            raise ValueError("day accommodation does not match the overnight city")

        segment = (
            None if day.intercity_segment_id is None else segments.get(day.intercity_segment_id)
        )
        if segment is None:
            if day.intercity_segment_id is not None or not (
                day.departure_city_index == day.arrival_city_index == day.overnight_city_index
            ):
                raise ValueError("non-transfer day city continuity is invalid")
            if not 1 <= len(day.activities) <= 2:
                raise ValueError("non-transfer day must contain one or two activities")
        else:
            if (
                day.local_date != segment.departure_at.date()
                or day.departure_city_index != segment.from_city_index
                or day.arrival_city_index != segment.to_city_index
                or day.overnight_city_index != segment.to_city_index
                or len(day.activities) > 1
            ):
                raise ValueError("transfer day continuity or activity count is invalid")

        allowed_city_indices = {day.departure_city_index, day.arrival_city_index}
        for activity in day.activities:
            location = locations.get(activity.location_id)
            if location is None:
                raise ValueError("activity location is missing")
            city_index = self.city_adcodes.index(location.city_adcode)
            if city_index not in allowed_city_indices:
                raise ValueError("activity belongs to a disallowed city")
            if segment is not None:
                _require_activity_outside_intercity_buffer(activity, city_index, segment)
        for route in day.routes:
            origin = locations.get(route.origin_location_id)
            destination = locations.get(route.destination_location_id)
            if (
                origin is None
                or destination is None
                or origin.city_adcode != destination.city_adcode
                or self.city_adcodes.index(origin.city_adcode) not in allowed_city_indices
            ):
                raise ValueError("local route must remain inside an allowed city")
        if day.weather is not None:
            weather_location = locations.get(day.weather.location_id)
            if (
                weather_location is None
                or weather_location.city_adcode != self.city_adcodes[day.overnight_city_index]
                or day.weather.forecast_date != day.local_date
            ):
                raise ValueError("weather must match the overnight city and local date")


class CityStaySummaryV3(ContractModel):
    city: CityText
    nights: StayNights


class TripRequestSummaryV3(ContractModel):
    request_version: Literal["3"]
    city_stays: Annotated[tuple[CityStaySummaryV3, ...], Field(min_length=2, max_length=3)]
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    budget: Money

    @model_validator(mode="after")
    def require_summary_dates_and_nights(self) -> TripRequestSummaryV3:
        day_count = (self.end_date - self.start_date).days + 1
        if (
            not 3 <= day_count <= 7
            or sum(item.nights for item in self.city_stays) != day_count - 1
            or len({item.city.casefold() for item in self.city_stays}) != len(self.city_stays)
        ):
            raise ValueError("multi-city request summary is inconsistent")
        return self

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


class TripPlanResponseV3(ContractModel):
    """Standalone V3 job resource; API union integration belongs to F-004B1 Step 3."""

    response_version: Literal["3"]
    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    status: PlanningStatus
    attempt: int = Field(strict=True, ge=1, le=3)
    request_summary: TripRequestSummaryV3
    resolved_destinations: Annotated[tuple[ResolvedDestination, ...], Field(max_length=3)] = ()
    plan: TripPlanV3 | None = None
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

    @model_validator(mode="after")
    def require_v3_terminal_and_source_integrity(self) -> TripPlanResponseV3:
        if self.updated_at < self.created_at:
            raise ValueError("response timestamps are out of order")
        if self.plan is not None:
            if len(self.resolved_destinations) != len(self.request_summary.city_stays):
                raise ValueError("resolved destinations must cover every city")
            if tuple(item.adcode for item in self.resolved_destinations) != self.plan.city_adcodes:
                raise ValueError("resolved destinations and plan cities must match")
            if (
                self.plan.start_date != self.request_summary.start_date
                or self.plan.end_date != self.request_summary.end_date
            ):
                raise ValueError("request summary and plan dates must match")
            if (
                tuple(segment.departure_at.date() for segment in self.plan.intercity_segments)
                != self.request_summary.transfer_dates
            ):
                raise ValueError("plan transfer dates must match request summary nights")
            self._require_user_intercity_sources()

        if self.status in {PlanningStatus.READY, PlanningStatus.PARTIAL} and self.plan is None:
            raise ValueError("ready and partial responses require a plan")
        if self.status is PlanningStatus.READY and (
            self.plan is None
            or self.plan.budget_summary.unknown_count > 0
            or self.violations
            or self.errors
            or self.retryable
        ):
            raise ValueError("ready response has an invalid terminal shape")
        if self.status is PlanningStatus.PARTIAL and not (
            self.violations
            or self.errors
            or self.warnings
            or self.uncertainties
            or (self.plan is not None and self.plan.budget_summary.unknown_count > 0)
        ):
            raise ValueError("partial response requires explicit evidence")
        if self.status is PlanningStatus.CONFLICT and not any(
            item.severity is ViolationSeverity.ERROR for item in self.violations
        ):
            raise ValueError("conflict response requires an error violation")
        if self.status is PlanningStatus.CONFLICT and self.retryable:
            raise ValueError("conflict response cannot be retryable")
        if self.status is PlanningStatus.NEEDS_INPUT and (
            self.plan is not None or self.retryable or not self.errors
        ):
            raise ValueError("needs-input response requires errors and no plan")
        if self.status is PlanningStatus.FAILED and (self.plan is not None or not self.errors):
            raise ValueError("failed response must have errors and no plan")
        if self.retryable and (
            self.status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}
            or not any(error.retryable for error in self.errors)
        ):
            raise ValueError("retryable response requires a retryable terminal error")
        return self

    def _require_user_intercity_sources(self) -> None:
        assert self.plan is not None
        sources = {item.source_id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("source ids must be unique")
        for segment in self.plan.intercity_segments:
            for source_id in segment.source_ids:
                source = sources.get(source_id)
                if (
                    source is None
                    or source.provider is not ProviderName.USER
                    or source.source_type != _USER_INTERCITY_SOURCE_TYPE
                    or source.provider_record_id is not None
                    or source.valid_until is not None
                    or source.freshness is not DataFreshness.UNKNOWN_VALIDITY
                    or source.reference_url is not None
                    or source.attributions != (_USER_INTERCITY_ATTRIBUTION,)
                    or source.warnings != (_USER_INTERCITY_WARNING,)
                ):
                    raise ValueError("intercity source must remain user-provided and unverified")


class BookedRailIntercitySegmentV4(ContractModel):
    """Strict user-provided rail facts; the service number is not provider-verified."""

    from_city_index: CityIndex
    to_city_index: CityIndex
    mode: Literal["rail"]
    service_number: str
    departure_station: ShortText
    arrival_station: ShortText
    departure_at: datetime
    arrival_at: datetime
    fare: Money | None = None

    @field_validator("service_number", mode="before")
    @classmethod
    def normalize_strict_service_number(cls, value: object) -> str:
        return normalize_service_number(value)

    @field_validator("departure_station", "arrival_station")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("station text must not contain control characters")
        return value

    @model_validator(mode="after")
    def require_booked_rail_segment(self) -> BookedRailIntercitySegmentV4:
        if self.to_city_index != self.from_city_index + 1:
            raise ValueError("intercity segment must connect adjacent cities")
        _require_shanghai_datetime(self.departure_at)
        _require_shanghai_datetime(self.arrival_at)
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise ValueError("intercity segment must arrive later on the same local day")
        if self.fare is not None and self.fare.amount <= 0:
            raise ValueError("known user-provided fare must be positive")
        return self

    @property
    def duration(self) -> timedelta:
        return self.arrival_at - self.departure_at


class TripPlanRequestV4(ContractModel):
    """Strict standalone V4 request for user-provided booked rail segments."""

    request_version: Literal["4"]
    client_request_id: UUID
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    total_budget: Money
    preferences: BookedRailTravelerPreferencesV4 = Field(
        default_factory=BookedRailTravelerPreferencesV4
    )
    pace: Pace = Pace.BALANCED
    transport_modes: Annotated[tuple[TransportMode, ...], Field(min_length=1, max_length=2)]
    city_stays: Annotated[tuple[CityStayV3, ...], Field(min_length=2, max_length=3)]
    intercity_segments: Annotated[
        tuple[BookedRailIntercitySegmentV4, ...], Field(min_length=1, max_length=2)
    ]
    day_windows: Annotated[tuple[MultiDayTimeWindow, ...], Field(min_length=3, max_length=7)]
    meal_budget_per_person_per_day: Money = Field(
        default_factory=lambda: Money(amount=Decimal("100.00"))
    )

    @model_validator(mode="after")
    def require_multicity_continuity(self) -> TripPlanRequestV4:
        if self.end_date <= self.start_date or not 3 <= self.day_count <= 7:
            raise ValueError("multi-city trip must contain between three and seven days")
        if len(self.day_windows) != self.day_count or {
            item.day_offset for item in self.day_windows
        } != set(range(self.day_count)):
            raise ValueError("day windows must exactly cover the trip offsets")
        normalized_cities = tuple(item.city.casefold() for item in self.city_stays)
        if len(set(normalized_cities)) != len(normalized_cities):
            raise ValueError("multi-city stays must contain unique ordered cities")
        if sum(item.nights for item in self.city_stays) != self.day_count - 1:
            raise ValueError("city stay nights must equal trip days minus one")
        if len(self.intercity_segments) != len(self.city_stays) - 1:
            raise ValueError("intercity segments must connect every adjacent city")
        for index, (segment, transfer_date) in enumerate(
            zip(self.intercity_segments, self.transfer_dates, strict=True)
        ):
            if (
                segment.from_city_index != index
                or segment.to_city_index != index + 1
                or segment.departure_at.date() != transfer_date
                or segment.arrival_at.date() != transfer_date
            ):
                raise ValueError("intercity segment order or transfer date is invalid")
        return self

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


class PlanBookedRailSegmentV4(ContractModel):
    segment_id: UUID
    from_city_index: CityIndex
    to_city_index: CityIndex
    mode: Literal["rail"]
    service_number: str
    departure_station_location_id: UUID
    arrival_station_location_id: UUID
    departure_at: datetime
    arrival_at: datetime
    fare: CostItem
    source_ids: NonEmptySourceIds

    @field_validator("service_number", mode="before")
    @classmethod
    def normalize_strict_service_number(cls, value: object) -> str:
        return normalize_service_number(value)

    @model_validator(mode="after")
    def require_safe_user_segment(self) -> PlanBookedRailSegmentV4:
        if self.to_city_index != self.from_city_index + 1:
            raise ValueError("intercity segment must connect adjacent cities")
        if self.departure_station_location_id == self.arrival_station_location_id:
            raise ValueError("intercity stations must differ")
        _require_shanghai_datetime(self.departure_at)
        _require_shanghai_datetime(self.arrival_at)
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise ValueError("intercity segment must arrive later on the same local day")
        if self.fare.category is not CostCategory.INTERCITY_TRANSPORT:
            raise ValueError("intercity fare must use the intercity category")
        if self.fare.confidence not in {
            CostConfidence.USER_PROVIDED,
            CostConfidence.UNKNOWN,
        }:
            raise ValueError("intercity fare must be user-provided or unknown")
        if self.fare.confidence is CostConfidence.USER_PROVIDED and (
            self.fare.amount is None or self.fare.amount.amount <= 0
        ):
            raise ValueError("known user-provided fare must be positive")
        if not set(self.fare.source_ids).issubset(self.source_ids):
            raise ValueError("intercity fare sources must belong to the segment")
        return self

    @property
    def duration(self) -> timedelta:
        return self.arrival_at - self.departure_at


class TripPlanV4(ContractModel):
    plan_id: UUID
    plan_format_version: Literal["4"]
    city_adcodes: Annotated[tuple[Adcode, ...], Field(min_length=2, max_length=3)]
    start_date: date
    end_date: date
    locations: Annotated[tuple[LocationRef, ...], Field(min_length=1, max_length=32)]
    intercity_segments: Annotated[
        tuple[PlanBookedRailSegmentV4, ...], Field(min_length=1, max_length=2)
    ]
    days: Annotated[tuple[PlanDayV3, ...], Field(min_length=3, max_length=7)]
    budget_summary: BudgetSummary

    @model_validator(mode="after")
    def require_multicity_plan_integrity(self) -> TripPlanV4:
        if len(set(self.city_adcodes)) != len(self.city_adcodes):
            raise ValueError("plan cities must be unique and ordered")
        day_count = (self.end_date - self.start_date).days + 1
        if not 3 <= day_count <= 7 or len(self.days) != day_count:
            raise ValueError("plan days must match a three-to-seven-day trip")
        expected_dates = tuple(
            self.start_date + timedelta(days=offset) for offset in range(day_count)
        )
        if tuple(day.local_date for day in self.days) != expected_dates:
            raise ValueError("plan days must exactly cover the trip dates")
        if len(self.intercity_segments) != len(self.city_adcodes) - 1:
            raise ValueError("plan must connect every adjacent city")

        locations = {item.location_id: item for item in self.locations}
        if len(locations) != len(self.locations):
            raise ValueError("plan location ids must be unique")
        if any(item.city_adcode not in self.city_adcodes for item in self.locations):
            raise ValueError("plan location belongs to an unknown city")

        segments = {item.segment_id: item for item in self.intercity_segments}
        if len(segments) != len(self.intercity_segments):
            raise ValueError("intercity segment ids must be unique")
        for index, segment in enumerate(self.intercity_segments):
            if segment.from_city_index != index or segment.to_city_index != index + 1:
                raise ValueError("intercity segments must follow city order")
            departure_station = locations.get(segment.departure_station_location_id)
            arrival_station = locations.get(segment.arrival_station_location_id)
            if (
                departure_station is None
                or arrival_station is None
                or departure_station.city_adcode != self.city_adcodes[index]
                or arrival_station.city_adcode != self.city_adcodes[index + 1]
            ):
                raise ValueError("intercity station references do not match city order")

        referenced_segment_ids: list[UUID] = []
        current_city_index = 0
        for day in self.days:
            if day.departure_city_index != current_city_index:
                raise ValueError("each day must depart from the previous overnight city")
            self._require_day_integrity(day, locations, segments)
            current_city_index = day.overnight_city_index
            if day.intercity_segment_id is not None:
                referenced_segment_ids.append(day.intercity_segment_id)
        if tuple(referenced_segment_ids) != tuple(
            segment.segment_id for segment in self.intercity_segments
        ):
            raise ValueError("each intercity segment must be referenced exactly once in order")
        if current_city_index != len(self.city_adcodes) - 1:
            raise ValueError("plan must finish in the final ordered city")
        return self

    def _require_day_integrity(
        self,
        day: PlanDayV3,
        locations: Mapping[UUID, LocationRef],
        segments: Mapping[UUID, PlanBookedRailSegmentV4],
    ) -> None:
        indices = (
            day.departure_city_index,
            day.arrival_city_index,
            day.overnight_city_index,
        )
        if any(index >= len(self.city_adcodes) for index in indices):
            raise ValueError("day city index is outside the trip")
        accommodation = locations.get(day.accommodation_location_id)
        if (
            accommodation is None
            or accommodation.city_adcode != self.city_adcodes[day.overnight_city_index]
        ):
            raise ValueError("day accommodation does not match the overnight city")

        segment = (
            None if day.intercity_segment_id is None else segments.get(day.intercity_segment_id)
        )
        if segment is None:
            if day.intercity_segment_id is not None or not (
                day.departure_city_index == day.arrival_city_index == day.overnight_city_index
            ):
                raise ValueError("non-transfer day city continuity is invalid")
            if not 1 <= len(day.activities) <= 2:
                raise ValueError("non-transfer day must contain one or two activities")
        elif (
            day.local_date != segment.departure_at.date()
            or day.departure_city_index != segment.from_city_index
            or day.arrival_city_index != segment.to_city_index
            or day.overnight_city_index != segment.to_city_index
            or len(day.activities) > 1
        ):
            raise ValueError("transfer day continuity or activity count is invalid")

        allowed_city_indices = {day.departure_city_index, day.arrival_city_index}
        for activity in day.activities:
            location = locations.get(activity.location_id)
            if location is None:
                raise ValueError("activity location is missing")
            city_index = self.city_adcodes.index(location.city_adcode)
            if city_index not in allowed_city_indices:
                raise ValueError("activity belongs to a disallowed city")
            if segment is not None:
                _require_activity_outside_intercity_buffer(activity, city_index, segment)
        for route in day.routes:
            origin = locations.get(route.origin_location_id)
            destination = locations.get(route.destination_location_id)
            if (
                origin is None
                or destination is None
                or origin.city_adcode != destination.city_adcode
                or self.city_adcodes.index(origin.city_adcode) not in allowed_city_indices
            ):
                raise ValueError("local route must remain inside an allowed city")
        if day.weather is not None:
            weather_location = locations.get(day.weather.location_id)
            if (
                weather_location is None
                or weather_location.city_adcode != self.city_adcodes[day.overnight_city_index]
                or day.weather.forecast_date != day.local_date
            ):
                raise ValueError("weather must match the overnight city and local date")


class TripRequestSummaryV4(ContractModel):
    request_version: Literal["4"]
    city_stays: Annotated[tuple[CityStaySummaryV3, ...], Field(min_length=2, max_length=3)]
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    budget: Money

    @model_validator(mode="after")
    def require_summary_dates_and_nights(self) -> TripRequestSummaryV4:
        day_count = (self.end_date - self.start_date).days + 1
        if (
            not 3 <= day_count <= 7
            or sum(item.nights for item in self.city_stays) != day_count - 1
            or len({item.city.casefold() for item in self.city_stays}) != len(self.city_stays)
        ):
            raise ValueError("multi-city request summary is inconsistent")
        return self

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


class TripPlanResponseV4(ContractModel):
    """Standalone V4 job resource for unverified user-provided booked rail facts."""

    response_version: Literal["4"]
    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    status: PlanningStatus
    attempt: int = Field(strict=True, ge=1, le=3)
    request_summary: TripRequestSummaryV4
    resolved_destinations: Annotated[tuple[ResolvedDestination, ...], Field(max_length=3)] = ()
    plan: TripPlanV4 | None = None
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

    @model_validator(mode="after")
    def require_v4_terminal_and_source_integrity(self) -> TripPlanResponseV4:
        if self.updated_at < self.created_at:
            raise ValueError("response timestamps are out of order")
        if self.plan is not None:
            if len(self.resolved_destinations) != len(self.request_summary.city_stays):
                raise ValueError("resolved destinations must cover every city")
            if tuple(item.adcode for item in self.resolved_destinations) != self.plan.city_adcodes:
                raise ValueError("resolved destinations and plan cities must match")
            if (
                self.plan.start_date != self.request_summary.start_date
                or self.plan.end_date != self.request_summary.end_date
            ):
                raise ValueError("request summary and plan dates must match")
            if (
                tuple(segment.departure_at.date() for segment in self.plan.intercity_segments)
                != self.request_summary.transfer_dates
            ):
                raise ValueError("plan transfer dates must match request summary nights")
            self._require_user_intercity_sources()

        if self.status in {PlanningStatus.READY, PlanningStatus.PARTIAL} and self.plan is None:
            raise ValueError("ready and partial responses require a plan")
        if self.status is PlanningStatus.READY and (
            self.plan is None
            or self.plan.budget_summary.unknown_count > 0
            or self.violations
            or self.errors
            or self.retryable
        ):
            raise ValueError("ready response has an invalid terminal shape")
        if self.status is PlanningStatus.PARTIAL and not (
            self.violations
            or self.errors
            or self.warnings
            or self.uncertainties
            or (self.plan is not None and self.plan.budget_summary.unknown_count > 0)
        ):
            raise ValueError("partial response requires explicit evidence")
        if self.status is PlanningStatus.CONFLICT and not any(
            item.severity is ViolationSeverity.ERROR for item in self.violations
        ):
            raise ValueError("conflict response requires an error violation")
        if self.status is PlanningStatus.CONFLICT and self.retryable:
            raise ValueError("conflict response cannot be retryable")
        if self.status is PlanningStatus.NEEDS_INPUT and (
            self.plan is not None or self.retryable or not self.errors
        ):
            raise ValueError("needs-input response requires errors and no plan")
        if self.status is PlanningStatus.FAILED and (self.plan is not None or not self.errors):
            raise ValueError("failed response must have errors and no plan")
        if self.retryable and (
            self.status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}
            or not any(error.retryable for error in self.errors)
        ):
            raise ValueError("retryable response requires a retryable terminal error")
        return self

    def _require_user_intercity_sources(self) -> None:
        assert self.plan is not None
        sources = {item.source_id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("source ids must be unique")
        for segment in self.plan.intercity_segments:
            for source_id in segment.source_ids:
                source = sources.get(source_id)
                if (
                    source is None
                    or source.provider is not ProviderName.USER
                    or source.source_type != _USER_INTERCITY_SOURCE_TYPE
                    or source.provider_record_id is not None
                    or source.valid_until is not None
                    or source.freshness is not DataFreshness.UNKNOWN_VALIDITY
                    or source.reference_url is not None
                    or source.attributions != (_USER_INTERCITY_ATTRIBUTION,)
                    or source.warnings != (_USER_INTERCITY_WARNING,)
                ):
                    raise ValueError("intercity source must remain user-provided and unverified")


def _require_shanghai_datetime(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != _SHANGHAI_OFFSET:
        raise ValueError("intercity timestamps must use UTC+08:00")


def _require_activity_outside_intercity_buffer(
    activity: ItineraryItem,
    city_index: int,
    segment: PlanIntercitySegmentV3 | PlanBookedRailSegmentV4,
) -> None:
    before_minutes, after_minutes = _INTERCITY_BUFFERS[IntercityMode(segment.mode)]
    if city_index == segment.from_city_index:
        departure_cutoff = (segment.departure_at - timedelta(minutes=before_minutes)).time()
        if activity.end_time > departure_cutoff:
            raise ValueError("departure activity overlaps the intercity buffer")
    elif city_index == segment.to_city_index:
        arrival_cutoff = (segment.arrival_at + timedelta(minutes=after_minutes)).time()
        if activity.start_time < arrival_cutoff:
            raise ValueError("arrival activity overlaps the intercity buffer")
    else:
        raise ValueError("transfer activity belongs to an unrelated city")


def _request_version_discriminator(value: object) -> str | None:
    if isinstance(value, TripPlanRequestV3):
        return "v3"
    if isinstance(value, TripPlanRequestV2):
        return "v2"
    if isinstance(value, TripPlanRequest):
        return "legacy"
    if isinstance(value, Mapping):
        if "request_version" not in value:
            return "legacy"
        if value.get("request_version") == "2":
            return "v2"
        if value.get("request_version") == "3":
            return "v3"
    return None


def _plan_version_discriminator(value: object) -> str | None:
    if isinstance(value, TripPlanV3):
        return "v3"
    if isinstance(value, TripPlanV2):
        return "v2"
    if isinstance(value, TripPlan):
        return "legacy"
    if isinstance(value, Mapping):
        if "plan_format_version" not in value:
            return "legacy"
        if value.get("plan_format_version") == "2":
            return "v2"
        if value.get("plan_format_version") == "3":
            return "v3"
    return None


def _response_version_discriminator(value: object) -> str | None:
    if isinstance(value, TripPlanResponseV3):
        return "v3"
    if isinstance(value, TripPlanResponseV2):
        return "v2"
    if isinstance(value, TripPlanResponse):
        return "legacy"
    if isinstance(value, Mapping):
        if "response_version" not in value:
            return "legacy"
        if value.get("response_version") == "2":
            return "v2"
        if value.get("response_version") == "3":
            return "v3"
    return None


PlanningRequest = Annotated[
    Annotated[TripPlanRequest, Tag("legacy")]
    | Annotated[TripPlanRequestV2, Tag("v2")]
    | Annotated[TripPlanRequestV3, Tag("v3")],
    Discriminator(_request_version_discriminator),
]
PlanningPlan = Annotated[
    Annotated[TripPlan, Tag("legacy")]
    | Annotated[TripPlanV2, Tag("v2")]
    | Annotated[TripPlanV3, Tag("v3")],
    Discriminator(_plan_version_discriminator),
]
PlanningResponse = Annotated[
    Annotated[TripPlanResponse, Tag("legacy")]
    | Annotated[TripPlanResponseV2, Tag("v2")]
    | Annotated[TripPlanResponseV3, Tag("v3")],
    Discriminator(_response_version_discriminator),
]
