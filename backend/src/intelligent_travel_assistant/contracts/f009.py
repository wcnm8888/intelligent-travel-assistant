"""Strict public contracts for F-009 preplanning and V5 map results."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.contracts.errors import ApiError
from intelligent_travel_assistant.contracts.trip_planning import (
    Money,
    MultiDayTimeWindow,
    Pace,
    PlanningStatus,
    TransportMode,
    TravelerPreferences,
)

F009Text = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200),
]
F009LongText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=500),
]
Adcode = Annotated[str, StringConstraints(strict=True, pattern=r"^\d{6}$")]
GroupId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[a-z][a-z0-9-]{0,39}$"),
]


class PreplanningState(StrEnum):
    DRAFT = "draft"
    DISCOVERING = "discovering"
    NEEDS_CONFIRMATION = "needs_confirmation"
    PRECHECKING = "prechecking"
    FEASIBLE = "feasible"
    CONFLICTED = "conflicted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    EXPIRED = "expired"


class PoiPurpose(StrEnum):
    VISIT = "visit"
    ACCOMMODATION = "accommodation"


class PoiScopeKind(StrEnum):
    POINT = "point"
    AREA = "area"
    COMPLEX = "complex"


class PoiConfirmationStatus(StrEnum):
    VERIFIED = "verified"
    REPRESENTATIVE_REQUIRED = "representative_required"


class AccommodationMode(StrEnum):
    AREA = "area"
    EXACT_POI = "exact_poi"
    MAP_PIN = "map_pin"


class AccommodationConfidence(StrEnum):
    EXACT = "exact"
    AREA_ESTIMATE = "area_estimate"


class PoiImportance(StrEnum):
    MUST_VISIT = "must_visit"
    OPTIONAL = "optional"


class PoiSelectionSource(StrEnum):
    USER_SELECTED = "user_selected"
    SYSTEM_RECOMMENDATION = "system_recommendation"


class FeasibilityConflictCode(StrEnum):
    CONFIRMATION_REQUIRED = "confirmation_required"
    ROUTE_UNREACHABLE = "route_unreachable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    EXTREME_SAME_CITY_LEG = "extreme_same_city_leg"
    IMPLAUSIBLE_ROUTE_RATIO = "implausible_route_ratio"
    ROUTE_ENDPOINT_MISMATCH = "route_endpoint_mismatch"
    DAILY_CAPACITY_EXCEEDED = "daily_capacity_exceeded"
    DAILY_TRANSPORT_BUDGET_EXCEEDED = "daily_transport_budget_exceeded"
    OPTIONAL_OMISSION_CONFIRMATION_REQUIRED = "optional_omission_confirmation_required"
    NO_FEASIBLE_SCHEDULE = "no_feasible_schedule"


class Gcj02Point(ContractModel):
    longitude: float = Field(ge=73.0, le=136.0)
    latitude: float = Field(ge=3.0, le=54.0)


class PoiOption(ContractModel):
    location_id: UUID
    provider: Literal["amap"] = "amap"
    provider_place_id: F009Text
    name: F009Text
    address: F009LongText | None = None
    city_adcode: Adcode
    district_adcode: Adcode
    category_code: F009Text
    category_label: F009Text
    coordinate_gcj02: Gcj02Point
    purpose: PoiPurpose
    scope_kind: PoiScopeKind = PoiScopeKind.POINT
    confirmation_status: PoiConfirmationStatus = PoiConfirmationStatus.VERIFIED


class AccommodationChoice(ContractModel):
    mode: AccommodationMode
    label: F009Text
    confidence: AccommodationConfidence
    semantic_location_id: UUID | None = None
    route_anchor_location_id: UUID

    @model_validator(mode="after")
    def require_mode_confidence_and_anchor(self) -> AccommodationChoice:
        if self.mode is AccommodationMode.EXACT_POI:
            if (
                self.confidence is not AccommodationConfidence.EXACT
                or self.semantic_location_id is None
                or self.semantic_location_id != self.route_anchor_location_id
            ):
                raise ValueError("exact accommodation requires the same verified POI anchor")
        elif self.confidence is not AccommodationConfidence.AREA_ESTIMATE:
            raise ValueError("area and map-pin accommodation must remain estimates")
        if self.mode is AccommodationMode.MAP_PIN and self.semantic_location_id is not None:
            raise ValueError("map pin cannot claim a semantic POI identity")
        return self


class PoiIntent(ContractModel):
    location_id: UUID
    route_anchor_location_id: UUID
    importance: PoiImportance
    either_or_group_id: GroupId | None = None
    visit_group_id: GroupId | None = None
    preferred_day: Annotated[int, Field(strict=True, ge=0, le=6)] | None = None
    expected_duration_minutes: (
        Annotated[int, Field(strict=True, ge=30, le=480, multiple_of=15)] | None
    ) = None
    omission_allowed: bool = False
    source: PoiSelectionSource = PoiSelectionSource.USER_SELECTED

    @model_validator(mode="after")
    def require_one_group_kind(self) -> PoiIntent:
        if self.either_or_group_id is not None and self.visit_group_id is not None:
            raise ValueError("a POI cannot belong to both group kinds")
        if (
            self.importance is PoiImportance.MUST_VISIT
            and self.omission_allowed
            and self.either_or_group_id is None
        ):
            raise ValueError("a standalone must-visit POI cannot be omitted")
        return self


class PreplanningSelection(ContractModel):
    accommodation: AccommodationChoice
    pois: Annotated[tuple[PoiIntent, ...], Field(min_length=1, max_length=8)]
    allow_system_recommendations: bool = False

    @model_validator(mode="after")
    def require_unique_and_valid_groups(self) -> PreplanningSelection:
        ids = [item.location_id for item in self.pois]
        if len(set(ids)) != len(ids):
            raise ValueError("selected POI ids must be unique")
        if (
            any(item.source is PoiSelectionSource.SYSTEM_RECOMMENDATION for item in self.pois)
            and not self.allow_system_recommendations
        ):
            raise ValueError("system recommendations require explicit permission")

        for attr in ("either_or_group_id", "visit_group_id"):
            groups: dict[str, list[PoiIntent]] = {}
            for item in self.pois:
                group = getattr(item, attr)
                if group is not None:
                    groups.setdefault(group, []).append(item)
            for members in groups.values():
                if len(members) < 2:
                    raise ValueError("POI groups require at least two members")
                if len({member.importance for member in members}) != 1:
                    raise ValueError("POI group members must share importance")
                if attr == "visit_group_id":
                    preferred = {
                        member.preferred_day
                        for member in members
                        if member.preferred_day is not None
                    }
                    if len(preferred) > 1:
                        raise ValueError("visit-group members must share preferred day")
        return self


class PreplanningTripInput(ContractModel):
    city: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=2, max_length=30),
    ]
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    total_budget: Money
    one_night_cost: Money | None = None
    meal_budget_per_person_per_day: Money = Field(
        default_factory=lambda: Money(amount=Decimal("100.00"))
    )
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    pace: Pace = Pace.BALANCED
    transport_modes: Annotated[tuple[TransportMode, ...], Field(min_length=1, max_length=2)]
    day_windows: Annotated[tuple[MultiDayTimeWindow, ...], Field(min_length=2, max_length=7)]

    @model_validator(mode="after")
    def require_exact_days(self) -> PreplanningTripInput:
        day_count = (self.end_date - self.start_date).days + 1
        if not 2 <= day_count <= 7:
            raise ValueError("preplanning trip must contain two to seven days")
        if len(self.day_windows) != day_count or {
            item.day_offset for item in self.day_windows
        } != set(range(day_count)):
            raise ValueError("day windows must exactly cover trip offsets")
        if len(set(self.transport_modes)) != len(self.transport_modes):
            raise ValueError("transport modes must be unique")
        return self

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


class PreplanningSessionCreateRequest(ContractModel):
    session_version: Literal["1"] = "1"
    trip: PreplanningTripInput


class PreplanningSelectionUpdate(ContractModel):
    expected_revision: int = Field(strict=True, ge=0)
    selection: PreplanningSelection


class PreplanningTripUpdate(ContractModel):
    expected_revision: int = Field(strict=True, ge=0)
    trip: PreplanningTripInput


class SafeCallCounts(ContractModel):
    poi_search: int = Field(strict=True, ge=0, le=25)
    reverse_geocode: int = Field(strict=True, ge=0, le=4)
    route: int = Field(strict=True, ge=0, le=24)
    total: int = Field(strict=True, ge=0, le=60)


class PreplanningSessionResponse(ContractModel):
    session_version: Literal["1"] = "1"
    session_id: UUID
    revision: int = Field(strict=True, ge=0)
    state: PreplanningState
    trip: PreplanningTripInput
    city_adcode: Adcode | None = None
    city_name: F009Text | None = None
    selection: PreplanningSelection | None = None
    calls: SafeCallCounts
    created_at: datetime
    expires_at: datetime
    absolute_expires_at: datetime

    @field_validator("created_at", "expires_at", "absolute_expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("session timestamps must include timezone")
        return value


class PoiSearchResponse(ContractModel):
    session_id: UUID
    revision: int = Field(strict=True, ge=0)
    state: PreplanningState
    page: int = Field(strict=True, ge=1, le=5)
    page_size: int = Field(strict=True, ge=1, le=20)
    has_more: bool
    items: Annotated[tuple[PoiOption, ...], Field(max_length=20)]
    calls: SafeCallCounts


class PoiSearchQuery(ContractModel):
    purpose: PoiPurpose
    keywords: Annotated[
        str,
        StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=80),
    ]
    district_adcode: Adcode | None = None
    center: Gcj02Point | None = None
    radius_m: int | None = Field(default=None, strict=True, ge=100, le=50_000)
    category_codes: Annotated[tuple[F009Text, ...], Field(max_length=5)] = ()
    page: int = Field(default=1, strict=True, ge=1, le=5)
    page_size: int = Field(default=20, strict=True, ge=1, le=20)

    @model_validator(mode="after")
    def require_center_and_radius_together(self) -> PoiSearchQuery:
        if (self.center is None) != (self.radius_m is None):
            raise ValueError("center and radius must be supplied together")
        return self


class MapPinCreateRequest(ContractModel):
    expected_revision: int = Field(strict=True, ge=0)
    coordinate: Gcj02Point


class MapPinResponse(ContractModel):
    session_id: UUID
    revision: int = Field(strict=True, ge=0)
    location_id: UUID
    label: F009Text
    city_adcode: Adcode
    district_adcode: Adcode
    coordinate: Gcj02Point
    calls: SafeCallCounts


class FeasibilityConflict(ContractModel):
    code: FeasibilityConflictCode
    message: F009LongText
    location_ids: Annotated[tuple[UUID, ...], Field(max_length=8)] = ()
    route_id: UUID | None = None
    recovery_options: Annotated[tuple[F009Text, ...], Field(max_length=6)] = ()


class RoutePreflightLeg(ContractModel):
    route_id: UUID
    origin_location_id: UUID
    destination_location_id: UUID
    mode: TransportMode
    straight_line_meters: int = Field(strict=True, ge=0)
    distance_meters: int = Field(strict=True, ge=0, le=200_000)
    duration_minutes: int = Field(strict=True, ge=1, le=240)


class FeasibilityStop(ContractModel):
    location_id: UUID
    route_anchor_location_id: UUID
    name: F009Text
    category: F009Text
    importance: PoiImportance
    expected_duration_minutes: int = Field(strict=True, ge=30, le=480)
    start_time: time
    end_time: time
    preferred_day_satisfied: bool
    source: PoiSelectionSource


class FeasibilityDay(ContractModel):
    local_date: date
    stops: Annotated[tuple[FeasibilityStop, ...], Field(min_length=1, max_length=4)]
    routes: Annotated[tuple[RoutePreflightLeg, ...], Field(min_length=2, max_length=5)]
    total_transport_minutes: int = Field(strict=True, ge=1)


class PreflightResponse(ContractModel):
    session_id: UUID
    revision: int = Field(strict=True, ge=0)
    state: PreplanningState
    feasibility_id: UUID | None = None
    days: Annotated[tuple[FeasibilityDay, ...], Field(max_length=7)] = ()
    conflicts: Annotated[tuple[FeasibilityConflict, ...], Field(max_length=50)] = ()
    calls: SafeCallCounts

    @model_validator(mode="after")
    def require_state_shape(self) -> PreflightResponse:
        if self.state is PreplanningState.FEASIBLE and (
            self.feasibility_id is None or not self.days or self.conflicts
        ):
            raise ValueError("feasible preflight requires a conflict-free snapshot")
        if self.state is not PreplanningState.FEASIBLE and self.feasibility_id is not None:
            raise ValueError("only feasible preflight may expose a token")
        return self


class PreflightRequest(ContractModel):
    expected_revision: int = Field(strict=True, ge=1)


class TripPlanRequestV5(ContractModel):
    request_version: Literal["5"]
    client_request_id: UUID
    session_id: UUID
    selection_revision: int = Field(strict=True, ge=1)
    feasibility_id: UUID
    trip: PreplanningTripInput
    selection: PreplanningSelection


class NarrativeRetryRequestV5(ContractModel):
    request_version: Literal["5"]
    client_request_id: UUID


class PlanLocationV5(ContractModel):
    location_id: UUID
    name: F009Text
    category: F009Text
    district_adcode: Adcode
    source: PoiSelectionSource | Literal["accommodation"]


class PlanStopV5(ContractModel):
    location_id: UUID
    visit_order: int = Field(strict=True, ge=1, le=4)
    start_time: time
    end_time: time
    importance: PoiImportance
    narrative: F009LongText | None = None


class PlanRouteSummaryV5(ContractModel):
    route_id: UUID
    origin_location_id: UUID
    destination_location_id: UUID
    mode: TransportMode
    distance_meters: int = Field(strict=True, ge=0, le=200_000)
    duration_minutes: int = Field(strict=True, ge=1, le=240)


class PlanDayV5(ContractModel):
    local_date: date
    accommodation_location_id: UUID
    stops: Annotated[tuple[PlanStopV5, ...], Field(min_length=1, max_length=4)]
    routes: Annotated[tuple[PlanRouteSummaryV5, ...], Field(min_length=2, max_length=5)]
    pace_note: F009LongText | None = None
    rationale: F009LongText | None = None


class TripPlanV5(ContractModel):
    plan_id: UUID
    plan_format_version: Literal["5"] = "5"
    city_adcode: Adcode
    start_date: date
    end_date: date
    accommodation: AccommodationChoice
    locations: Annotated[tuple[PlanLocationV5, ...], Field(min_length=2, max_length=9)]
    days: Annotated[tuple[PlanDayV5, ...], Field(min_length=2, max_length=7)]
    global_notes: Annotated[tuple[F009LongText, ...], Field(max_length=10)] = ()


class TripRequestSummaryV5(ContractModel):
    request_version: Literal["5"] = "5"
    city: F009Text
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    budget: Money
    selected_poi_count: int = Field(strict=True, ge=1, le=8)


class TripPlanResponseV5(ContractModel):
    response_version: Literal["5"] = "5"
    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    status: PlanningStatus
    attempt: Literal[1] = 1
    request_summary: TripRequestSummaryV5
    plan: TripPlanV5 | None = None
    conflicts: Annotated[tuple[FeasibilityConflict, ...], Field(max_length=50)] = ()
    warnings: Annotated[tuple[F009LongText, ...], Field(max_length=50)] = ()
    errors: Annotated[tuple[ApiError, ...], Field(max_length=20)] = ()
    retryable: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_response_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("response timestamps must include timezone")
        return value

    @model_validator(mode="after")
    def require_terminal_shape(self) -> TripPlanResponseV5:
        if self.updated_at < self.created_at:
            raise ValueError("response timestamps are out of order")
        if self.status in {PlanningStatus.READY, PlanningStatus.PARTIAL} and self.plan is None:
            raise ValueError("ready and partial V5 results require a plan")
        if self.status is PlanningStatus.READY and (
            self.conflicts or self.errors or self.retryable
        ):
            raise ValueError("ready V5 result must be conflict free")
        if self.status is PlanningStatus.CONFLICT and not self.conflicts:
            raise ValueError("conflict V5 result requires conflicts")
        if self.status is PlanningStatus.FAILED and not self.errors:
            raise ValueError("failed V5 result requires errors")
        return self


class MapMarkerV1(ContractModel):
    location_id: UUID
    name: F009Text
    coordinate: Gcj02Point
    visit_order: int | None = Field(default=None, strict=True, ge=1, le=4)


class MapPolylineV1(ContractModel):
    route_id: UUID
    origin_location_id: UUID
    destination_location_id: UUID
    mode: TransportMode
    distance_meters: int = Field(strict=True, ge=0, le=200_000)
    duration_minutes: int = Field(strict=True, ge=1, le=240)
    points: Annotated[tuple[Gcj02Point, ...], Field(min_length=2, max_length=500)]


class MapDayLayerV1(ContractModel):
    local_date: date
    color_token: Literal["day-1", "day-2", "day-3", "day-4", "day-5", "day-6", "day-7"]
    markers: Annotated[tuple[MapMarkerV1, ...], Field(min_length=1, max_length=4)]
    routes: Annotated[tuple[MapPolylineV1, ...], Field(max_length=5)]


class MapPlanV1(ContractModel):
    map_version: Literal["1"] = "1"
    job_id: UUID
    plan_id: UUID
    coordinate_system: Literal["gcj02"] = "gcj02"
    accommodation: MapMarkerV1
    days: Annotated[tuple[MapDayLayerV1, ...], Field(min_length=2, max_length=7)]
    warnings: Annotated[tuple[F009LongText, ...], Field(max_length=20)] = ()
