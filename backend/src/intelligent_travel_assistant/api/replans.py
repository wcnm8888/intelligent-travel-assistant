"""FastAPI routes and projections for local F-003 replan resources."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Response, status

from intelligent_travel_assistant.api.errors import (
    PlanningHttpError,
    confirmation_expired_error,
    input_invalid_error,
    internal_error,
    job_not_found_error,
    replan_http_error,
    replan_not_allowed_error,
    replan_scope_not_supported_error,
    repository_http_error,
)
from intelligent_travel_assistant.api.trip_plans import _job_response
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationError,
    ReplanApplicationRequest,
    ReplanApplicationResult,
    ReplanApplicationService,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJobRepository,
    PlanningJobRepositoryError,
    ReplanRecord,
    ReplanRepositoryError,
)
from intelligent_travel_assistant.contracts import (
    AdjustActivityTimeCommand,
    ApiError,
    ApiErrorCode,
    ApiErrorResponse,
    DataFreshness,
    DeleteActivityCommand,
    ReorderActivitiesCommand,
    ReplaceActivityCommand,
    ReplanChangeSetResponse,
    ReplanDecisionRequest,
    ReplanDecisionResponse,
    ReplanImpactResponse,
    ReplanPublicChoice,
    ReplanPublicOperation,
    ReplanPublicStatus,
    ReplanRequest,
    ReplanResponse,
    ReplanSourceActionResponse,
    TripPlanRequestV2,
    TripPlanRequestV3,
    TripPlanRequestV4,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DeleteActivity,
    DomainInvariantError,
    ReorderActivities,
    ReplaceActivity,
    ReplanChoice,
    ReplanCommand,
    ReplanStatus,
)


def create_replan_router(
    planning_jobs: PlanningJobRepository,
    service: ReplanApplicationService | None,
) -> APIRouter:
    router = APIRouter(prefix="/api/trip-plans/{job_id}/replans", tags=["replans"])

    @router.post(
        "",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=ReplanResponse,
        responses={409: {"model": ApiErrorResponse}, 422: {"model": ApiErrorResponse}},
        summary="Create or reuse one local replan",
    )
    async def create_replan(
        job_id: str,
        request: ReplanRequest,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> ReplanResponse:
        identifier = _identifier(job_id, job=True)
        try:
            job = await planning_jobs.get(identifier)
            if isinstance(job.request, (TripPlanRequestV3, TripPlanRequestV4)) or (
                isinstance(job.request, TripPlanRequestV2) and job.request.day_count > 2
            ):
                raise replan_scope_not_supported_error()
            application = _require_service(service)
            result = await application.create(
                ReplanApplicationRequest(
                    identifier,
                    request.replan_request_id,
                    request.baseline_plan_id,
                    _command(request),
                ),
                defer_execution=True,
            )
            if result.replan.status is ReplanStatus.REJECTED:
                raise replan_scope_not_supported_error()
            projection = await _response(planning_jobs, result)
        except PlanningHttpError:
            raise
        except ReplanRepositoryError as error:
            raise replan_http_error(error) from None
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="get") from None
        except ReplanApplicationError as error:
            raise _application_error(error) from None
        except DomainInvariantError:
            raise input_invalid_error() from None
        except Exception:
            raise internal_error() from None
        response.headers["Location"] = (
            f"/api/trip-plans/{identifier}/replans/{projection.replan_id}"
        )
        if result.replan.status is ReplanStatus.REPLANNING:
            background_tasks.add_task(
                _execute_safely, application, identifier, result.replan.replan_id
            )
        return projection

    @router.get(
        "/{replan_id}",
        response_model=ReplanResponse,
        responses={404: {"model": ApiErrorResponse}, 500: {"model": ApiErrorResponse}},
        summary="Read one local replan",
    )
    async def get_replan(job_id: str, replan_id: str) -> ReplanResponse:
        application = _require_service(service)
        job_identifier = _identifier(job_id, job=True)
        replan_identifier = _identifier(replan_id, job=False)
        try:
            return await _response(
                planning_jobs,
                await application.get(job_identifier, replan_identifier),
            )
        except ReplanRepositoryError as error:
            raise replan_http_error(error) from None
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="get") from None
        except PlanningHttpError:
            raise
        except Exception:
            raise internal_error() from None

    @router.post(
        "/{replan_id}/decision",
        response_model=ReplanResponse,
        responses={404: {"model": ApiErrorResponse}, 409: {"model": ApiErrorResponse}},
        summary="Approve or cancel one pending replan",
    )
    async def decide_replan(
        job_id: str,
        replan_id: str,
        request: ReplanDecisionRequest,
        response: Response,
        background_tasks: BackgroundTasks,
    ) -> ReplanResponse:
        application = _require_service(service)
        job_identifier = _identifier(job_id, job=True)
        replan_identifier = _identifier(replan_id, job=False)
        try:
            current = await application.get(job_identifier, replan_identifier)
            result = await application.decide(
                job_identifier,
                replan_identifier,
                ReplanChoice(request.choice.value),
                expected_replan_version=current.replan.aggregate_version,
                defer_execution=True,
            )
            if result.replan.status is ReplanStatus.EXPIRED:
                raise confirmation_expired_error()
            projection = await _response(planning_jobs, result)
        except PlanningHttpError:
            raise
        except ReplanRepositoryError as error:
            raise replan_http_error(error) from None
        except PlanningJobRepositoryError as error:
            raise repository_http_error(error, operation="get") from None
        except ReplanApplicationError as error:
            raise _application_error(error) from None
        except Exception:
            raise internal_error() from None
        if result.replan.status is ReplanStatus.REPLANNING:
            response.status_code = status.HTTP_202_ACCEPTED
            background_tasks.add_task(
                _execute_safely, application, job_identifier, replan_identifier
            )
        else:
            response.status_code = status.HTTP_200_OK
        return projection

    return router


async def _execute_safely(service: ReplanApplicationService, job_id: UUID, replan_id: UUID) -> None:
    try:
        await service.execute(job_id, replan_id)
    except Exception:
        return


async def _response(
    planning_jobs: PlanningJobRepository,
    result: ReplanApplicationResult,
) -> ReplanResponse:
    replan = result.replan
    job_response = None
    if replan.status is ReplanStatus.COMPLETED:
        job = await planning_jobs.get(replan.job_id)
        if replan.result is None:
            raise ValueError("replan_result_missing")
        job_response = _job_response(
            replace(
                job,
                status=replan.result.status,
                retryable=replan.result.retryable,
                result=replan.result,
                updated_at=replan.updated_at,
            )
        )
    return _project(replan, job_response)


def _project(replan: ReplanRecord, result: object | None) -> ReplanResponse:
    from intelligent_travel_assistant.contracts import TripPlanResponse

    plan_result = result if isinstance(result, TripPlanResponse) else None
    impact = replan.impact
    decision = replan.decision
    change_set = replan.change_set
    return ReplanResponse(
        job_id=replan.job_id,
        replan_id=replan.replan_id,
        replan_request_id=replan.replan_request_id,
        trace_id=replan.trace_id,
        baseline_plan_id=replan.baseline_plan_id,
        operation=ReplanPublicOperation(replan.operation.value),
        status=ReplanPublicStatus(replan.status.value),
        impact=(
            ReplanImpactResponse(
                categories=tuple(value.value for value in impact.categories),
                direct_refs=impact.direct_refs,
                transitive_refs=impact.transitive_refs,
                affected_dates=impact.affected_dates,
                route_refs=impact.route_refs,
                budget_effect=None,
                source_actions=tuple(
                    ReplanSourceActionResponse(
                        source_id=value.source_id,
                        action=value.action.value,
                        freshness=DataFreshness(value.freshness.value),
                        reason=value.reason.value,
                    )
                    for value in impact.source_actions
                ),
                required_validations=impact.required_validations,
                confirmation_required=impact.confirmation_required,
            )
            if impact is not None
            else None
        ),
        confirmation_expires_at=replan.expires_at,
        decision=(
            ReplanDecisionResponse(
                decision_id=decision.decision_id,
                choice=(
                    ReplanPublicChoice(decision.choice.value)
                    if decision.choice is not None
                    else None
                ),
                decided_at=decision.decided_at,
            )
            if decision is not None
            else None
        ),
        result=plan_result,
        change_set=(
            ReplanChangeSetResponse(
                baseline_plan_id=change_set.baseline_plan_id,
                result_plan_id=change_set.result_plan_id,
                added_refs=change_set.added_refs,
                removed_refs=change_set.removed_refs,
                changed_refs=change_set.changed_refs,
                change_codes=change_set.change_codes,
            )
            if change_set is not None
            else None
        ),
        errors=_terminal_errors(replan),
        created_at=replan.created_at,
        updated_at=replan.updated_at,
    )


def _terminal_errors(replan: ReplanRecord) -> tuple[ApiError, ...]:
    mapping = {
        ReplanStatus.NEEDS_INPUT: ApiErrorCode.DATA_MISSING,
        ReplanStatus.CONFLICT: ApiErrorCode.CONSTRAINT_CONFLICT,
        ReplanStatus.FAILED: ApiErrorCode.INTERNAL_ERROR,
        ReplanStatus.REJECTED: ApiErrorCode.REPLAN_SCOPE_NOT_SUPPORTED,
        ReplanStatus.EXPIRED: ApiErrorCode.CONFIRMATION_EXPIRED,
    }
    code = mapping.get(replan.status)
    if code is None:
        return ()
    return (ApiError(code=code, message="The replan did not replace the current plan."),)


def _command(request: ReplanRequest) -> ReplanCommand:
    command = request.command
    if isinstance(command, ReplaceActivityCommand):
        return ReplaceActivity(
            command.target_activity_id,
            command.replacement_categories,
            command.reason_code,
        )
    if isinstance(command, DeleteActivityCommand):
        return DeleteActivity(command.target_activity_id, command.reason_code)
    if isinstance(command, AdjustActivityTimeCommand):
        return AdjustActivityTime(
            command.target_activity_id,
            command.start_time,
            command.end_time,
            command.reason_code,
        )
    if isinstance(command, ReorderActivitiesCommand):
        return ReorderActivities(
            command.local_date, command.ordered_activity_ids, command.reason_code
        )
    raise TypeError("replan_command_invalid")


def _identifier(raw: str, *, job: bool) -> UUID:
    try:
        return UUID(raw)
    except (AttributeError, TypeError, ValueError):
        if job:
            raise job_not_found_error() from None
        raise PlanningHttpError(
            404, ApiErrorCode.REPLAN_NOT_FOUND, "The replan resource was not found."
        ) from None


def _require_service(
    service: ReplanApplicationService | None,
) -> ReplanApplicationService:
    if service is None:
        raise internal_error()
    return service


def _application_error(error: ReplanApplicationError) -> PlanningHttpError:
    code = str(error)
    if code == "replan_not_allowed":
        return replan_not_allowed_error()
    if code == "replan_baseline_conflict":
        return PlanningHttpError(
            409, ApiErrorCode.VERSION_CONFLICT, "The replan baseline has changed."
        )
    return internal_error()
