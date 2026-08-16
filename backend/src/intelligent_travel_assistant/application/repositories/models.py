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
from intelligent_travel_assistant.domain.replanning import (
    AdjustActivityTime,
    DeleteActivity,
    ImpactAnalysis,
    PlanChangeSet,
    ReorderActivities,
    ReplaceActivity,
    ReplanChoice,
    ReplanCommand,
    ReplanDecisionStatus,
    ReplanOperation,
    ReplanStatus,
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


class ReplanRepositoryErrorCode(StrEnum):
    IDEMPOTENCY_CONFLICT = "replan_idempotency_conflict"
    REPLAN_NOT_FOUND = "replan_not_found"
    JOB_NOT_FOUND = "job_not_found"
    VERSION_CONFLICT = "replan_version_conflict"
    JOB_VERSION_CONFLICT = "replan_job_version_conflict"
    INVALID_STATE = "replan_state_invalid"
    CONFIRMATION_EXPIRED = "confirmation_expired"
    DECISION_CONFLICT = "decision_conflict"
    IDENTIFIER_INVALID = "replan_identifier_invalid"
    JSON_INVALID = "replan_json_invalid"
    OUTCOME_INVALID = "replan_outcome_invalid"
    COMMIT_INVALID = "replan_commit_invalid"
    BASELINE_CONFLICT = "replan_baseline_conflict"


class ReplanRepositoryError(ValueError):
    """Stable, secret-free errors for the independent replan aggregate."""

    __slots__ = ("code",)

    def __init__(self, code: ReplanRepositoryErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class PlanningJobRepositoryError(ValueError):
    """Stable repository error that never includes identifiers or request text."""

    __slots__ = ("code",)

    def __init__(self, code: PlanningJobRepositoryErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ReplanDecisionRecord:
    decision_id: UUID
    job_id: UUID
    attempt: int
    trace_id: UUID
    baseline_plan_version: int
    kind: str
    status: ReplanDecisionStatus
    command: ReplanCommand
    impact: ImpactAnalysis
    choice: ReplanChoice | None
    created_at: datetime
    decided_at: datetime | None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, UUID) for value in (self.decision_id, self.job_id, self.trace_id)
        ):
            raise ValueError("decision_identifier_invalid")
        if type(self.attempt) is not int or not 1 <= self.attempt <= 3:
            raise ValueError("decision_attempt_invalid")
        if type(self.baseline_plan_version) is not int or self.baseline_plan_version < 1:
            raise ValueError("decision_plan_version_invalid")
        if _SAFE_CODE.fullmatch(self.kind) is None:
            raise ValueError("decision_kind_invalid")
        if not isinstance(self.status, ReplanDecisionStatus):
            raise ValueError("decision_status_invalid")
        if not isinstance(
            self.command,
            (ReplaceActivity, DeleteActivity, AdjustActivityTime, ReorderActivities),
        ):
            raise ValueError("decision_command_invalid")
        if not isinstance(self.impact, ImpactAnalysis):
            raise ValueError("decision_impact_invalid")
        if self.choice is not None and not isinstance(self.choice, ReplanChoice):
            raise ValueError("decision_choice_invalid")
        _require_aware_datetime(self.created_at, "decision_created_at")
        if self.decided_at is not None:
            _require_aware_datetime(self.decided_at, "decision_decided_at")


@dataclass(frozen=True, slots=True)
class ReplanRecord:
    replan_id: UUID
    job_id: UUID
    replan_request_id: UUID
    request_fingerprint: RequestFingerprint
    baseline_plan_id: UUID
    baseline_plan_version: int
    expected_job_version: int
    trace_id: UUID
    operation: ReplanOperation
    command: ReplanCommand
    impact: ImpactAnalysis | None
    status: ReplanStatus
    aggregate_version: int
    decision: ReplanDecisionRecord | None
    result_plan_version: int | None
    result: PlanningJobResult | None = field(repr=False)
    change_set: PlanChangeSet | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    decided_at: datetime | None

    def __post_init__(self) -> None:
        identifiers = (
            self.replan_id,
            self.job_id,
            self.replan_request_id,
            self.baseline_plan_id,
            self.trace_id,
        )
        if any(not isinstance(value, UUID) for value in identifiers):
            raise ValueError("replan_identifier_invalid")
        if not isinstance(self.request_fingerprint, RequestFingerprint):
            raise ValueError("replan_fingerprint_invalid")
        if type(self.baseline_plan_version) is not int or self.baseline_plan_version < 1:
            raise ValueError("replan_plan_version_invalid")
        if type(self.expected_job_version) is not int or self.expected_job_version < 1:
            raise ValueError("replan_job_version_invalid")
        if not isinstance(self.operation, ReplanOperation):
            raise ValueError("replan_operation_invalid")
        if not isinstance(
            self.command,
            (ReplaceActivity, DeleteActivity, AdjustActivityTime, ReorderActivities),
        ):
            raise ValueError("replan_command_invalid")
        if self.command.operation is not self.operation:
            raise ValueError("replan_operation_mismatch")
        if self.impact is not None and not isinstance(self.impact, ImpactAnalysis):
            raise ValueError("replan_impact_invalid")
        if not isinstance(self.status, ReplanStatus):
            raise ValueError("replan_status_invalid")
        if type(self.aggregate_version) is not int or self.aggregate_version < 1:
            raise ValueError("replan_aggregate_version_invalid")
        if self.decision is not None and not isinstance(self.decision, ReplanDecisionRecord):
            raise ValueError("replan_decision_invalid")
        if self.result_plan_version is not None and (
            type(self.result_plan_version) is not int or self.result_plan_version < 1
        ):
            raise ValueError("replan_result_version_invalid")
        if self.change_set is not None and not isinstance(self.change_set, PlanChangeSet):
            raise ValueError("replan_change_set_invalid")
        if (self.status is ReplanStatus.COMPLETED) != (
            self.result_plan_version is not None
            and self.result is not None
            and self.change_set is not None
        ):
            raise ValueError("replan_completed_projection_invalid")
        if self.result is not None and (
            not isinstance(self.result, PlanningJobResult)
            or self.result.plan is None
            or self.change_set is None
            or self.result.plan.plan_id != self.change_set.result_plan_id
        ):
            raise ValueError("replan_result_projection_invalid")
        if self.error_code is not None and _SAFE_CODE.fullmatch(self.error_code) is None:
            raise ValueError("replan_error_code_invalid")
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
            ("expires_at", self.expires_at),
        ):
            _require_aware_datetime(value, field_name)
        if self.updated_at < self.created_at:
            raise ValueError("replan_timestamp_order_invalid")
        if self.decided_at is not None:
            _require_aware_datetime(self.decided_at, "replan_decided_at")


