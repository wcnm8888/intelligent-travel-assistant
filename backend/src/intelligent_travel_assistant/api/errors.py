"""Safe project error mapping for the local HTTP adapter."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
)
from intelligent_travel_assistant.contracts import ApiError, ApiErrorCode, ApiErrorResponse


class PlanningHttpError(Exception):
    """HTTP status plus a stable public error; never stores the source exception."""

    __slots__ = ("status_code", "error")

    def __init__(self, status_code: int, code: ApiErrorCode, message: str) -> None:
        self.status_code = status_code
        self.error = ApiError(code=code, message=message, retryable=False)
        super().__init__(code.value)


def repository_http_error(
    error: PlanningJobRepositoryError,
    *,
    operation: str,
) -> PlanningHttpError:
    """Map repository policy failures without forwarding identifiers or messages."""

    if error.code is PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT:
        return PlanningHttpError(
            409,
            ApiErrorCode.IDEMPOTENCY_CONFLICT,
            "The client request ID is already used for different input.",
        )
    if error.code is PlanningJobRepositoryErrorCode.JOB_NOT_FOUND:
        return job_not_found_error()
    if operation == "retry" and error.code in {
        PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED,
        PlanningJobRepositoryErrorCode.RETRY_LIMIT_REACHED,
        PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED,
        PlanningJobRepositoryErrorCode.VERSION_CONFLICT,
    }:
        return PlanningHttpError(
            409,
            ApiErrorCode.RETRY_NOT_ALLOWED,
            "The planning job cannot be retried.",
        )
    return internal_error()


def input_invalid_error() -> PlanningHttpError:
    return PlanningHttpError(
        422,
        ApiErrorCode.INPUT_INVALID,
        "Request does not match the public API contract.",
    )


def job_not_found_error() -> PlanningHttpError:
    return PlanningHttpError(
        404,
        ApiErrorCode.JOB_NOT_FOUND,
        "The planning job was not found.",
    )


def internal_error() -> PlanningHttpError:
    return PlanningHttpError(
        500,
        ApiErrorCode.INTERNAL_ERROR,
        "The planning request could not be processed safely.",
    )


def error_response(error: PlanningHttpError) -> JSONResponse:
    envelope = ApiErrorResponse(trace_id=None, error=error.error)
    return JSONResponse(
        status_code=error.status_code,
        content=envelope.model_dump(mode="json", exclude_none=True),
    )
