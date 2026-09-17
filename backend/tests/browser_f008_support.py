"""F-008 synthetic-only dual-mode browser composition; never a production runner."""

# Import safety must precede importing the module-level production app.
# ruff: noqa: E402
from __future__ import annotations

import asyncio
import json
import os
import socket
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from ipaddress import ip_address
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

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
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
    FakeQWeatherAdapter,
    SyntheticPlanningJobExecutor,
)
from intelligent_travel_assistant.adapters.persistence import SqliteReplanRepository
from intelligent_travel_assistant.adapters.providers import (
    AmapAdapter,
    DeepSeekAdapter,
    QWeatherAdapter,
)
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationService,
    ReplanExecutionResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
    build_planning_persistence,
)
from intelligent_travel_assistant.contracts import TripPlanResponse
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanCommand,
    ReplanStatus,
)
from intelligent_travel_assistant.settings import Settings

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_OUTCOMES = {
    "needs_input": (ReplanStatus.NEEDS_INPUT, "replacement_input_required"),
    "conflict": (ReplanStatus.CONFLICT, "replan_job_version_conflict"),
    "stop": (ReplanStatus.FAILED, "provider_unauthorized"),
}


def request_payload(start: date) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (_FIXTURES / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    payload["start_date"] = start.isoformat()
    payload["client_request_id"] = str(uuid4())
    return payload


def _result(start: date) -> PlanningJobResult:
    payload = json.loads((_FIXTURES / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8"))[
        "response"
    ]
    end = start + timedelta(days=1)
    for section in (payload["plan"], payload["request_summary"]):
        section.update(start_date=start.isoformat(), end_date=end.isoformat())
    for index, day in enumerate(payload["plan"]["days"]):
        day["local_date"] = (start + timedelta(days=index)).isoformat()
        if day["weather"]:
            day["weather"]["forecast_date"] = day["local_date"]
    response = TripPlanResponse.model_validate(payload)
    return PlanningJobResult(
        response.status,
        response.resolved_destination,
        response.plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
    )


class BrowserReplanExecutor:
    """Real application/commit, deterministic synthetic outcomes and actual time edit."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.execution_calls = 0

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        assert isinstance(command, AdjustActivityTime)
        return ImpactAnalysis(
            (ImpactCategory.SOURCE_REFRESH,),
            ImpactDisposition.CONFIRM,
            (command.target_activity_id,),
            (),
            (),
            (),
            (),
            ("schedule",),
            True,
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        self.execution_calls += 1
        if self.scenario in _OUTCOMES:
            status, code = _OUTCOMES[self.scenario]
            return ReplanExecutionResult(outcome=ReplanOutcome(status, code))
        if self.scenario == "recovery" and self.execution_calls == 1:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "provider_timeout")
            )
        assert job.result is not None and job.result.plan is not None
        assert isinstance(job.result, PlanningJobResult)
        command = replan.command
        assert isinstance(command, AdjustActivityTime)
        old_plan = job.result.plan
        days = tuple(
            day.model_copy(
                update={
                    "activities": tuple(
                        activity.model_copy(
                            update={"start_time": command.start_time, "end_time": command.end_time}
                        )
                        if activity.item_id == command.target_activity_id
                        else activity
                        for activity in day.activities
                    )
                }
            )
            for day in old_plan.days
        )
        plan = old_plan.model_copy(update={"plan_id": uuid4(), "days": days})
        result = PlanningJobResult(
            job.result.status,
            job.result.resolved_destination,
            plan,
            job.result.violations,
            job.result.warnings,
            job.result.uncertainties,
            job.result.sources,
            job.result.errors,
            job.result.retryable,
        )
        changes = PlanChangeSet(
            old_plan.plan_id,
            plan.plan_id,
            (),
            (),
            (command.target_activity_id,),
            (),
            ("schedule_changed",),
        )
        return ReplanExecutionResult(commit=ReplanCommit(result, changes))


def create_f008_app(
    mode: str,
    start: date,
    database_path: Path,
    *,
    scenario: str = "recovery",
    allow_reopen: bool = False,
) -> FastAPI:
    if mode not in {"memory", "sqlite"} or scenario not in {"recovery", "completed", *_OUTCOMES}:
        raise RuntimeError("f008_synthetic_mode_invalid")
    path = database_path.resolve()
    if not path.is_relative_to(
        Path(tempfile.gettempdir()).resolve()
    ) or not path.parent.name.startswith("f008-step12-"):
        raise RuntimeError("f008_temporary_path_required")
    if path.name != "offline.sqlite3" or (path.exists() and not allow_reopen):
        raise RuntimeError("f008_unowned_database_rejected")
    state = ProviderActivationState.READY if mode == "memory" else ProviderActivationState.DISABLED
    adapters = ProviderAdapters(
        ProviderStartupReport(state, state, state),
        cast(DeepSeekAdapter, FakeDeepSeekAdapter()) if mode == "memory" else None,
        cast(AmapAdapter, FakeAmapAdapter()) if mode == "memory" else None,
        cast(QWeatherAdapter, FakeQWeatherAdapter()) if mode == "memory" else None,
    )
    assert Settings.model_config.get("env_file") is None
    settings = Settings.model_validate({"app_env": "test", "sqlite_database_path": path})
    persistence = build_planning_persistence(settings, adapters)
    replans = persistence.replan_repository
    if mode == "sqlite":
        assert persistence.database is not None
        replans = SqliteReplanRepository(persistence.database)
    assert replans is not None
    executor = BrowserReplanExecutor(scenario)
    app = create_app(
        settings=settings,
        planning_job_repository=persistence.repository,
        provider_adapters=adapters,
        planning_job_executor=SyntheticPlanningJobExecutor(
            persistence.repository, _result(start), wait_between_states=lambda: asyncio.sleep(0.01)
        ),
        replan_application_service=ReplanApplicationService(
            persistence.repository, replans, executor
        ),
    )
    app.state.planning_persistence = persistence
    app.state.planning_storage_mode = persistence.storage_mode
    app.state.replan_repository = replans
    app.state.f008_executor = executor
    app.state.f008_sqlite_attempts = 0

    def forbidden_sqlite(*args: object, **kwargs: object) -> None:
        app.state.f008_sqlite_attempts += 1
        raise AssertionError("f008_live_sqlite_forbidden")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if mode == "memory":
            with patch("sqlite3.connect", forbidden_sqlite):
                await persistence.start()
                try:
                    yield
                finally:
                    persistence.close()
        else:
            await persistence.start()
            try:
                yield
            finally:
                persistence.close()

    app.router.lifespan_context = lifespan
    return app


def create_browser_app() -> FastAPI:
    """CLI-only factory; block outbound sockets and serve the exact built frontend."""
    original = socket.socket.connect

    def loopback_only(instance: Any, address: Any) -> None:
        if not isinstance(address, tuple) or not ip_address(address[0]).is_loopback:
            raise RuntimeError("f008_non_loopback_forbidden")
        original(instance, address)

    socket.socket.connect = loopback_only  # type: ignore[method-assign]
    app = create_f008_app(
        os.environ["F008_MODE"],
        date.fromisoformat(os.environ["F008_START"]),
        Path(os.environ["F008_DATABASE"]),
        scenario=os.environ.get("F008_SCENARIO", "recovery"),
        allow_reopen=os.environ.get("F008_REOPEN") == "1",
    )
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    app.mount("/", StaticFiles(directory=frontend, html=True), name="synthetic_frontend")
    return app
