"""Execute the Windows gate coordinator with synthetic native tools, never providers."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify.ps1"
STUBS = r"""
function uv {
    $global:LASTEXITCODE = 0
    if (($args -join ' ') -match 'check_(?:f008|current_task)_readiness.py') {
        Write-Output 'SYNTHETIC_READINESS_REFUSED'
        $global:LASTEXITCODE = 7
    } elseif ($args -contains '--version') {
        Write-Output 'Python 3.13.3'
    } elseif ($args -contains 'pytest' -and $env:VERIFY_SYNTHETIC_FAIL -eq '1') {
        Write-Output 'synthetic backend failure'
        $global:LASTEXITCODE = 8
    } else {
        Write-Output 'synthetic tool success'
    }
}
function node {
    $global:LASTEXITCODE = 0
    if ($args -contains '--version') { Write-Output 'v22.16.0' }
    else { Write-Output 'synthetic capture success' }
}
function corepack {
    $global:LASTEXITCODE = 0
    if ($args -contains '--version') { Write-Output '11.19.0' }
    else { Write-Output 'synthetic frontend success' }
}
"""


class RepositoryVerificationTests(unittest.TestCase):
    def run_coordinator(
        self, arguments: str, *, fail_backend: bool = False, output_width: int | None = None
    ) -> str:
        command = f"& '{str(VERIFY).replace(chr(39), chr(39) * 2)}' {arguments}"
        if output_width is not None:
            command = (
                f"try {{ {command} 2>&1 | Out-String -Width {output_width} }} "
                f"catch {{ $_ | Out-String -Width {output_width}; exit 1 }}"
            )
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                STUBS + "\n" + command,
            ],
            cwd=ROOT,
            env={**os.environ, "VERIFY_SYNTHETIC_FAIL": "1" if fail_backend else "0"},
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.last_returncode = result.returncode
        return result.stdout + result.stderr

    def test_repository_phase_runs_all_gates_without_task_readiness(self) -> None:
        output = self.run_coordinator("-Phase RepositoryVerification")
        self.assertEqual(self.last_returncode, 0, output)
        self.assertNotIn("SYNTHETIC_READINESS_REFUSED", output)
        for name in (
            "Backend lock validation",
            "Backend dependency sync",
            "Frontend frozen install",
            "Frontend peer dependency validation",
            "Backend format check",
            "Backend lint",
            "Backend and script typecheck",
            "Frontend build",
            "Backend tests",
            "Frontend format check",
            "CI workflow format check",
            "Frontend lint",
            "Frontend typecheck",
            "Frontend tests",
            "Documentation checker tests",
            "Capture unit tests",
            "Documentation and repository contracts",
        ):
            self.assertIn(f"{name} passed.", output)
        self.assertLess(output.index("Frontend build passed."), output.index("Backend tests"))

    def test_development_and_formal_still_require_authorized_readiness(self) -> None:
        for phase in ("Development", "FormalAcceptance"):
            with self.subTest(phase=phase):
                output = self.run_coordinator(f"-Phase {phase}")
                self.assertNotEqual(self.last_returncode, 0, output)
                self.assertIn("SYNTHETIC_READINESS_REFUSED", output)
                self.assertNotIn("Backend dependency sync", output)

    def test_repository_phase_cannot_silently_reduce_quality_gates(self) -> None:
        for switch in ("-MechanismOnly", "-PreflightOnly"):
            with self.subTest(switch=switch):
                output = self.run_coordinator(f"-Phase RepositoryVerification {switch}")
                self.assertNotEqual(self.last_returncode, 0, output)
                self.assertIn("requires all quality gates", output)
                self.assertNotIn("All local verification gates passed", output)

    def test_failed_gate_stops_dependent_gates(self) -> None:
        for width in (None, 16, 40, 120):
            with self.subTest(output_width=width):
                output = self.run_coordinator(
                    "-Phase RepositoryVerification", fail_backend=True, output_width=width
                )
                self.assertEqual(self.last_returncode, 1, output)
                record, _ = json.JSONDecoder().raw_decode(output[output.index("\n{") + 1 :])
                self.assertEqual(record["command"], "Backend tests")
                self.assertEqual(record["exit_code"], 8)
                self.assertIs(record["failed"], True)
                self.assertEqual(record["scope"], "ProductTests")
                self.assertEqual(record["actual"], "failed")
                self.assertIn("dependent gates", record["not_run"])
                self.assertNotIn("==> Frontend format check", output)
                self.assertNotIn("Frontend tests passed", output)
                self.assertNotIn("All local verification gates passed", output)

    def test_windows_powershell_guard_keeps_error_and_stderr_contracts(self) -> None:
        output = self.run_coordinator("-GateSelfTest")
        self.assertEqual(self.last_returncode, 0, output)
        self.assertIn("Native gate self-test PASS", output)
        self.assertIn("synthetic-benign-stderr passed", output)


if __name__ == "__main__":
    unittest.main()
