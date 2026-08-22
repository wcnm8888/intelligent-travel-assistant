"""Offline contract tests for the owned-process local runner."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "scripts" / "run-local.ps1"


def _process_is_active(process_id: int) -> bool:
    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, process_id)
    if not process:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
            return False
        return exit_code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(process)


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
        self.assertIn("$CleanupFailed = $true", text)
        self.assertIn("Local application child process cleanup did not complete.", text)

    def test_runner_self_test_covers_frozen_negative_process_matrix(self) -> None:
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

    def test_ctrl_break_runs_finally_for_only_the_owned_children(self) -> None:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        unrelated = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Start-Sleep -Seconds 30",
            ],
            cwd=PROJECT_ROOT,
            startupinfo=startupinfo,
        )
        runner = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(RUNNER),
                "-InterruptSelfTest",
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE),
            startupinfo=startupinfo,
        )
        try:
            assert runner.stdout is not None
            pids = json.loads(runner.stdout.readline())
            self.assertTrue(_process_is_active(pids["first_pid"]))
            self.assertTrue(_process_is_active(pids["second_pid"]))

            signal_helper = """
import ctypes
import sys

kernel32 = ctypes.windll.kernel32
kernel32.FreeConsole()
if not kernel32.AttachConsole(int(sys.argv[1])):
    raise OSError(ctypes.get_last_error(), "AttachConsole failed")
kernel32.SetConsoleCtrlHandler(None, True)
if not kernel32.GenerateConsoleCtrlEvent(0, 0):
    raise OSError(ctypes.get_last_error(), "GenerateConsoleCtrlEvent failed")
kernel32.FreeConsole()
"""
            delivered = subprocess.run(
                [sys.executable, "-c", signal_helper, str(runner.pid)],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertIn(delivered.returncode, (0, 3221225786), delivered.stderr)
            stdout, stderr = runner.communicate(timeout=15)

            self.assertIn("Interrupt cleanup completed.", stdout)
            self.assertNotIn("cleanup did not complete", stderr)
            self.assertFalse(_process_is_active(pids["first_pid"]))
            self.assertFalse(_process_is_active(pids["second_pid"]))
            self.assertIsNone(unrelated.poll())
        finally:
            if runner.poll() is None:
                runner.kill()
                runner.wait(timeout=5)
            if unrelated.poll() is None:
                unrelated.terminate()
                unrelated.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
