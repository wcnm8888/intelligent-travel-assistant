"""FastAPI routes for local planning-job resources."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Response, status

from intelligent_travel_assistant.api.errors import (
    PlanningHttpError,
    internal_error,
    job_not_found_error,
    repository_http_error,
)
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
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
    PlanningRequest,
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
) -> APIRouter:
    """Bind one application repository to a narrow HTTP adapter."""

    router = APIRouter(prefix="/api/trip-plans", tags=["trip-plans"])

    @router.post(
        "",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=PlanningResponse,
        responses={
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Create or reuse a local planning job",
    )
    async def create_trip_plan(
        request: PlanningRequest,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> PlanningResponse:
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
        response_model=PlanningResponse,
        responses={
            404: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Read a local planning job",
    )
    async def get_trip_plan(job_id: str) -> PlanningResponse:
        identifier = _job_id(job_id)
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

    return router
