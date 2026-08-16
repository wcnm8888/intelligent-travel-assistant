"""Immutable values and safe errors for planning-job persistence ports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.contracts import (
    ApiError,
    ConstraintViolation,
    PlanningStatus,
    ResolvedDestination,
    SourceRecord,
    TripPlan,
    TripPlanRequest,
    Uncertainty,
)

_TERMINAL_STATUSES: Final = frozenset(
    {
        PlanningStatus.READY,
        PlanningStatus.PARTIAL,
        PlanningStatus.CONFLICT,
        PlanningStatus.NEEDS_INPUT,
        PlanningStatus.FAILED,
    }
)
_UNSAFE_TEXT: Final = re.compile(
    r"authorization\s*:|cookie\s*:|(?:api[_-]?key|token|jwt|secret|password|"
    r"private[_-]?key)\s*[=:]|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_SAFE_CODE: Final = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")


class PlanningJobRepositoryErrorCode(StrEnum):
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    JOB_NOT_FOUND = "job_not_found"
    TRANSITION_NOT_ALLOWED = "transition_not_allowed"
    VERSION_CONFLICT = "version_conflict"
    RETRY_NOT_ALLOWED = "retry_not_allowed"
    RETRY_LIMIT_REACHED = "retry_limit_reached"
    RETRYABLE_FLAG_INVALID = "retryable_flag_invalid"
    IDENTIFIER_INVALID = "identifier_invalid"
    IDENTIFIER_COLLISION = "identifier_collision"
    CLOCK_INVALID = "clock_invalid"
    RESULT_REQUIRED = "result_required"
    RESULT_INVALID = "result_invalid"
    RESULT_REQUEST_MISMATCH = "result_request_mismatch"


class PlanningJobRepositoryError(ValueError):
    """Stable repository error that never includes identifiers or request text."""

    __slots__ = ("code",)

    def __init__(self, code: PlanningJobRepositoryErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class RequestFingerprint:
    """Opaque deterministic digest; the canonical request body is never retained here."""

    digest: str
    algorithm: str = "sha256"

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("fingerprint_algorithm_invalid")
        has_invalid_character = any(
            character not in "0123456789abcdef" for character in self.digest
        )
        if len(self.digest) != 64 or has_invalid_character:
            raise ValueError("fingerprint_digest_invalid")


class AcceptanceStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class AcceptanceEvidence:
    """Small code-only evidence summary; never a raw log, prompt, or provider body."""

    check_codes: tuple[str, ...]
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for values in (self.check_codes, self.limitation_codes):
            if not isinstance(values, tuple) or len(values) > 50:
                raise ValueError("acceptance_evidence_invalid")
            if any(
                _SAFE_CODE.fullmatch(value) is None or _UNSAFE_TEXT.search(value) is not None
                for value in values
            ):
                raise ValueError("acceptance_evidence_invalid")
            if len(set(values)) != len(values):
                raise ValueError("acceptance_evidence_duplicate")


@dataclass(frozen=True, slots=True)
class AcceptanceRecord:
    """Typed internal acceptance record persisted independently from public APIs."""

    acceptance_id: UUID
    job_id: UUID
    attempt: int
    plan_version: int | None
    case_id: str
    status: AcceptanceStatus
    observed_at: datetime
    environment: str
    evidence: AcceptanceEvidence = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.acceptance_id, UUID) or not isinstance(self.job_id, UUID):
            raise ValueError("acceptance_identifier_invalid")
        if type(self.attempt) is not int or not 1 <= self.attempt <= 3:
            raise ValueError("acceptance_attempt_invalid")
        if self.plan_version is not None and (
            type(self.plan_version) is not int or self.plan_version < 1
        ):
            raise ValueError("acceptance_plan_version_invalid")
        if _SAFE_CODE.fullmatch(self.case_id) is None:
            raise ValueError("acceptance_case_invalid")
        if not isinstance(self.status, AcceptanceStatus):
            raise ValueError("acceptance_status_invalid")
        if not isinstance(self.observed_at, datetime) or self.observed_at.utcoffset() is None:
            raise ValueError("acceptance_timestamp_invalid")
        if _SAFE_CODE.fullmatch(self.environment) is None:
            raise ValueError("acceptance_environment_invalid")
        if not isinstance(self.evidence, AcceptanceEvidence):
            raise ValueError("acceptance_evidence_invalid")


def request_fingerprint(request: TripPlanRequest) -> RequestFingerprint:
    """Hash normalized typed input, excluding the idempotency key itself."""

    if not isinstance(request, TripPlanRequest):
        raise TypeError("request_type_invalid")
    normalized = request.model_dump(mode="json", exclude={"client_request_id"})
    canonical = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return RequestFingerprint(digest=hashlib.sha256(canonical).hexdigest())


@dataclass(frozen=True, slots=True)
class PlanningJobResult:
    """Validated public terminal payload stored independently from HTTP identity fields."""

    status: PlanningStatus
    resolved_destination: ResolvedDestination | None
    plan: TripPlan | None
    violations: tuple[ConstraintViolation, ...]
    warnings: tuple[str, ...]
    uncertainties: tuple[Uncertainty, ...]
    sources: tuple[SourceRecord, ...]
    errors: tuple[ApiError, ...]
    retryable: bool

    def __post_init__(self) -> None:
        if self.status not in _TERMINAL_STATUSES:
            raise ValueError("result_status_invalid")
        _require_result_collections(self)
        _require_terminal_shape(self)
        _require_safe_result_text(self)
        _require_result_references(self)


@dataclass(frozen=True, slots=True)
class PlanningJob:
    """Immutable in-process snapshot of one planning job."""

    job_id: UUID
    trace_id: UUID
    client_request_id: UUID
    request_fingerprint: RequestFingerprint
    request: TripPlanRequest = field(repr=False)
    status: PlanningStatus
    attempt: int
    version: int
    retryable: bool
    created_at: datetime
    updated_at: datetime
    result: PlanningJobResult | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        identifiers = (self.job_id, self.trace_id, self.client_request_id)
        if any(not isinstance(identifier, UUID) for identifier in identifiers):
            raise ValueError("job_identifier_invalid")
        if not isinstance(self.request_fingerprint, RequestFingerprint):
            raise ValueError("request_fingerprint_invalid")
        if not isinstance(self.request, TripPlanRequest):
            raise ValueError("request_invalid")
        if self.request.client_request_id != self.client_request_id:
            raise ValueError("client_request_id_mismatch")
        if not isinstance(self.status, PlanningStatus):
            raise ValueError("status_invalid")
        if type(self.attempt) is not int or not 1 <= self.attempt <= 3:
            raise ValueError("attempt_invalid")
        if type(self.version) is not int or self.version < 1:
            raise ValueError("version_invalid")
        if type(self.retryable) is not bool:
            raise ValueError("retryable_invalid")
        for timestamp in (self.created_at, self.updated_at):
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise ValueError("timestamp_invalid")
        if self.updated_at < self.created_at:
            raise ValueError("timestamp_order_invalid")
        if self.result is None:
            if self.status in _TERMINAL_STATUSES:
                raise ValueError("terminal_job_missing_result")
        elif (
            not isinstance(self.result, PlanningJobResult)
            or self.result.status is not self.status
            or self.result.retryable is not self.retryable
        ):
            raise ValueError("job_result_mismatch")


@dataclass(frozen=True, slots=True)
class PlanningJobReservation:
    created: bool
    job: PlanningJob

    def __post_init__(self) -> None:
        if type(self.created) is not bool or not isinstance(self.job, PlanningJob):
            raise ValueError("reservation_invalid")


def result_matches_request(result: PlanningJobResult, request: TripPlanRequest) -> bool:
    """Prevent a valid payload from being attached to a different request."""

    if result.plan is None:
        return True
    plan = result.plan
    return (
        plan.start_date == request.start_date
        and plan.end_date == request.start_date + timedelta(days=1)
        and plan.budget_summary.budget == request.total_budget
        and (
            result.resolved_destination is None
            or result.resolved_destination.adcode == plan.city_adcode
        )
    )


def _require_result_collections(result: PlanningJobResult) -> None:
    collections: tuple[tuple[object, ...], ...] = (
        result.violations,
        result.warnings,
        result.uncertainties,
        result.sources,
        result.errors,
    )
    if any(not isinstance(value, tuple) for value in collections):
        raise ValueError("result_collections_invalid")
    if not all(isinstance(item, ConstraintViolation) for item in result.violations):
        raise ValueError("result_violations_invalid")
    if not all(isinstance(item, str) and item.strip() for item in result.warnings):
        raise ValueError("result_warnings_invalid")
    if not all(isinstance(item, Uncertainty) for item in result.uncertainties):
        raise ValueError("result_uncertainties_invalid")
    if not all(isinstance(item, SourceRecord) for item in result.sources):
        raise ValueError("result_sources_invalid")
    if not all(isinstance(item, ApiError) for item in result.errors):
        raise ValueError("result_errors_invalid")
    if type(result.retryable) is not bool:
        raise ValueError("result_retryable_invalid")


def _require_terminal_shape(result: PlanningJobResult) -> None:
    if result.status is PlanningStatus.READY:
        if result.plan is None or result.retryable or result.errors or result.violations:
            raise ValueError("result_ready_invalid")
    elif result.status is PlanningStatus.PARTIAL:
        diagnostics = (
            result.violations,
            result.warnings,
            result.uncertainties,
            result.errors,
        )
        if result.plan is None or not any(diagnostics):
            raise ValueError("result_partial_invalid")
    elif result.status is PlanningStatus.CONFLICT:
        if result.retryable or not (result.violations or result.errors):
            raise ValueError("result_conflict_invalid")
    elif result.status is PlanningStatus.NEEDS_INPUT:
        if result.plan is not None or result.retryable or not result.errors:
            raise ValueError("result_needs_input_invalid")
    elif result.status is PlanningStatus.FAILED and (result.plan is not None or not result.errors):
        raise ValueError("result_failed_invalid")

    if result.retryable and (
        result.status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}
        or not any(error.retryable for error in result.errors)
    ):
        raise ValueError("result_retryable_invalid")


def _require_safe_result_text(result: PlanningJobResult) -> None:
    values = [*result.warnings]
    values.extend(error.message for error in result.errors)
    values.extend(item.message for item in result.violations)
    values.extend(item.message for item in result.uncertainties)
    for source in result.sources:
        values.extend(source.attributions)
        values.extend(source.warnings)
    if any(_UNSAFE_TEXT.search(value) is not None for value in values):
        raise ValueError("result_text_unsafe")


def _require_result_references(result: PlanningJobResult) -> None:
    known_source_ids = {source.source_id for source in result.sources}
    if len(known_source_ids) != len(result.sources):
        raise ValueError("result_source_id_duplicate")
    referenced_source_ids: set[UUID] = set()
    if result.resolved_destination is not None:
        referenced_source_ids.update(result.resolved_destination.source_ids)
    if result.plan is not None:
        known_location_ids = {location.location_id for location in result.plan.locations}
        referenced_location_ids: set[UUID] = set()
        for location in result.plan.locations:
            referenced_source_ids.update(location.source_ids)
        for cost in result.plan.budget_summary.cost_items:
            referenced_source_ids.update(cost.source_ids)
        for day in result.plan.days:
            referenced_location_ids.add(day.accommodation_location_id)
            if day.weather is not None:
                referenced_location_ids.add(day.weather.location_id)
                referenced_source_ids.update(day.weather.source_ids)
                for alert in day.weather.alerts:
                    referenced_source_ids.update(alert.source_ids)
            for activity in day.activities:
                referenced_location_ids.add(activity.location_id)
                referenced_source_ids.update(activity.source_ids)
                for cost in activity.cost_items:
                    referenced_source_ids.update(cost.source_ids)
            for route in day.routes:
                referenced_location_ids.update(
                    {route.origin_location_id, route.destination_location_id}
                )
                referenced_source_ids.update(route.source_ids)
                if route.fare is not None:
                    referenced_source_ids.update(route.fare.source_ids)
        if not referenced_location_ids <= known_location_ids:
            raise ValueError("result_location_reference_invalid")
    for uncertainty in result.uncertainties:
        referenced_source_ids.update(uncertainty.source_ids)
    if not referenced_source_ids <= known_source_ids:
        raise ValueError("result_source_reference_invalid")
