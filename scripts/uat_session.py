"""Default-off UAT helpers; only the explicitly enabled CLI starts a server."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from intelligent_travel_assistant.settings import Settings

from intelligent_travel_assistant.application.services.provider_planning_jobs import (
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.services.provider_replan_planner import (
    ProviderReplanPlanner,
)
from intelligent_travel_assistant.application.services.provider_replanning import (
    ProviderNeutralReplanExecutor,
)
from intelligent_travel_assistant.application.tooling.governance import RunCallBudget
from intelligent_travel_assistant.application.tooling.resilience import ProviderRunSession


def attach_run_session(
    application: FastAPI,
    *,
    enabled: bool = False,
    budget: RunCallBudget | None = None,
    stop_on_failure: bool = False,
) -> ProviderRunSession:
    """Attach only to the verified default memory composition, before serving requests."""
    if not enabled:
        raise ValueError("uat_observation_not_enabled")
    planning = application.state.planning_job_executor
    executor = getattr(application.state.replan_application_service, "_executor", None)
    if not isinstance(executor, ProviderNeutralReplanExecutor):
        raise ValueError("uat_default_composition_required")
    planner = executor._planner
    if (
        not isinstance(planning, ProviderPlanningJobExecutor)
        or not isinstance(planner, ProviderReplanPlanner)
        or getattr(application.state.planning_storage_mode, "value", None) != "live_memory_only"
        or application.state.sqlite_database is not None
        or planning._attempt_runtime_factory is None
    ):
        raise ValueError("uat_default_memory_composition_required")
    if planning.run_session is not None or planner.run_session is not None:
        raise ValueError("uat_session_already_bound")
    session = ProviderRunSession(
        budget if budget is not None else RunCallBudget(clock=monotonic),
        stop_on_failure=stop_on_failure,
    )
    planning.run_session = session
    planner.run_session = session
    return session


def write_run_evidence(session: ProviderRunSession, destination: Path) -> None:
    """Only typed counters/IDs/status; no raw app, request, result or exception payloads."""
    path = _evidence_path(destination)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(session.snapshot(), stream, ensure_ascii=False, indent=2)


def _evidence_path(destination: Path) -> Path:
    root = Path(__file__).resolve().parents[1] / "output" / "diagnostics"
    path = destination.resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != ".json":
        raise ValueError("uat_owned_json_required")
    if path.exists():
        raise FileExistsError("uat_evidence_already_exists")
    return path


def install_uat_lifecycle(
    application: FastAPI,
    *,
    evidence: Path,
    enabled: bool = False,
    budget: RunCallBudget | None = None,
    drain_seconds: float = 10,
) -> ProviderRunSession:
    if not enabled:
        raise ValueError("uat_observation_not_enabled")
    if not 0 <= drain_seconds <= 10:
        raise ValueError("uat_drain_invalid")
    path = _evidence_path(evidence)
    started = _evidence_path(path.with_name(path.stem + ".started.json"))
    session = attach_run_session(application, enabled=True, budget=budget, stop_on_failure=True)
    previous = application.router.lifespan_context
    application.state.uat_session = session
    application.state.uat_on_stop = None
    application.state.uat_evidence_complete = False
    application.state.uat_lifecycle_complete = False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.uat_evidence_complete = False
        app.state.uat_lifecycle_complete = False
        # Exclusive start record prevents accidental reuse of this run's evidence.
        write_run_evidence(session, started)
        watcher: asyncio.Task[None] | None = None

        async def watch() -> None:
            try:
                await asyncio.wait_for(session.stopped_event.wait(), session.budget.remaining())
            except TimeoutError:
                session.budget.stop("deadline")
            await session.stop(drain_seconds)
            callback = app.state.uat_on_stop
            if callback is not None:
                callback()

        try:
            async with previous(app):
                watcher = asyncio.create_task(watch())
                try:
                    yield
                finally:
                    await session.stop(drain_seconds)
        finally:
            try:
                if watcher is not None:
                    watcher.cancel()
                    await asyncio.gather(watcher, return_exceptions=True)
                else:
                    await session.stop(drain_seconds)
            finally:
                write_run_evidence(session, path)
                app.state.uat_evidence_complete = True
        # Reached only after the wrapped lifespan and final evidence both succeed.
        app.state.uat_lifecycle_complete = True

    application.router.lifespan_context = lifespan
    return session


def create_uat_app(
    *,
    evidence: Path,
    enabled: bool = False,
    settings: Settings | None = None,
    budget: RunCallBudget | None = None,
) -> FastAPI:
    if not enabled:
        raise ValueError("uat_observation_not_enabled")
    _evidence_path(evidence)
    from intelligent_travel_assistant.app import create_app
    from intelligent_travel_assistant.settings import get_settings

    resolved = settings if settings is not None else get_settings()
    if resolved.sqlite_database_path is not None:
        raise ValueError("uat_memory_only_required")
    application = create_app(settings=resolved)
    install_uat_lifecycle(application, evidence=evidence, enabled=True, budget=budget)
    return application


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit single-process loopback UAT entry")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    if not args.enable:
        print("UAT disabled; no settings loaded and no service started.")
        return 0
    if args.evidence is None:
        parser.error("--enable requires --evidence")
    try:
        import uvicorn

        application = create_uat_app(evidence=args.evidence, enabled=True)
        server = uvicorn.Server(
            uvicorn.Config(
                application,
                host="127.0.0.1",
                port=18008,
                workers=1,
                access_log=False,
                log_level="critical",
                lifespan="on",
                timeout_graceful_shutdown=10,
            )
        )
        application.state.uat_on_stop = lambda: setattr(server, "should_exit", True)
        server.run()
        if (
            application.state.uat_session.last_drain_complete is True
            and application.state.uat_evidence_complete is True
            and application.state.uat_lifecycle_complete is True
            and not server.lifespan.startup_failed
            and not server.lifespan.shutdown_failed
            and not server.lifespan.error_occurred
        ):
            return 0
    except Exception:
        pass
    print("UAT stopped with an execution or evidence error; no payload is logged.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
