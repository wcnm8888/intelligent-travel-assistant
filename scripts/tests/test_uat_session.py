"""UAT support remains default-off and writes only new owned evidence."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from time import monotonic

from fastapi import FastAPI

from intelligent_travel_assistant.application.tooling.governance import RunCallBudget
from intelligent_travel_assistant.application.tooling.resilience import ProviderRunSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uat_session import (  # noqa: E402
    attach_run_session,
    create_uat_app,
    install_uat_lifecycle,
    main,
    write_run_evidence,
)


class UatSupportTests(unittest.TestCase):
    def test_disabled_has_no_composition_side_effect(self) -> None:
        app = FastAPI()
        with self.assertRaisesRegex(ValueError, "not_enabled"):
            attach_run_session(app)
        self.assertFalse(hasattr(app.state, "planning_job_executor"))

    def test_evidence_rejects_unowned_path(self) -> None:
        session = ProviderRunSession(RunCallBudget(clock=monotonic))
        with self.assertRaisesRegex(ValueError, "owned_json"):
            write_run_evidence(session, Path(tempfile.gettempdir()) / "outside-uat.json")

    def test_evidence_is_new_file_and_contains_only_snapshot(self) -> None:
        root = Path(__file__).resolve().parents[2] / "output" / "diagnostics"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="uat-output-", dir=root))
        session = ProviderRunSession(RunCallBudget(clock=monotonic))
        target = folder / "counts.json"
        write_run_evidence(session, target)
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            write_run_evidence(session, target)
        self.assertEqual(target.read_bytes(), original)


class UatLifecycleTests(unittest.TestCase):
    def test_cli_exit_reflects_actual_lifespan_and_final_evidence(self) -> None:
        for mode in ("success", "partial_write", "collision", "startup_error", "shutdown_error"):
            with self.subTest(mode=mode):
                self._assert_cli_exit(mode)

    def _assert_cli_exit(self, mode: str) -> None:
        import asyncio
        import io
        from collections.abc import AsyncIterator
        from contextlib import asynccontextmanager, redirect_stdout
        from unittest.mock import patch

        from tests.browser_f008_production_support import create_production_app
        from uvicorn import Server
        from uvicorn.lifespan.on import LifespanOn

        output = Path(__file__).resolve().parents[2] / "output" / "diagnostics"
        output.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="uat-cli-exit-", dir=output))
        target = folder / "final.json"
        app = create_production_app(Path(tempfile.mkdtemp(prefix="uat-synthetic-")))
        previous = app.router.lifespan_context

        @asynccontextmanager
        async def original_lifespan(application: FastAPI) -> AsyncIterator[None]:
            if mode == "startup_error":
                raise RuntimeError("synthetic-private-marker")
            async with previous(application):
                yield
            if mode == "shutdown_error":
                raise RuntimeError("synthetic-private-marker")

        app.router.lifespan_context = original_lifespan
        session = install_uat_lifecycle(app, enabled=True, evidence=target)

        def writer(value: ProviderRunSession, destination: Path) -> None:
            if destination == target and mode in ("partial_write", "collision"):
                with target.open("x", encoding="utf-8") as stream:
                    stream.write('{"partial":' if mode == "partial_write" else "old-record")
                if mode == "partial_write":
                    raise OSError("synthetic-private-marker")
            write_run_evidence(value, destination)

        def protocol_only(server: Server) -> None:
            async def run() -> None:
                lifecycle = LifespanOn(server.config)
                server.lifespan = lifecycle
                await lifecycle.startup()
                await lifecycle.shutdown()
                self.assertEqual(lifecycle.startup_failed, mode == "startup_error")
                self.assertEqual(
                    lifecycle.shutdown_failed,
                    mode in ("partial_write", "collision", "shutdown_error"),
                )

            asyncio.run(run())

        captured = io.StringIO()
        with (
            patch("uat_session.create_uat_app", return_value=app),
            patch("uat_session.write_run_evidence", side_effect=writer),
            patch("uvicorn.Server.run", autospec=True, side_effect=protocol_only),
            patch(
                "asyncio.BaseEventLoop.create_server",
                side_effect=AssertionError("no service listener"),
            ) as listener,
            redirect_stdout(captured),
        ):
            code = main(["--enable", "--evidence", str(target)])
        listener.assert_not_called()
        self.assertTrue(session.last_drain_complete)
        self.assertEqual(len(app.state.r5_transport.calls), 0)
        self.assertNotIn("synthetic-private-marker", captured.getvalue())
        if mode == "collision":
            self.assertEqual(target.read_text(encoding="utf-8"), "old-record")
        self.assertEqual(code, 0 if mode == "success" else 2)
        if mode != "success":
            self.assertIn("UAT stopped", captured.getvalue())

    def test_default_factory_and_cli_never_start(self) -> None:
        from unittest.mock import patch

        with patch("uvicorn.Server") as server:
            self.assertEqual(main([]), 0)
            with self.assertRaisesRegex(ValueError, "not_enabled"):
                create_uat_app(evidence=Path("unused.json"))
            server.assert_not_called()

    def test_actual_factory_stops_on_business_failure_and_exports_on_exit(self) -> None:
        import json

        import httpx2
        from fastapi.testclient import TestClient
        from tests.api.test_production_replans_api import (
            _approve_and_read,
            _command,
            _create_plan,
            _create_replan,
        )
        from tests.browser_f008_production_support import create_production_app

        output = Path(__file__).resolve().parents[2] / "output" / "diagnostics"
        folder = Path(tempfile.mkdtemp(prefix="uat-lifecycle-", dir=output))
        fixture = Path(tempfile.mkdtemp(prefix="uat-synthetic-"))
        reference = create_production_app(fixture)
        target = folder / "final.json"
        app = create_uat_app(enabled=True, evidence=target, settings=reference.state.settings)
        transport = reference.state.r5_transport
        mock = httpx2.MockTransport(transport)
        adapters = app.state.provider_adapters
        for adapter in (adapters.amap, adapters.qweather, adapters.deepseek):
            adapter._transport = mock
        self.assertEqual(set(app.openapi()["paths"]), set(reference.openapi()["paths"]))
        with TestClient(app) as client:
            url, original = _create_plan(client)
            transport.fail_next_amap_attempts()
            _, pending = _create_replan(
                client, url, original, _command(original["plan"], "replace_activity")
            )
            self.assertEqual(_approve_and_read(client, url, pending)["status"], "failed")
            self.assertEqual(client.get(url).json()["plan"], original["plan"])
            self.assertTrue(app.state.uat_session.snapshot()["stopped"])
            self.assertEqual(app.state.uat_session.snapshot()["reason"], "business_failure")
            calls = len(transport.calls)
            _, pending = _create_replan(
                client, url, original, _command(original["plan"], "delete_activity")
            )
            self.assertNotEqual(_approve_and_read(client, url, pending)["status"], "completed")
            self.assertEqual(len(transport.calls), calls)
        result = json.loads(target.read_text(encoding="utf-8"))
        self.assertTrue(result["drain_complete"])
        self.assertEqual(result["active_executions"], 0)
        self.assertTrue((folder / "final.started.json").is_file())
        text = target.read_text(encoding="utf-8")
        for forbidden in ("r5-synthetic", "coordinates", "api_key", "https://", "合成"):
            self.assertNotIn(forbidden, text)

    def test_failed_startup_still_leaves_terminal_evidence(self) -> None:
        import json
        from collections.abc import AsyncIterator
        from contextlib import asynccontextmanager

        from fastapi.testclient import TestClient
        from tests.browser_f008_production_support import create_production_app

        output = Path(__file__).resolve().parents[2] / "output" / "diagnostics"
        folder = Path(tempfile.mkdtemp(prefix="uat-startup-", dir=output))
        app = create_production_app(Path(tempfile.mkdtemp(prefix="uat-synthetic-")))

        @asynccontextmanager
        async def failed(_app: FastAPI) -> AsyncIterator[None]:
            raise RuntimeError("synthetic startup failure")
            yield

        app.router.lifespan_context = failed
        target = folder / "final.json"
        install_uat_lifecycle(app, enabled=True, evidence=target)
        with self.assertRaisesRegex(RuntimeError, "synthetic startup failure"):
            with TestClient(app):
                self.fail("startup unexpectedly succeeded")
        result = json.loads(target.read_text(encoding="utf-8"))
        self.assertTrue(result["stopped"] and result["drain_complete"])
        self.assertEqual(len(app.state.r5_transport.calls), 0)

    def test_deadline_watch_requests_server_exit_without_http(self) -> None:
        import asyncio
        import json

        from tests.browser_f008_production_support import create_production_app

        output = Path(__file__).resolve().parents[2] / "output" / "diagnostics"
        folder = Path(tempfile.mkdtemp(prefix="uat-idle-deadline-", dir=output))
        app = create_production_app(Path(tempfile.mkdtemp(prefix="uat-synthetic-")))
        target = folder / "final.json"
        install_uat_lifecycle(
            app,
            enabled=True,
            evidence=target,
            budget=RunCallBudget(clock=monotonic, deadline_seconds=0.02),
        )

        async def scenario() -> None:
            exited = asyncio.Event()
            app.state.uat_on_stop = exited.set
            async with app.router.lifespan_context(app):
                await asyncio.wait_for(exited.wait(), 2)

        asyncio.run(scenario())
        result = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(result["reason"], "deadline")
        self.assertTrue(result["drain_complete"])
        self.assertEqual(len(app.state.r5_transport.calls), 0)
