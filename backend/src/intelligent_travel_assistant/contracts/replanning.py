"""Strict public contracts for local F-003 replanning resources."""

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
    DataFreshness,
    TripPlanResponse,
)

ReasonCode = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$"),
]
CategoryCode = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$"),
]
ValidationCode = CategoryCode


class ReplanPublicOperation(StrEnum):
    REPLACE_ACTIVITY = "replace_activity"
    DELETE_ACTIVITY = "delete_activity"
    ADJUST_ACTIVITY_TIME = "adjust_activity_time"
    REORDER_ACTIVITIES = "reorder_activities"


class ReplanPublicStatus(StrEnum):
    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    CONFLICT = "conflict"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ReplanPublicChoice(StrEnum):
    APPROVE = "approve"
    CANCEL = "cancel"


class ReplaceActivityCommand(ContractModel):
    operation: Literal["replace_activity"]
    target_activity_id: UUID
    replacement_categories: Annotated[tuple[CategoryCode, ...], Field(min_length=1, max_length=3)]
    reason_code: ReasonCode | None = None

    @field_validator("replacement_categories")
    @classmethod
    def require_unique_categories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("replacement categories must be unique")
        return value


class DeleteActivityCommand(ContractModel):
    operation: Literal["delete_activity"]
    target_activity_id: UUID
    reason_code: ReasonCode | None = None


class AdjustActivityTimeCommand(ContractModel):
    operation: Literal["adjust_activity_time"]
    target_activity_id: UUID
    start_time: time
    end_time: time
    reason_code: ReasonCode | None = None

    @model_validator(mode="after")
    def require_local_positive_time_range(self) -> AdjustActivityTimeCommand:
        if (
            self.start_time.tzinfo is not None
            or self.end_time.tzinfo is not None
            or self.end_time <= self.start_time
        ):
            raise ValueError("activity time range is invalid")
        return self


class ReorderActivitiesCommand(ContractModel):
    operation: Literal["reorder_activities"]
    local_date: date
    ordered_activity_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]
    reason_code: ReasonCode | None = None

    @field_validator("ordered_activity_ids")
    @classmethod
    def require_unique_activity_ids(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(set(value)) != len(value):
            raise ValueError("ordered activity IDs must be unique")
        return value


type ReplanCommandRequest = Annotated[
    ReplaceActivityCommand
    | DeleteActivityCommand
    | AdjustActivityTimeCommand
    | ReorderActivitiesCommand,
    Field(discriminator="operation"),
]


class ReplanRequest(ContractModel):
    replan_request_id: UUID
    baseline_plan_id: UUID
    command: ReplanCommandRequest


class ReplanDecisionRequest(ContractModel):
    choice: ReplanPublicChoice


class ReplanBudgetEffectResponse(ContractModel):
    known_total_delta: Decimal
    unknown_count_delta: int = Field(strict=True)
    risk_increased: bool


class ReplanSourceActionResponse(ContractModel):
    source_id: UUID
    action: Literal["reuse", "refresh", "drop"]
    freshness: DataFreshness
    reason: Literal[
        "unaffected_fresh",
        "affected",
        "stale",
        "unknown_validity",
        "removed",
        "not_required",
    ]


class ReplanImpactResponse(ContractModel):
    categories: tuple[
        Literal[
            "same_day_low",
            "adjacent_day",
            "cross_day",
            "accommodation_effect",
            "budget_risk",
            "source_refresh",
            "cross_city",
            "unknown_impact",
        ],
        ...,
    ]
    direct_refs: tuple[UUID, ...]
    transitive_refs: tuple[UUID, ...]
    affected_dates: tuple[date, ...]
    route_refs: tuple[UUID, ...]
    budget_effect: ReplanBudgetEffectResponse | None
    source_actions: tuple[ReplanSourceActionResponse, ...]
    required_validations: tuple[ValidationCode, ...]
    confirmation_required: bool


class ReplanDecisionResponse(ContractModel):
    decision_id: UUID | None
    choice: ReplanPublicChoice | None
    decided_at: datetime | None

    @field_validator("decided_at")
    @classmethod
    def require_aware_decision_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("decision timestamp must include timezone")
        return value


class ReplanChangeSetResponse(ContractModel):
    baseline_plan_id: UUID
    result_plan_id: UUID
    added_refs: tuple[UUID, ...]
    removed_refs: tuple[UUID, ...]
    changed_refs: tuple[UUID, ...]
    change_codes: tuple[CategoryCode, ...]


class ReplanResponse(ContractModel):
    job_id: UUID
    replan_id: UUID
    replan_request_id: UUID
    trace_id: UUID
    baseline_plan_id: UUID
    operation: ReplanPublicOperation
    status: ReplanPublicStatus
    impact: ReplanImpactResponse | None
    confirmation_expires_at: datetime
    decision: ReplanDecisionResponse | None
    result: TripPlanResponse | None
    change_set: ReplanChangeSetResponse | None
    errors: tuple[ApiError, ...]
    created_at: datetime
    updated_at: datetime

    @field_validator("confirmation_expires_at", "created_at", "updated_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("replan timestamp must include timezone")
        return value

    @model_validator(mode="after")
    def require_completed_projection(self) -> ReplanResponse:
        completed = self.status is ReplanPublicStatus.COMPLETED
        if completed != (self.result is not None and self.change_set is not None):
            raise ValueError("completed replan projection is invalid")
        return self
