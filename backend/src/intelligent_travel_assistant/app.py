"""FastAPI application, persistence lifespan, and health contract."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from intelligent_travel_assistant.api import (
    PlanningHttpError,
    create_trip_plan_router,
    error_response,
    input_invalid_error,
)
from intelligent_travel_assistant.application.execution import PlanningJobExecutor
from intelligent_travel_assistant.application.repositories import PlanningJobRepository
from intelligent_travel_assistant.bootstrap import (
    PlanningPersistence,
    ProviderAdapters,
    build_planning_job_executor,
    build_planning_persistence,
    build_provider_adapters,
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
) -> FastAPI:
    """Create an application instance without requiring third-party credentials."""

    resolved_settings = settings or get_settings()
    persistence: PlanningPersistence | None = None
    if planning_job_repository is None:
        persistence = build_planning_persistence(resolved_settings)
        repository = persistence.repository
    else:
        repository = planning_job_repository

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
    resolved_adapters = (
        provider_adapters
        if provider_adapters is not None
        else build_provider_adapters(resolved_settings)
    )
    application.state.provider_adapters = resolved_adapters
    application.state.planning_job_repository = repository
    executor = (
        planning_job_executor
        if planning_job_executor is not None
        else build_planning_job_executor(repository, resolved_adapters)
    )
    application.state.planning_job_executor = executor

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

    application.include_router(create_trip_plan_router(repository, executor))
    return application


app = create_app()
