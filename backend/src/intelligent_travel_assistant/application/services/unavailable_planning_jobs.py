"""Safe planning-job terminal result when required provider adapters are unavailable."""

from __future__ import annotations

from typing import Final
from uuid import UUID

from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobResult,
    PlanningJobResultV3,
    PlanningJobResultV4,
    PlanningResult,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    PlanningRequest,
    PlanningStatus,
    TripPlanRequestV3,
    TripPlanRequestV4,
)

_SAFE_MESSAGE: Final = "本机服务配置不完整，无法生成旅行计划。"
_SAFE_DIAGNOSTIC: Final = "required_provider_configuration_missing"


class ConfigurationMissingPlanningJobExecutor:
    """Publish one typed zero-call failure without consulting providers or the Agent."""

    __slots__ = ("_repository",)

    def __init__(self, repository: PlanningJobRepository) -> None:
        self._repository = repository

    async def execute(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        if job.status is PlanningStatus.DRAFT:
            job = await self._repository.advance(
                job_id,
                PlanningStatus.NORMALIZING,
                expected_version=job.version,
            )
        if job.status is not PlanningStatus.NORMALIZING:
            return
        await self._repository.record_result(
            job_id,
            _configuration_missing_result(job.request),
            expected_version=job.version,
        )


def _configuration_missing_result(request: PlanningRequest) -> PlanningResult:
    error = ApiError(
        code=ApiErrorCode.CONFIGURATION_MISSING,
        message=_SAFE_MESSAGE,
        diagnostic_code=_SAFE_DIAGNOSTIC,
        retryable=False,
    )
    if isinstance(request, TripPlanRequestV4):
        return PlanningJobResultV4(
            status=PlanningStatus.FAILED,
            resolved_destinations=(),
            plan=None,
            violations=(),
            warnings=(),
            uncertainties=(),
            sources=(),
            errors=(error,),
            retryable=False,
        )
    if isinstance(request, TripPlanRequestV3):
        return PlanningJobResultV3(
            status=PlanningStatus.FAILED,
            resolved_destinations=(),
            plan=None,
            violations=(),
            warnings=(),
            uncertainties=(),
            sources=(),
            errors=(error,),
            retryable=False,
        )
    return PlanningJobResult(
        status=PlanningStatus.FAILED,
        resolved_destination=None,
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(error,),
        retryable=False,
    )
