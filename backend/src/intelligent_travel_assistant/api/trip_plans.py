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
)
from intelligent_travel_assistant.contracts import (
    ApiErrorResponse,
    TripPlanRequest,
    TripPlanResponse,
    TripRequestSummary,
)


def _job_response(job: PlanningJob) -> TripPlanResponse:
    request = job.request
    result = job.result
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
        plan=result.plan if result is not None else None,
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
        response_model=TripPlanResponse,
        responses={
            409: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Create or reuse a local planning job",
    )
    async def create_trip_plan(
        request: TripPlanRequest,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> TripPlanResponse:
        try:
            reservation = await repository.get_or_create(request)
            result = _job_response(reservation.job)
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="create") from None
        except Exception:
            raise internal_error() from None
        if reservation.created and executor is not None:
            background_tasks.add_task(executor.execute, reservation.job.job_id)
        response.headers["Location"] = f"/api/trip-plans/{result.job_id}"
        return result

    @router.get(
        "/{job_id}",
        response_model=TripPlanResponse,
        responses={
            404: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        summary="Read a local planning job",
    )
    async def get_trip_plan(job_id: str) -> TripPlanResponse:
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
        response_model=TripPlanResponse,
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
    ) -> TripPlanResponse:
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
        if executor is not None:
            background_tasks.add_task(executor.execute, job.job_id)
        response.headers["Location"] = f"/api/trip-plans/{result.job_id}"
        return result

    return router
