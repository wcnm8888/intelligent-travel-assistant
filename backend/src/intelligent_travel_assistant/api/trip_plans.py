"""FastAPI routes for local planning-job resources."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Response, status
from pydantic import Discriminator, Tag

from intelligent_travel_assistant.api.errors import (
    PlanningHttpError,
    internal_error,
    job_not_found_error,
    repository_http_error,
)
from intelligent_travel_assistant.api.preplanning import preplanning_http_error
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
from intelligent_travel_assistant.application.f009 import (
    F009ServiceError,
    F009ServiceErrorCode,
    PreplanningService,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    PlanningJobRepositoryError,
    PlanningJobResult,
    PlanningJobResultV3,
    PlanningJobResultV4,
)
from intelligent_travel_assistant.contracts import (
    ApiErrorResponse,
    CityStaySummaryV3,
    PlanningResponse,
    TripPlan,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanRequestV3,
    TripPlanRequestV4,
    TripPlanResponse,
    TripPlanResponseV2,
    TripPlanResponseV3,
    TripPlanResponseV4,
    TripPlanV2,
    TripPlanV3,
    TripPlanV4,
    TripRequestSummary,
    TripRequestSummaryV2,
    TripRequestSummaryV3,
    TripRequestSummaryV4,
)
from intelligent_travel_assistant.contracts.errors import ApiErrorCode
from intelligent_travel_assistant.contracts.f009 import (
    MapPlanV1,
    NarrativeRetryRequestV5,
    TripPlanRequestV5,
    TripPlanResponseV5,
)
from intelligent_travel_assistant.contracts.f015 import (
    NarrativeRetryRequestV6,
    TripPlanRequestV6,
    TripPlanResponseV6,
)


def _api_request_version(value: object) -> str | None:
    if isinstance(value, TripPlanRequestV6):
        return "v6"
    if isinstance(value, TripPlanRequestV5):
        return "v5"
    if isinstance(value, TripPlanRequestV4):
        return "v4"
    if isinstance(value, TripPlanRequestV3):
        return "v3"
    if isinstance(value, TripPlanRequestV2):
        return "v2"
    if isinstance(value, TripPlanRequest):
        return "legacy"
    if isinstance(value, Mapping):
        version = value.get("request_version")
        return "legacy" if version is None else f"v{version}"
    return None


def _api_response_version(value: object) -> str | None:
    if isinstance(value, TripPlanResponseV6):
        return "v6"
    if isinstance(value, TripPlanResponseV5):
        return "v5"
    if isinstance(value, TripPlanResponseV4):
        return "v4"
    if isinstance(value, TripPlanResponseV3):
        return "v3"
    if isinstance(value, TripPlanResponseV2):
        return "v2"
    if isinstance(value, TripPlanResponse):
        return "legacy"
    if isinstance(value, Mapping):
        version = value.get("response_version")
        return "legacy" if version is None else f"v{version}"
    return None


AnyPlanningRequest = Annotated[
    Annotated[TripPlanRequest, Tag("legacy")]
    | Annotated[TripPlanRequestV2, Tag("v2")]
    | Annotated[TripPlanRequestV3, Tag("v3")]
    | Annotated[TripPlanRequestV4, Tag("v4")]
    | Annotated[TripPlanRequestV5, Tag("v5")]
    | Annotated[TripPlanRequestV6, Tag("v6")],
    Discriminator(_api_request_version),
]
AnyPlanningResponse = Annotated[
    Annotated[TripPlanResponse, Tag("legacy")]
    | Annotated[TripPlanResponseV2, Tag("v2")]
    | Annotated[TripPlanResponseV3, Tag("v3")]
    | Annotated[TripPlanResponseV4, Tag("v4")]
    | Annotated[TripPlanResponseV5, Tag("v5")]
    | Annotated[TripPlanResponseV6, Tag("v6")],
    Discriminator(_api_response_version),
]


def _job_response(job: PlanningJob) -> PlanningResponse:
    request = job.request
    result = job.result
    if isinstance(request, TripPlanRequestV4):
        if result is not None and not isinstance(result, PlanningJobResultV4):
            raise ValueError("stored_result_format_mismatch")
        v4_plan = result.plan if result is not None else None
        if v4_plan is not None and not isinstance(v4_plan, TripPlanV4):
            raise ValueError("stored_plan_format_mismatch")
        return TripPlanResponseV4(
            response_version="4",
            job_id=job.job_id,
            trace_id=job.trace_id,
            client_request_id=job.client_request_id,
            status=job.status,
            attempt=job.attempt,
            request_summary=TripRequestSummaryV4(
                request_version="4",
                city_stays=tuple(
                    CityStaySummaryV3(city=stay.city, nights=stay.nights)
                    for stay in request.city_stays
                ),
                start_date=request.start_date,
                end_date=request.end_date,
                travelers=request.travelers,
                budget=request.total_budget,
            ),
            resolved_destinations=(result.resolved_destinations if result is not None else ()),
            plan=v4_plan,
            violations=result.violations if result is not None else (),
            warnings=result.warnings if result is not None else (),
            uncertainties=result.uncertainties if result is not None else (),
            sources=result.sources if result is not None else (),
            errors=result.errors if result is not None else (),
            retryable=job.retryable,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    if isinstance(request, TripPlanRequestV3):
        if result is not None and not isinstance(result, PlanningJobResultV3):
            raise ValueError("stored_result_format_mismatch")
        v3_plan = result.plan if result is not None else None
        if v3_plan is not None and not isinstance(v3_plan, TripPlanV3):
            raise ValueError("stored_plan_format_mismatch")
        return TripPlanResponseV3(
            response_version="3",
            job_id=job.job_id,
            trace_id=job.trace_id,
            client_request_id=job.client_request_id,
            status=job.status,
            attempt=job.attempt,
            request_summary=TripRequestSummaryV3(
                request_version="3",
                city_stays=tuple(
                    CityStaySummaryV3(city=stay.city, nights=stay.nights)
                    for stay in request.city_stays
                ),
                start_date=request.start_date,
                end_date=request.end_date,
                travelers=request.travelers,
                budget=request.total_budget,
            ),
            resolved_destinations=(result.resolved_destinations if result is not None else ()),
            plan=v3_plan,
            violations=result.violations if result is not None else (),
            warnings=result.warnings if result is not None else (),
            uncertainties=result.uncertainties if result is not None else (),
            sources=result.sources if result is not None else (),
            errors=result.errors if result is not None else (),
            retryable=job.retryable,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    if result is not None and not isinstance(result, PlanningJobResult):
        raise ValueError("stored_result_format_mismatch")
    if isinstance(request, TripPlanRequestV2):
        v2_plan = result.plan if result is not None else None
        if v2_plan is not None and not isinstance(v2_plan, TripPlanV2):
            raise ValueError("stored_plan_format_mismatch")
        return TripPlanResponseV2(
            response_version="2",
            job_id=job.job_id,
            trace_id=job.trace_id,
            client_request_id=job.client_request_id,
            status=job.status,
            attempt=job.attempt,
            request_summary=TripRequestSummaryV2(
                request_version="2",
                city=request.city,
                start_date=request.start_date,
                end_date=request.end_date,
                travelers=request.travelers,
                budget=request.total_budget,
            ),
            resolved_destination=(result.resolved_destination if result is not None else None),
            plan=v2_plan,
            violations=result.violations if result is not None else (),
            warnings=result.warnings if result is not None else (),
            uncertainties=result.uncertainties if result is not None else (),
            sources=result.sources if result is not None else (),
            errors=result.errors if result is not None else (),
            retryable=job.retryable,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    legacy_plan_value = result.plan if result is not None else None
    if legacy_plan_value is not None and type(legacy_plan_value) is not TripPlan:
        raise ValueError("stored_plan_format_mismatch")
    legacy_plan = legacy_plan_value
    return TripPlanResponse(
        job_id=job.job_id,
        trace_id=job.trace_id,
        client_request_id=job.client_request_id,
        status=job.status,
        attempt=job.attempt,
        request_summary=TripRequestSummary(
            city=request.city,
            start_date=request.start_date,
            end_date=request.start_date + timedelta(days=1),
            travelers=request.travelers,
            budget=request.total_budget,
        ),
        resolved_destination=(result.resolved_destination if result is not None else None),
        plan=legacy_plan,
        violations=result.violations if result is not None else (),
        warnings=result.warnings if result is not None else (),
        uncertainties=result.uncertainties if result is not None else (),
        sources=result.sources if result is not None else (),
        errors=result.errors if result is not None else (),
        retryable=job.retryable,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_id(raw_job_id: str) -> UUID:
    try:
        return UUID(raw_job_id)
    except (AttributeError, TypeError, ValueError):
        raise job_not_found_error() from None


def create_trip_plan_router(
    repository: PlanningJobRepository,
    executor: PlanningJobExecutor | None = None,
    preplanning_service: PreplanningService | None = None,
) -> APIRouter:
    """Bind one application repository to a narrow HTTP adapter."""

    router = APIRouter(prefix="/api/trip-plans", tags=["trip-plans"])

    @router.post(
        "",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=AnyPlanningResponse,
        responses={
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Create or reuse a local planning job",
    )
    async def create_trip_plan(
        request: AnyPlanningRequest,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> AnyPlanningResponse:
        if isinstance(request, TripPlanRequestV6):
            if preplanning_service is None:
                raise PlanningHttpError(
                    409,
                    ApiErrorCode.CONFIGURATION_MISSING,
                    "V6 joint planning is unavailable.",
                )
            try:
                v6_result = await preplanning_service.create_v6_job(request)
            except F009ServiceError as error:
                raise preplanning_http_error(error) from None
            response.headers["Location"] = f"/api/trip-plans/{v6_result.job_id}"
            return v6_result
        if isinstance(request, TripPlanRequestV5):
            if preplanning_service is None:
                raise PlanningHttpError(
                    409,
                    ApiErrorCode.CONFIGURATION_MISSING,
                    "F-009 preplanning is unavailable.",
                )
            try:
                v5_result = await preplanning_service.create_v5_job(request)
            except F009ServiceError as error:
                raise preplanning_http_error(error) from None
            response.headers["Location"] = f"/api/trip-plans/{v5_result.job_id}"
            return v5_result
        try:
            reservation = await repository.get_or_create(request)
            result = _job_response(reservation.job)
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="create") from None
        except Exception:
            raise internal_error() from None
        if (
            reservation.created
            and executor is not None
            and isinstance(request, (TripPlanRequest, TripPlanRequestV3, TripPlanRequestV4))
        ):
            background_tasks.add_task(executor.execute, reservation.job.job_id)
        response.headers["Location"] = f"/api/trip-plans/{result.job_id}"
        return result

    @router.get(
        "/{job_id}",
        response_model=AnyPlanningResponse,
        responses={
            404: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Read a local planning job",
    )
    async def get_trip_plan(job_id: str) -> AnyPlanningResponse:
        identifier = _job_id(job_id)
        if preplanning_service is not None and await preplanning_service.is_v6_job(identifier):
            return await preplanning_service.get_v6_job(identifier)
        if preplanning_service is not None and await preplanning_service.is_v5_job(identifier):
            return await preplanning_service.get_v5_job(identifier)
        try:
            job = await repository.get(identifier)
            return _job_response(job)
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="get") from None
        except PlanningHttpError:
            raise
        except Exception:
            raise internal_error() from None

    @router.delete(
        "/{job_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            404: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Delete one local planning job",
    )
    async def delete_trip_plan(job_id: str) -> Response:
        identifier = _job_id(job_id)
        if preplanning_service is not None and await preplanning_service.is_v6_job(identifier):
            await preplanning_service.delete_v6_job(identifier)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if preplanning_service is not None and await preplanning_service.is_v5_job(identifier):
            await preplanning_service.delete_v5_job(identifier)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        try:
            await repository.delete(identifier)
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="delete") from None
        except PlanningHttpError:
            raise
        except Exception:
            raise internal_error() from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{job_id}/narrative-retries",
        status_code=status.HTTP_200_OK,
        response_model=TripPlanResponseV5 | TripPlanResponseV6,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
        },
        summary="Retry only narrative for an in-memory V5 or V6 plan",
    )
    async def retry_trip_plan_narrative(
        job_id: str,
        request: NarrativeRetryRequestV5 | NarrativeRetryRequestV6,
    ) -> TripPlanResponseV5 | TripPlanResponseV6:
        identifier = _job_id(job_id)
        if preplanning_service is None:
            raise job_not_found_error()
        try:
            if isinstance(request, NarrativeRetryRequestV6):
                return await preplanning_service.retry_v6_narrative(
                    identifier,
                    client_request_id=request.client_request_id,
                )
            return await preplanning_service.retry_v5_narrative(
                identifier,
                client_request_id=request.client_request_id,
            )
        except F009ServiceError as error:
            if error.code is F009ServiceErrorCode.SESSION_NOT_FOUND:
                raise job_not_found_error() from None
            if error.code is F009ServiceErrorCode.NARRATIVE_RETRY_CONFLICT:
                raise PlanningHttpError(
                    409,
                    ApiErrorCode.IDEMPOTENCY_CONFLICT,
                    "The narrative retry id is already bound to another job.",
                ) from None
            if error.code is F009ServiceErrorCode.NARRATIVE_RETRY_NOT_ALLOWED:
                raise PlanningHttpError(
                    409,
                    ApiErrorCode.RETRY_NOT_ALLOWED,
                    "This narrative is not eligible for retry.",
                ) from None
            raise preplanning_http_error(error) from None

    @router.post(
        "/{job_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=PlanningResponse,
        responses={
            404: {"model": ApiErrorResponse},
            409: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Retry an eligible local planning job",
    )
    async def retry_trip_plan(
        job_id: str,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> PlanningResponse:
        identifier = _job_id(job_id)
        if preplanning_service is not None and (
            await preplanning_service.is_v5_job(identifier)
            or await preplanning_service.is_v6_job(identifier)
        ):
            raise PlanningHttpError(
                409,
                ApiErrorCode.RETRY_NOT_ALLOWED,
                "Deterministic V5/V6 plans are not retryable.",
            )
        try:
            current = await repository.get(identifier)
            job = await repository.retry(identifier, expected_version=current.version)
            result = _job_response(job)
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="retry") from None
        except PlanningHttpError:
            raise
        except Exception:
            raise internal_error() from None
        if executor is not None and isinstance(
            job.request, (TripPlanRequest, TripPlanRequestV3, TripPlanRequestV4)
        ):
            background_tasks.add_task(executor.execute, job.job_id)
        response.headers["Location"] = f"/api/trip-plans/{result.job_id}"
        return result

    @router.get(
        "/{job_id}/map",
        response_model=MapPlanV1,
        responses={404: {"model": ApiErrorResponse}, 410: {"model": ApiErrorResponse}},
        summary="Read ephemeral V5 map geometry",
    )
    async def get_trip_plan_map(job_id: str) -> MapPlanV1:
        identifier = _job_id(job_id)
        if preplanning_service is None:
            raise job_not_found_error()
        try:
            return await preplanning_service.get_map_plan(identifier)
        except F009ServiceError as error:
            if error.code is F009ServiceErrorCode.SESSION_NOT_FOUND:
                raise job_not_found_error() from None
            raise preplanning_http_error(error) from None

    return router