@dataclass(frozen=True, slots=True)
class ReplanReservation:
    created: bool
    replan: ReplanRecord

    def __post_init__(self) -> None:
        if type(self.created) is not bool or not isinstance(self.replan, ReplanRecord):
            raise ValueError("replan_reservation_invalid")


@dataclass(frozen=True, slots=True)
class ReplanOutcome:
    status: ReplanStatus
    error_code: str

    def __post_init__(self) -> None:
        if self.status not in {
            ReplanStatus.NEEDS_INPUT,
            ReplanStatus.CONFLICT,
            ReplanStatus.FAILED,
            ReplanStatus.REJECTED,
            ReplanStatus.CANCELLED,
            ReplanStatus.EXPIRED,
        }:
            raise ValueError("replan_outcome_status_invalid")
        if _SAFE_CODE.fullmatch(self.error_code) is None:
            raise ValueError("replan_outcome_code_invalid")


@dataclass(frozen=True, slots=True)
class ReplanCommit:
    result: PlanningJobResult
    change_set: PlanChangeSet

    def __post_init__(self) -> None:
        if not isinstance(self.result, PlanningJobResult) or self.result.status not in {
            PlanningStatus.READY,
            PlanningStatus.PARTIAL,
        }:
            raise ValueError("replan_commit_result_invalid")
        if self.result.plan is None:
            raise ValueError("replan_commit_plan_required")
        if (
            self.result.status is PlanningStatus.READY
            and self.result.plan.budget_summary.unknown_count > 0
        ):
            raise ValueError("replan_ready_unknown_budget_invalid")
        if not isinstance(self.change_set, PlanChangeSet):
            raise ValueError("replan_commit_change_set_invalid")
        if self.change_set.result_plan_id != self.result.plan.plan_id:
            raise ValueError("replan_commit_plan_mismatch")


@dataclass(frozen=True, slots=True)
class ReplanCommitResult:
    replan: ReplanRecord
    job_version: int
    plan_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.replan, ReplanRecord):
            raise ValueError("replan_commit_result_invalid")
        if self.replan.status is not ReplanStatus.COMPLETED:
            raise ValueError("replan_commit_status_invalid")
        if self.replan.result_plan_version is None:
            raise ValueError("replan_commit_version_missing")
        if type(self.job_version) is not int or self.job_version < 2:
            raise ValueError("replan_commit_job_version_invalid")
        if type(self.plan_version) is not int or self.plan_version < 2:
            raise ValueError("replan_commit_plan_version_invalid")
        if self.replan.result_plan_version != self.plan_version:
            raise ValueError("replan_commit_version_mismatch")


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


def _require_aware_datetime(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{field}_invalid")


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
