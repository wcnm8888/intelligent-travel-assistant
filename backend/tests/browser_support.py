"""Local-only FastAPI composition used by Step 35 browser verification."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI

from intelligent_travel_assistant.adapters.fakes import SyntheticPlanningJobExecutor
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.repositories import PlanningJobResult
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
)
from intelligent_travel_assistant.contracts import TripPlanResponse

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
_SCENARIOS = frozenset({"ready", "partial", "conflict", "needs_input", "failed"})


def _load_result(scenario: str) -> PlanningJobResult:
    if scenario not in _SCENARIOS:
        raise RuntimeError("synthetic_browser_scenario_invalid")
    payload = json.loads(
        (_FIXTURE_ROOT / f"synthetic_hangzhou_{scenario}.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
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
    """Compose real routes/repository with a visibly synthetic terminal publisher."""

    scenario = os.environ.get("ITA_SYNTHETIC_SCENARIO", "ready")
    repository = InMemoryPlanningJobRepository()
    executor = SyntheticPlanningJobExecutor(
        repository,
        _load_result(scenario),
        wait_between_states=lambda: asyncio.sleep(2.25),
    )
    disabled = ProviderActivationState.DISABLED
    providers = ProviderAdapters(
        report=ProviderStartupReport(
            deepseek=disabled,
            amap=disabled,
            qweather=disabled,
        )
    )
    return create_app(
        planning_job_repository=repository,
        planning_job_executor=executor,
        provider_adapters=providers,
    )


app = create_browser_app()
