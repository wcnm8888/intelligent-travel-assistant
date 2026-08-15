"""Planning-job persistence contracts owned by the application layer."""

from intelligent_travel_assistant.application.repositories.models import (
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
    RequestFingerprint,
    request_fingerprint,
    result_matches_request,
)
from intelligent_travel_assistant.application.repositories.ports import PlanningJobRepository

__all__ = [
    "PlanningJob",
    "PlanningJobResult",
    "PlanningJobRepository",
    "PlanningJobRepositoryError",
    "PlanningJobRepositoryErrorCode",
    "PlanningJobReservation",
    "RequestFingerprint",
    "request_fingerprint",
    "result_matches_request",
]
