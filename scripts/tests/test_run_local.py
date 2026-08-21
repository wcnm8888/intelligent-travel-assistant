"""Offline contract tests for the owned-process local runner."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "scripts" / "run-local.ps1"


class LocalRunnerContractTest(unittest.TestCase):
    def test_runner_has_fixed_offline_loopback_contract(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")

        for required in (
            '"3.13.3"',
            '"22.16.0"',
            '"11.19.0"',
            '"http://127.0.0.1:8000/api/health"',
            '"http://127.0.0.1:5173/"',
            '$env:COREPACK_ENABLE_NETWORK = "0"',
            '$env:UV_OFFLINE = "1"',
            '"--strictPort"',
        ):
            self.assertIn(required, text)

        lowered = text.lower()
        for forbidden in (
            ".env.local",
            "taskkill",
            "stop-computer",
            "remove-item",
            "get-process",
            "start-job",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_runner_uses_exact_owned_process_objects(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")

        self.assertIn("Start-Process", text)
        self.assertIn("[System.Diagnostics.Process]$Process", text)
        self.assertIn("Stop-Process -Id $Process.Id", text)
        self.assertIn("$Process.WaitForExit", text)
        self.assertNotIn("Stop-Process -Name", text)
        self.assertIn("Get-SafeFailureMessage $_.Exception.Message", text)
        self.assertNotIn("Write-Error $_.Exception.Message", text)

    def test_runner_self_test_covers_versions_ports_health_and_cleanup(self) -> None:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUNNER),
                "-ContractSelfTest",
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Local runner contract self-test passed.")

    def test_runner_preflight_uses_installed_offline_runtimes_without_starting_services(
        self,
    ) -> None:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUNNER),
                "-PreflightOnly",
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Local runner preflight passed.")


if __name__ == "__main__":
    unittest.main()
