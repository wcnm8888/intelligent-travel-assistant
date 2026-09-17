"""Strict V6 joint-planning contracts backed only by ephemeral session facts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.contracts.errors import ApiError
from intelligent_travel_assistant.contracts.f009 import (
    AccommodationChoice,
    F009LongText,
    F009Text,
    FeasibilityConflict,
    FeasibilityDay,
    PlanDayV5,
    PlanLocationV5,
    PreplanningSelection,
    PreplanningState,
    PreplanningTripInput,
    SafeCallCounts,
)
from intelligent_travel_assistant.contracts.trip_planning import Money, PlanningStatus


class PlanOptionKind(StrEnum):
    LESS_TRANSPORT = "less_transport"
    RELAXED_PACE = "relaxed_pace"
    PREFERENCE_COVERAGE = "preference_coverage"


class WeatherEvidenceStatus(StrEnum):
    VERIFIED = "verified"
    NOT_COVERED = "not_covered"
    UNAVAILABLE = "unavailable"


class PlanOptionV6(ContractModel):
    option_id: UUID
    kind: PlanOptionKind
    title: F009Text
    explanation: F009LongText
    days: Annotated[tuple[FeasibilityDay, ...], Field(min_length=2, max_length=7)]
    omitted_location_ids: Annotated[tuple[UUID, ...], Field(max_length=8)] = ()
    total_transport_minutes: int = Field(strict=True, ge=1)
    preferred_day_deviation: int = Field(strict=True, ge=0)
    preference_coverage_score: int = Field(strict=True, ge=0, le=100)
    weather_status: WeatherEvidenceStatus = WeatherEvidenceStatus.NOT_COVERED
    weather_message: F009Text = "天气尚不可核验"


class PreflightRequestV6(ContractModel):
    request_version: Literal["6"]
    expected_revision: int = Field(strict=True, ge=1)


class PreflightResponseV6(ContractModel):
    response_version: Literal["6"] = "6"
    session_id: UUID
    revision: int = Field(strict=True, ge=1)
    state: PreplanningState
    feasibility_set_id: UUID | None = None
    options: Annotated[tuple[PlanOptionV6, ...], Field(max_length=3)] = ()
    conflicts: Annotated[tuple[FeasibilityConflict, ...], Field(max_length=50)] = ()
    calls: SafeCallCounts

    @model_validator(mode="after")
    def require_state_shape(self) -> PreflightResponseV6:
        if self.state is PreplanningState.FEASIBLE and (
            self.feasibility_set_id is None or not self.options or self.conflicts
        ):
            raise ValueError("feasible V6 preflight requires one to three options")
        if self.state is not PreplanningState.FEASIBLE and self.feasibility_set_id is not None:
            raise ValueError("only feasible V6 preflight may expose a set token")
        return self


class TripPlanRequestV6(ContractModel):
    request_version: Literal["6"]
    client_request_id: UUID
    session_id: UUID
    selection_revision: int = Field(strict=True, ge=1)
    feasibility_set_id: UUID
    option_id: UUID
    trip: PreplanningTripInput
    selection: PreplanningSelection


class NarrativeRetryRequestV6(ContractModel):
    request_version: Literal["6"]
    client_request_id: UUID


class RecoveryActionKind(StrEnum):
    MOVE_TO_DAY = "move_to_day"
    SHORTEN_VISIT = "shorten_visit"
    ALLOW_OMISSION = "allow_omission"
    REMOVE_OPTIONAL = "remove_optional"
    UNLINK_GROUP = "unlink_group"


class RecoveryActionRequestV6(ContractModel):
    request_version: Literal["6"]
    client_request_id: UUID
    expected_revision: int = Field(strict=True, ge=1)
    action: RecoveryActionKind
    location_id: UUID
    target_day: int | None = Field(default=None, strict=True, ge=0, le=6)
    duration_minutes: int | None = Field(default=None, strict=True, ge=30, le=480, multiple_of=15)

    @model_validator(mode="after")
    def require_action_value(self) -> RecoveryActionRequestV6:
        if self.action is RecoveryActionKind.MOVE_TO_DAY and self.target_day is None:
            raise ValueError("move action requires target_day")
        if self.action is RecoveryActionKind.SHORTEN_VISIT and self.duration_minutes is None:
            raise ValueError("shorten action requires duration_minutes")
        if self.action not in {
            RecoveryActionKind.MOVE_TO_DAY,
            RecoveryActionKind.SHORTEN_VISIT,
        } and (self.target_day is not None or self.duration_minutes is not None):
            raise ValueError("action contains an unrelated value")
        return self


class TripPlanV6(ContractModel):
    plan_id: UUID
    plan_format_version: Literal["6"] = "6"
    selected_option_id: UUID
    option_kind: PlanOptionKind
    city_adcode: str = Field(pattern=r"^\d{6}$")
    start_date: date
    end_date: date
    accommodation: AccommodationChoice
    locations: Annotated[tuple[PlanLocationV5, ...], Field(min_length=2, max_length=9)]
    days: Annotated[tuple[PlanDayV5, ...], Field(min_length=2, max_length=7)]
    global_notes: Annotated[tuple[F009LongText, ...], Field(max_length=10)] = ()
    weather_status: WeatherEvidenceStatus
    weather_message: F009Text


class TripRequestSummaryV6(ContractModel):
    request_version: Literal["6"] = "6"
    city: F009Text
    start_date: date
    end_date: date
    travelers: int = Field(strict=True, ge=1, le=8)
    budget: Money
    selected_poi_count: int = Field(strict=True, ge=1, le=8)


class TripPlanResponseV6(ContractModel):
    response_version: Literal["6"] = "6"
    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    status: PlanningStatus
    attempt: Literal[1] = 1
    request_summary: TripRequestSummaryV6
    plan: TripPlanV6 | None = None
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
    def require_terminal_shape(self) -> TripPlanResponseV6:
        if self.updated_at < self.created_at:
            raise ValueError("response timestamps are out of order")
        if self.status in {PlanningStatus.READY, PlanningStatus.PARTIAL} and self.plan is None:
            raise ValueError("ready and partial V6 results require a plan")
        if self.status is PlanningStatus.READY and (
            self.conflicts or self.errors or self.retryable
        ):
            raise ValueError("ready V6 result must be conflict free")
        return self
