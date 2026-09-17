"""F-010 offline browser composition; every fact is synthetic and loopback-only."""

# Import safety must precede importing the module-level production app.
# ruff: noqa: E402
from __future__ import annotations

import os
import socket
from datetime import timedelta
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from uuid import UUID

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
    SyntheticF014AdvisorProvider,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.f009 import (
    F009Narrative,
    F009NarrativeDay,
    F009NarrativeRequest,
    F009ProviderOutcome,
    PreplanningService,
)
from intelligent_travel_assistant.settings import Settings

_EXTRA_LOCATION_ID = UUID("91000000-0000-4000-8000-999999999999")


class InvalidSyntheticNarrativeProvider:
    """Attempts a forbidden identity/date mutation on both bounded calls."""

    def __init__(self, mode: str) -> None:
        self._mode = mode
        self._calls = 0

    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self._calls += 1
        if self._mode == "retry" and self._calls % 3 == 0:
            return self._valid_outcome(request)
        return self._outcome(request)

    async def repair(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self._calls += 1
        return self._outcome(request)

    @staticmethod
    def _valid_outcome(
        request: F009NarrativeRequest,
    ) -> F009ProviderOutcome[F009Narrative]:
        return F009ProviderOutcome(
            F009Narrative(
                days=tuple(
                    F009NarrativeDay(
                        local_date=local_date,
                        location_ids=tuple(item[0] for item in locations),
                        pace_note="按已冻结顺序从容游览（synthetic）。",
                        stop_narratives=tuple("保留充足游览时间（synthetic）。" for _ in locations),
                        rationale="说明只解释确定性安排（synthetic）。",
                    )
                    for local_date, locations in request.days
                )
            )
        )

    def _outcome(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        days = []
        for index, (local_date, locations) in enumerate(request.days):
            ids = tuple(item[0] for item in locations)
            if self._mode in {"extra", "retry"} and index == 0:
                ids = (*ids, _EXTRA_LOCATION_ID)
            elif self._mode == "order" and index == 0:
                ids = tuple(reversed(ids))
                local_date += timedelta(days=1)
            days.append(
                F009NarrativeDay(
                    local_date=local_date,
                    location_ids=ids,
                    pace_note="该说明应被拒绝（synthetic）。",
                    stop_narratives=tuple("synthetic" for _ in ids),
                    rationale="该说明尝试改变冻结日程（synthetic）。",
                )
            )
        return F009ProviderOutcome(F009Narrative(days=tuple(days)))


def create_browser_app() -> FastAPI:
    """Serve built UI while blocking every non-loopback socket attempt."""

    original = socket.socket.connect

    def loopback_only(instance: Any, address: Any) -> None:
        if not isinstance(address, tuple) or not ip_address(address[0]).is_loopback:
            raise RuntimeError("f010_non_loopback_forbidden")
        original(instance, address)

    socket.socket.connect = loopback_only  # type: ignore[method-assign]
    narrative_mode = os.environ.get("F010_SYNTHETIC_NARRATIVE_MODE", "extra")
    if narrative_mode not in {"extra", "order", "retry"}:
        raise RuntimeError("f010_synthetic_narrative_mode_invalid")
    application = create_app(
        settings=Settings.model_validate({"app_env": "test"}),
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=PreplanningService(
            SyntheticF009MapProvider(),
            narrative=InvalidSyntheticNarrativeProvider(narrative_mode),
            advisor=SyntheticF014AdvisorProvider(),
        ),
    )
    application.state.f010_external_calls = 0
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    application.mount(
        "/",
        StaticFiles(directory=frontend, html=True),
        name="f010_synthetic_frontend",
    )
    return application
