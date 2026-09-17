"""Strict V6 travel advisor contracts; all state remains process-local."""

from __future__ import annotations

from datetime import time
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.contracts.f009 import PoiImportance, PreplanningSelection

AdvisorText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=500),
]
AdvisorLabel = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120),
]


class AdvisorPhase(StrEnum):
    INTERVIEW = "interview"
    CURATION = "curation"
    READY = "ready"
    DEGRADED = "degraded"


class AdvisorConversationEntry(ContractModel):
    role: Literal["user", "advisor"]
    text: AdvisorText


class AdvisorPreferencePatch(ContractModel):
    walking_tolerance: Literal["low", "medium", "high"] | None = None
    crowd_tolerance: Literal["low", "medium", "high"] | None = None
    day_start: time | None = None
    food_preferences: Annotated[tuple[AdvisorLabel, ...], Field(max_length=5)] = ()
    budget_flexibility: Literal["fixed", "small", "flexible"] | None = None
    party_notes: Annotated[tuple[AdvisorLabel, ...], Field(max_length=5)] = ()

    def is_empty(self) -> bool:
        return not any(
            (
                self.walking_tolerance,
                self.crowd_tolerance,
                self.day_start,
                self.food_preferences,
                self.budget_flexibility,
                self.party_notes,
            )
        )


class AdvisorSuggestion(ContractModel):
    suggestion_id: UUID
    kind: Literal["preference_patch", "poi"]
    title: AdvisorLabel
    reason: AdvisorText
    preference_patch: AdvisorPreferencePatch | None = None
    location_id: UUID | None = None
    location_name: AdvisorLabel | None = None
    category: AdvisorLabel | None = None

    @model_validator(mode="after")
    def require_kind_payload(self) -> AdvisorSuggestion:
        if self.kind == "preference_patch":
            if self.preference_patch is None or self.preference_patch.is_empty():
                raise ValueError("preference suggestion requires a nonempty patch")
            if self.location_id is not None:
                raise ValueError("preference suggestion cannot contain a location")
        elif (
            self.location_id is None
            or self.location_name is None
            or self.category is None
            or self.preference_patch is not None
        ):
            raise ValueError("POI suggestion requires only a verified location")
        return self


class AdvisorSnapshotResponse(ContractModel):
    advisor_version: Literal["1"] = "1"
    session_id: UUID
    revision: int = Field(strict=True, ge=0)
    phase: AdvisorPhase
    conversation: Annotated[tuple[AdvisorConversationEntry, ...], Field(max_length=12)] = ()
    confirmed_preferences: AdvisorPreferencePatch
    pending_suggestions: Annotated[tuple[AdvisorSuggestion, ...], Field(max_length=6)] = ()
    question: AdvisorText | None = None
    safety_summary: AdvisorText


class AdvisorTurnRequest(ContractModel):
    advisor_version: Literal["1"]
    client_request_id: UUID
    expected_revision: int = Field(strict=True, ge=0)
    message: AdvisorText


class AdvisorActionRequest(ContractModel):
    advisor_version: Literal["1"]
    client_request_id: UUID
    expected_revision: int = Field(strict=True, ge=0)
    suggestion_id: UUID
    action: Literal["accept", "ignore"]
    importance: PoiImportance = PoiImportance.MUST_VISIT
    selection_context: PreplanningSelection | None = None
