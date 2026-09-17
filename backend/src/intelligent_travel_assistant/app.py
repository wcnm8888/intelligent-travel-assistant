"""FastAPI application, persistence lifespan, and health contract."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic
from typing import Final, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from intelligent_travel_assistant.adapters.providers import (
    F009AmapProvider,
    F009DeepSeekNarrativeProvider,
    F014DeepSeekAdvisorProvider,
)
from intelligent_travel_assistant.api import (
    PlanningHttpError,
    create_preplanning_router,
    create_replan_router,
    create_trip_plan_router,
    error_response,
    input_invalid_error,
)
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
from intelligent_travel_assistant.application.f009 import (
    PreplanningService,
    UnavailableF009MapProvider,
)
from intelligent_travel_assistant.application.replanning import ReplanApplicationService
from intelligent_travel_assistant.application.repositories import PlanningJobRepository
from intelligent_travel_assistant.bootstrap import (
    ApplicationServices,
    PlanningPersistence,
    ProviderAdapters,
    build_application_services,
    build_planning_job_executor,
    build_planning_persistence,
    build_provider_adapters,
    require_live_memory_repository,
)
from intelligent_travel_assistant.settings import Settings, get_settings

SERVICE_NAME: Final = "intelligent-travel-assistant-api"


class HealthResponse(BaseModel):
    """Stable response returned by the local health endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    service: Literal["intelligent-travel-assistant-api"] = SERVICE_NAME


def create_app(
    settings: Settings | None = None,
    planning_job_repository: PlanningJobRepository | None = None,
    provider_adapters: ProviderAdapters | None = None,
    planning_job_executor: PlanningJobExecutor | None = None,
    replan_application_service: ReplanApplicationService | None = None,
    preplanning_service: PreplanningService | None = None,
) -> FastAPI:
    """Create an application instance without requiring third-party credentials."""

    resolved_settings = settings or get_settings()
    resolved_adapters = (
        provider_adapters
        if provider_adapters is not None
        else build_provider_adapters(resolved_settings)
    )
    persistence: PlanningPersistence | None = None
    if planning_job_repository is None:
        persistence = build_planning_persistence(resolved_settings, resolved_adapters)
        repository = persistence.repository
    else:
        repository = planning_job_repository
        require_live_memory_repository(repository, resolved_adapters)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        if persistence is not None:
            await persistence.start()
        try:
            yield
        finally:
            if persistence is not None:
                persistence.close()

    application = FastAPI(
        title="Intelligent Travel Assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.planning_persistence = persistence
    application.state.sqlite_database = persistence.database if persistence is not None else None
    application.state.planning_storage_mode = (
        persistence.storage_mode if persistence is not None else None
    )
    application.state.replan_repository = (
        persistence.replan_repository if persistence is not None else None
    )
    application.state.provider_adapters = resolved_adapters
    application.state.planning_job_repository = repository
    default_services: ApplicationServices | None = None
    if (
        persistence is not None
        and planning_job_executor is None
        and replan_application_service is None
    ):
        default_services = build_application_services(persistence, resolved_adapters)
    if planning_job_executor is not None:
        executor = planning_job_executor
    elif default_services is not None:
        executor = default_services.planning_job_executor
    elif planning_job_repository is None:
        executor = build_planning_job_executor(repository, resolved_adapters)
    else:
        executor = None
    application.state.planning_job_executor = executor
    resolved_replan_application_service = (
        default_services.replan_application_service
        if default_services is not None
        else replan_application_service
    )
    application.state.replan_application_service = resolved_replan_application_service
    application.state.route_attempt_limiter = (
        default_services.route_attempt_limiter if default_services is not None else None
    )
    if preplanning_service is not None:
        resolved_preplanning_service = preplanning_service
    elif resolved_adapters.amap is not None:
        resolved_preplanning_service = PreplanningService(
            F009AmapProvider(resolved_adapters.amap),
            narrative=(
                F009DeepSeekNarrativeProvider(resolved_adapters.deepseek)
                if resolved_adapters.deepseek is not None
                else None
            ),
            advisor=(
                F014DeepSeekAdvisorProvider(resolved_adapters.deepseek)
                if resolved_adapters.deepseek is not None
                else None
            ),
            route_limiter=application.state.route_attempt_limiter,
            monotonic_clock=(
                monotonic if application.state.route_attempt_limiter is not None else None
            ),
        )
    else:
        resolved_preplanning_service = PreplanningService(UnavailableF009MapProvider())
    application.state.preplanning_service = resolved_preplanning_service

    @application.exception_handler(PlanningHttpError)
    async def handle_planning_http_error(
        _request: Request,
        error: PlanningHttpError,
    ) -> JSONResponse:
        return error_response(error)

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return error_response(input_invalid_error())

    @application.get(
        "/api/health",
        response_model=HealthResponse,
        response_model_exclude_none=True,
        tags=["health"],
        summary="Check local API health",
    )
    def health() -> HealthResponse:
        return HealthResponse()

    application.include_router(
        create_trip_plan_router(repository, executor, resolved_preplanning_service)
    )
    application.include_router(create_preplanning_router(resolved_preplanning_service))
    application.include_router(
        create_replan_router(
            repository,
            resolved_replan_application_service,
            resolved_preplanning_service,
        )
    )
    return application


app = create_app()
