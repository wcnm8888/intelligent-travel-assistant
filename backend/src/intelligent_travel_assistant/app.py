"""FastAPI application and health contract."""

from typing import Final, Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from intelligent_travel_assistant.settings import Settings, get_settings

SERVICE_NAME: Final = "intelligent-travel-assistant-api"


class HealthResponse(BaseModel):
    """Stable response returned by the local health endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"] = "ok"
    service: Literal["intelligent-travel-assistant-api"] = SERVICE_NAME


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application instance without requiring third-party credentials."""

    resolved_settings = settings or get_settings()
    application = FastAPI(
        title="Intelligent Travel Assistant API",
        version="0.1.0",
    )
    application.state.settings = resolved_settings

    @application.get(
        "/api/health",
        response_model=HealthResponse,
        response_model_exclude_none=True,
        tags=["health"],
        summary="Check local API health",
    )
    def health() -> HealthResponse:
        return HealthResponse()

    return application


app = create_app()
