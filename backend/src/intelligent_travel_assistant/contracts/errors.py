"""Stable, safe error contract for the trip-planning API."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from intelligent_travel_assistant.contracts.base import ContractModel

SafeMessage = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=300),
]
FieldPath = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=120),
]
DiagnosticCode = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[a-z][a-z0-9_]{0,79}$"),
]


class ApiErrorCode(StrEnum):
    """Project-owned errors; provider raw messages never cross this boundary."""

    INPUT_INVALID = "input_invalid"
    CONFIGURATION_MISSING = "configuration_missing"
    PROVIDER_UNAUTHORIZED = "provider_unauthorized"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_SCHEMA_INVALID = "provider_schema_invalid"
    DATA_MISSING = "data_missing"
    DATA_STALE = "data_stale"
    MODEL_OUTPUT_INVALID = "model_output_invalid"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    BUDGET_INCOMPLETE = "budget_incomplete"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    JOB_NOT_FOUND = "job_not_found"
    RETRY_NOT_ALLOWED = "retry_not_allowed"
    INTERNAL_ERROR = "internal_error"


class ApiError(ContractModel):
    """One safe error item suitable for logs and user-facing responses."""

    code: ApiErrorCode
    message: SafeMessage
    field: FieldPath | None = None
    provider: str | None = Field(default=None, max_length=40)
    diagnostic_code: DiagnosticCode | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    retryable: bool = False


class ApiErrorResponse(ContractModel):
    """HTTP error envelope used before a planning job can represent the failure."""

    trace_id: UUID | None = None
    error: ApiError
