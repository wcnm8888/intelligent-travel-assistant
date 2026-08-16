"""Loopback-only deterministic app for F-003 browser verification."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, date, datetime, timedelta
from ipaddress import IPv4Address
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI

from intelligent_travel_assistant.adapters.fakes import SyntheticPlanningJobExecutor
from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
    InMemoryReplanRepository,
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
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
)
from intelligent_travel_assistant.bootstrap import (
    ProviderActivationState,
    ProviderAdapters,
    ProviderStartupReport,
)
from intelligent_travel_assistant.contracts import TripPlanResponse
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanChoice,
    ReplanCommand,
    ReplanStatus,
)
from intelligent_travel_assistant.settings import Settings

_FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
_RESULT_PLAN_ID = UUID("f7000000-0000-4000-8000-000000000010")
_NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)
_SCENARIOS = frozenset(
    {"completed", "failed", "conflict", "needs_input", "expired", "version_conflict"}
)


class _Clock:
    def __init__(self) -> None:
        self.now = _NOW

    def __call__(self) -> datetime:
        return self.now


class _BrowserReplanRepository(InMemoryReplanRepository):
    def __init__(self, scenario: str, clock: _Clock) -> None:
        super().__init__(clock=clock)
        self._scenario = scenario
        self._browser_clock = clock

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        if self._scenario == "version_conflict":
            raise ReplanRepositoryError(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
        if self._scenario == "expired":
            self._browser_clock.now = _NOW + timedelta(minutes=15)
        return await super().decide(
            job_id,
            replan_id,
            choice,
            expected_replan_version=expected_replan_version,
            expected_job_version=expected_job_version,
        )


def _ready_result() -> PlanningJobResult:
    payload = json.loads(
        (_FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    plan = response.plan
    browser_start_date = date.fromisoformat(
        os.environ.get("ITA_BROWSER_START_DATE", str(response.request_summary.start_date))
    )
    if plan is not None and browser_start_date != plan.start_date:
        days = tuple(
            day.model_copy(
                update={
                    "local_date": browser_start_date + timedelta(days=offset),
                    "weather": (
                        day.weather.model_copy(
                            update={"forecast_date": browser_start_date + timedelta(days=offset)}
                        )
                        if day.weather is not None
                        else None
                    ),
                }
            )
            for offset, day in enumerate(plan.days)
        )
        plan = plan.model_copy(
            update={
                "start_date": browser_start_date,
                "end_date": browser_start_date + timedelta(days=1),
                "days": days,
            }
        )
    return PlanningJobResult(
        response.status,
        response.resolved_destination,
        plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        response.retryable,
    )


class _BrowserReplanExecutor:
    def __init__(self, scenario: str) -> None:
        self._scenario = scenario

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        assert isinstance(command, AdjustActivityTime)
        target = command.target_activity_id
        return ImpactAnalysis(
            (ImpactCategory.SOURCE_REFRESH,),
            ImpactDisposition.CONFIRM,
            (target,),
            (),
            (),
            (),
            (),
            ("schedule", "source"),
            True,
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        if self._scenario in {"failed", "conflict", "needs_input"}:
            status = ReplanStatus(self._scenario)
            return ReplanExecutionResult(outcome=ReplanOutcome(status, f"offline_{self._scenario}"))
        assert job.result is not None and job.result.plan is not None
        changed = _ready_result()
        assert changed.plan is not None
        changed = PlanningJobResult(
            changed.status,
            changed.resolved_destination,
            changed.plan.model_copy(update={"plan_id": _RESULT_PLAN_ID}),
            changed.violations,
            changed.warnings,
            changed.uncertainties,
            changed.sources,
            changed.errors,
            changed.retryable,
        )
        assert isinstance(replan.command, AdjustActivityTime)
        target = replan.command.target_activity_id
        return ReplanExecutionResult(
            commit=ReplanCommit(
                changed,
                PlanChangeSet(
                    baseline_plan_id=job.result.plan.plan_id,
                    result_plan_id=_RESULT_PLAN_ID,
                    added_refs=(),
                    removed_refs=(),
                    changed_refs=(target,),
                    added_origins=(),
                    change_codes=("schedule",),
                ),
            )
        )


def create_browser_app() -> FastAPI:
    scenario = os.environ.get("ITA_REPLAN_SCENARIO", "completed")
    if scenario not in _SCENARIOS:
        raise RuntimeError("synthetic_replan_scenario_invalid")
    planning = InMemoryPlanningJobRepository()
    planning_executor = SyntheticPlanningJobExecutor(
        planning,
        _ready_result(),
        wait_between_states=lambda: asyncio.sleep(0.05),
    )
    clock = _Clock()
    replans = _BrowserReplanRepository(scenario, clock)
    service = ReplanApplicationService(planning, replans, _BrowserReplanExecutor(scenario))
    disabled = ProviderActivationState.DISABLED
    providers = ProviderAdapters(
        report=ProviderStartupReport(deepseek=disabled, amap=disabled, qweather=disabled)
    )
    settings = Settings.model_validate(
        {
            "app_env": "test",
            "api_host": IPv4Address("127.0.0.1"),
            "api_port": 8000,
        }
    )
    return create_app(
        settings=settings,
        planning_job_repository=planning,
        planning_job_executor=planning_executor,
        provider_adapters=providers,
        replan_application_service=service,
    )


app = create_browser_app()
