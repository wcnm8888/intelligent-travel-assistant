"""Loopback-only multiday SQLite composition for F-004A browser verification."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from ipaddress import IPv4Address
from pathlib import Path

from fastapi import FastAPI

from intelligent_travel_assistant.adapters.fakes import SyntheticPlanningJobExecutor
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import PlanningJobResult
from intelligent_travel_assistant.bootstrap import (
    PlanningPersistence,
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
    build_planning_persistence,
)
from intelligent_travel_assistant.contracts import TripPlanResponseV2
from intelligent_travel_assistant.settings import Settings

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
_SCENARIOS = frozenset({"ready", "partial", "conflict", "needs_input", "failed"})
_DAY_COUNTS = frozenset({2, 3, 4, 5, 6, 7})


def _required_path() -> Path:
    raw = os.environ.get("ITA_BROWSER_SQLITE_PATH")
    if raw is None:
        raise RuntimeError("synthetic_browser_sqlite_path_required")
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError("synthetic_browser_sqlite_path_invalid")
    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if (
        resolved == temporary_root
        or not resolved.is_relative_to(temporary_root)
        or resolved.exists()
    ):
        raise RuntimeError("synthetic_browser_sqlite_path_unsafe")
    return resolved


def _configured_start() -> date:
    raw = os.environ.get("ITA_BROWSER_START_DATE")
    if raw is None:
        raise RuntimeError("synthetic_browser_start_date_required")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise RuntimeError("synthetic_browser_start_date_invalid") from None


def _configured_day_count() -> int:
    raw = os.environ.get("ITA_MULTIDAY_DAYS", "3")
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError("synthetic_browser_day_count_invalid") from None
    if value not in _DAY_COUNTS:
        raise RuntimeError("synthetic_browser_day_count_invalid")
    return value


def _load_result(scenario: str, start: date, day_count: int) -> PlanningJobResult:
    if scenario not in _SCENARIOS:
        raise RuntimeError("synthetic_browser_scenario_invalid")
    payload = copy.deepcopy(
        json.loads(
            (_FIXTURE_ROOT / f"synthetic_hangzhou_{scenario}.json").read_text(encoding="utf-8")
        )["response"]
    )
    if scenario == "conflict":
        conflict = payload
        payload = copy.deepcopy(
            json.loads(
                (_FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
            )["response"]
        )
        for field in (
            "status",
            "violations",
            "warnings",
            "uncertainties",
            "errors",
            "retryable",
        ):
            payload[field] = copy.deepcopy(conflict[field])
    end = start + timedelta(days=day_count - 1)
    payload["response_version"] = "2"
    payload["request_summary"]["request_version"] = "2"
    payload["request_summary"]["start_date"] = start.isoformat()
    payload["request_summary"]["end_date"] = end.isoformat()
    plan = payload["plan"]
    if plan is not None:
        plan["plan_format_version"] = "2"
        plan["start_date"] = start.isoformat()
        plan["end_date"] = end.isoformat()
        originals = plan["days"]
        days = []
        for offset in range(day_count):
            day = copy.deepcopy(originals[min(offset, 1)])
            local_date = start + timedelta(days=offset)
            day["local_date"] = local_date.isoformat()
            if day["weather"] is not None:
                day["weather"]["forecast_date"] = local_date.isoformat()
            days.append(day)
        plan["days"] = days
    response = TripPlanResponseV2.model_validate(payload)
    return PlanningJobResult(
        status=response.status,
        resolved_destination=response.resolved_destination,
        plan=response.plan,
        violations=response.violations,
        warnings=response.warnings,
        uncertainties=response.uncertainties,
        sources=response.sources,
        errors=response.errors,
        retryable=response.retryable,
    )


def create_browser_app() -> FastAPI:
    """Use only explicit synthetic data and an explicit temporary SQLite path."""

    scenario = os.environ.get("ITA_MULTIDAY_SCENARIO", "ready")
    start = _configured_start()
    day_count = _configured_day_count()
    settings = Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
            "sqlite_database_path": _required_path(),
        }
    )
    persistence = build_planning_persistence(settings)
    executor = SyntheticPlanningJobExecutor(
        persistence.repository,
        _load_result(scenario, start, day_count),
        wait_between_states=lambda: asyncio.sleep(0.05),
    )
    disabled = ProviderActivationState.DISABLED
    providers = ProviderAdapters(
        report=ProviderStartupReport(
            deepseek=disabled,
            amap=disabled,
            qweather=disabled,
        )
    )
    application = create_app(
        settings=settings,
        planning_job_repository=persistence.repository,
        planning_job_executor=executor,
        provider_adapters=providers,
    )
    application.state.planning_persistence = persistence
    application.state.sqlite_database = persistence.database

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        await persistence.start()
        try:
            yield
        finally:
            persistence.close()

    application.router.lifespan_context = lifespan
    return application


def persistence_for(application: FastAPI) -> PlanningPersistence:
    """Expose the test-owned lifecycle for narrow longitudinal assertions."""

    value = application.state.planning_persistence
    if not isinstance(value, PlanningPersistence):
        raise RuntimeError("synthetic_browser_persistence_invalid")
    return value
