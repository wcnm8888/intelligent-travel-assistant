"""F-009 synthetic browser composition with a process-wide outbound socket gate."""

# Import safety must precede importing the module-level production app.
# ruff: noqa: E402
from __future__ import annotations

import os
import socket
from ipaddress import ip_address
from pathlib import Path
from typing import Any

os.environ["APP_ENV"] = "test"
for _name in (
    "DEEPSEEK_API_KEY",
    "AMAP_API_KEY",
    "QWEATHER_API_HOST",
    "QWEATHER_PROJECT_ID",
    "QWEATHER_CREDENTIAL_ID",
    "QWEATHER_PRIVATE_KEY_PATH",
    "SQLITE_DATABASE_PATH",
):
    os.environ.pop(_name, None)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from intelligent_travel_assistant.adapters.fakes import (
    SyntheticF009MapProvider,
    SyntheticF009NarrativeProvider,
    SyntheticF014AdvisorProvider,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.f009 import PreplanningService
from intelligent_travel_assistant.settings import Settings


def create_browser_app() -> FastAPI:
    """Serve the built UI and reject every non-loopback socket attempt."""

    original = socket.socket.connect

    def loopback_only(instance: Any, address: Any) -> None:
        if not isinstance(address, tuple) or not ip_address(address[0]).is_loopback:
            raise RuntimeError("f009_non_loopback_forbidden")
        original(instance, address)

    socket.socket.connect = loopback_only  # type: ignore[method-assign]
    application = create_app(
        settings=Settings.model_validate({"app_env": "test"}),
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=PreplanningService(
            SyntheticF009MapProvider(),
            narrative=SyntheticF009NarrativeProvider(),
            advisor=SyntheticF014AdvisorProvider(),
        ),
    )
    application.state.f009_external_calls = 0
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    application.mount(
        "/",
        StaticFiles(directory=frontend, html=True),
        name="f009_synthetic_frontend",
    )
    return application
