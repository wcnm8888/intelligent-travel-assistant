"""Negative and positive execution-mechanism contracts, without product imports."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_f008_readiness import (  # noqa: E402
    MYPY,
    UNCERTAINTIES,
    canonical_issues,
    command_failed,
    command_issues,
    date_issues,
    diagnostic,
    failure_action,
    inventory,
    preflight,
)


class ReadinessTests(unittest.TestCase):
    def test_tool_readiness_requires_real_evidence_and_stopped_development_is_denied(self) -> None:
        with patch("check_f008_readiness.fingerprint", return_value="version"):
            issues = preflight(Path("."), "tool_readiness", {})
        self.assertIn("missing_readiness:tool_runtime", issues)
        self.assertIn("missing_readiness:diagnostic_capture", issues)
        self.assertNotIn("new_formal_batch_not_authorized", issues)
        stopped = {"phase": "development", "status": "STOPPED", "development_authorized": True}
        self.assertIn("execution_not_active", preflight(Path("."), "development", stopped))
        active = dict(stopped, status="ACTIVE")
        self.assertEqual(preflight(Path("."), "development", active), [])
        self.assertEqual(failure_action("development", 3, limit=4), "REPAIR_WITHIN_AUTHORIZATION")
        self.assertEqual(failure_action("development", 4, limit=4), "STOP_REPAIR_LIMIT")

    def test_formal_missing_conditions_and_development_failure_are_distinct(self) -> None:
        with patch("check_f008_readiness.fingerprint", return_value="version"):
            issues = preflight(Path("."), "formal_acceptance", {})
        self.assertIn("new_formal_batch_not_authorized", issues)
        self.assertIn("missing_readiness:tool_runtime", issues)
        self.assertIn("missing_readiness:diagnostic_capture", issues)
        self.assertEqual(failure_action("development", 0), "REPAIR_WITHIN_AUTHORIZATION")
        self.assertEqual(failure_action("tool_readiness", 1), "REPAIR_WITHIN_AUTHORIZATION")
        self.assertEqual(failure_action("development", 2), "STOP_REPAIR_LIMIT")
        self.assertEqual(failure_action("formal_acceptance", 0), "FREEZE_ORIGINAL_BATCH")

    def test_command_regressions(self) -> None:
        bad = [
            ["playwright-cli", "click", "getByRole('button', { name: 'invented' })"],
            [
                "playwright-cli",
                "eval",
                "el => el.ariaChecked",
                "getByRole('checkbox', { name: '博物馆 / 文化' })",
            ],
            ["New-Item", "-ItemType", "Directory", "-LiteralPath", "safe"],
            ["rg", "pattern", "frontend/src/*.tsx"],
            ["uv", "run", "--directory", "backend", "mypy", "tests/one.py"],
            ["playwright-cli", "resize", "resize", "390", "844"],
            ["playwright-cli", "click", "e42"],
            ["playwright-cli", "eval", "el => el.checked", "guessed-selector"],
        ]
        for argv in bad:
            with self.subTest(argv=argv):
                self.assertTrue(command_issues(argv))
        for argv in [
            list(MYPY),
            ["New-Item", "-Path", "safe space"],
            ["rg", "-g", "*.tsx", "label", "frontend/src"],
            ["playwright-cli", "-s=synthetic", "resize", "390", "844"],
            ["playwright-cli", "click", "getByRole('button', { name: '分析影响' })"],
            [
                "playwright-cli",
                "eval",
                "el => el.checked",
                "getByRole('checkbox', { name: '博物馆 / 文化' })",
            ],
        ]:
            self.assertEqual(command_issues(argv), [])

    def test_capture_commands_require_exact_file_and_hash(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="f008-capture-command-"))
        path = root / "scripts/capture_f008_replan.js"
        path.parent.mkdir()
        path.write_text("async page => page.url()", encoding="utf-8")
        approved = {"scripts/capture_f008_replan.js": hashlib.sha256(path.read_bytes()).hexdigest()}
        good = ["playwright-cli", "run-code", "--filename=scripts/capture_f008_replan.js"]
        self.assertEqual(command_issues(good, root=root, approved_scripts=approved), [])
        for bad in [
            ["playwright-cli", "run-code", "async page => page.url()"],
            ["playwright-cli", "run-code", "--filename=../outside.js"],
            ["playwright-cli", "run-code", "--filename=scripts/other.js"],
            ["playwright-cli", "requests", "--filename=raw.txt"],
            ["playwright-cli", "request", "1"],
        ]:
            self.assertTrue(command_issues(bad, root=root, approved_scripts=approved))
        path.write_text("changed", encoding="utf-8")
        self.assertEqual(
            command_issues(good, root=root, approved_scripts=approved),
            ["capture_script_hash_mismatch"],
        )
        for name in ("关闭局部调整", "重新发起调整"):
            self.assertEqual(
                command_issues(
                    ["playwright-cli", "click", f"getByRole('button', {{ name: '{name}' }})"]
                ),
                [],
            )
        self.assertEqual(command_issues(["playwright-cli", "requests"]), [])

    def test_observed_journey_commands_and_negative_variants(self) -> None:
        dates = {"start": "2026-09-12", "end": "2026-09-13"}
        first = "getByRole('article', { name: '第 1 天，2026-09-12 行程' })"
        second = "getByRole('article', { name: '第 2 天，2026-09-13 行程' })"
        controls = [
            "getByText('自然', { exact: true })",
            "getByText('历史', { exact: true })",
            "getByText('博物馆 / 文化', { exact: true })",
            "getByText('景区 / 自然', { exact: true })",
            "getByRole('button', { name: '生成2日计划' })",
            "getByRole('button', { name: '取消并保留原计划' })",
            first + ".getByRole('button', { name: '替换活动' }).nth(0)",
            first + ".getByRole('button', { name: '删除活动' }).nth(1)",
            second + ".getByRole('button', { name: '替换活动' }).nth(0)",
            second + ".getByRole('button', { name: '调整时间' }).nth(0)",
            second + ".getByRole('button', { name: '调整当天顺序' })",
            "getByRole('region', { name: '调整 2026-09-13 活动顺序' })"
            ".getByRole('button', { name: '下移' }).nth(0)",
        ]
        commands = [["click", control] for control in controls]
        commands.extend(
            ["fill", f"getByLabel('{label}')", value]
            for label, value in (
                ("目的地城市 *", "杭州"),
                ("总预算 *", "4000.00"),
                ("住宿区域或 POI *", "西湖附近"),
                ("开始日期 *", dates["start"]),
                ("结束日期 *", dates["end"]),
            )
        )
        commands.extend(
            ["fill", f"getByRole('textbox', {{ name: '{label}' }})", value]
            for label, value in (("新的开始时间", "09:45"), ("新的结束时间", "11:45"))
        )
        commands.extend(
            [
                ["localstorage-get", "ita.last-local-job"],
                ["console"],
                ["requests", "--static"],
                ["reload"],
                ["open", "http://127.0.0.1:18008"],
                [
                    "eval",
                    "JSON.stringify({viewport:innerWidth,"
                    "document:document.documentElement.scrollWidth})",
                ],
            ]
        )
        for args in commands:
            with self.subTest(args=args):
                self.assertEqual(command_issues(["playwright-cli", *args], dates=dates), [])
        bad = [
            ["click", controls[6].replace("2026-09-12", "2026-09-14")],
            ["click", controls[6].replace("nth(0)", "nth(9)")],
            ["click", controls[6] + ".click()"],
            ["click", "getByText('invented', { exact: true })"],
            ["fill", "getByLabel('开始日期 *')", "2026-09-14"],
            ["localstorage-get", "token"],
            ["localstorage-set", "ita.last-local-job", "arbitrary"],
            ["requests", "--static", "--filename=raw.txt"],
            ["console", "--filename=raw.txt"],
            ["eval", "localStorage.clear()"],
            ["eval", "fetch('https://example.com')"],
            ["eval", commands[-1][1] + ";location.href='https://example.com'"],
        ]
        bad.extend(
            ["open", url]
            for url in (
                "https://example.com",
                "http://127.0.0.1:18008.evil/",
                "http://127.0.0.1:18008@evil/",
                "http://127.0.0.1:180080/",
            )
        )
        for args in bad:
            with self.subTest(args=args):
                self.assertTrue(command_issues(["playwright-cli", *args], dates=dates))
        invalid_dates = {"start": "2026-02-30", "end": "x').click()"}
        self.assertTrue(command_issues(["playwright-cli", *commands[6]], dates=invalid_dates))

    def test_screenshot_is_new_png_inside_bound_artifact_root(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="f008-screenshot-"))
        owned = root / "output/f008-r5/new-batch"
        good = ["playwright-cli", "screenshot", "--filename=output/f008-r5/new-batch/mobile.png"]
        self.assertEqual(command_issues(good, root=root, artifact_root=owned), [])
        for filename in (
            "../outside.png",
            "output/f008-r5/new-batch/../old-batch/mobile.png",
            "output/f008-r5/new-batch/raw.json",
            "output/diagnostics/old-evidence.png",
        ):
            with self.subTest(filename=filename):
                self.assertTrue(
                    command_issues(
                        ["playwright-cli", "screenshot", f"--filename={filename}"],
                        root=root,
                        artifact_root=owned,
                    )
                )
        self.assertTrue(command_issues(good, root=root))
        self.assertTrue(command_issues(good, root=root, artifact_root=root.parent))
        owned.mkdir(parents=True)
        original = owned / "mobile.png"
        original.write_bytes(b"original evidence")
        self.assertTrue(command_issues(good, root=root, artifact_root=owned))
        self.assertEqual(original.read_bytes(), b"original evidence")

    def test_date_and_partial_contract(self) -> None:
        today = date(2026, 9, 11)
        self.assertEqual(date_issues("2026-09-12", "2026-09-13", "2026-09-12", today), [])
        self.assertEqual(date_issues("2026-09-16", "2026-09-17", "2026-09-16", today), [])
        for start, end, fixture in [
            ("2026-09-11", "2026-09-12", "2026-09-11"),
            ("2026-09-17", "2026-09-18", "2026-09-17"),
            ("09/11/2026", "2026-09-12", "2026-09-11"),
            ("2026-09-10", "2026-09-11", "2026-09-10"),
            ("2026-02-30", "2026-03-01", "2026-02-30"),
            ("2026-09-11", "2026-09-13", "2026-09-11"),
            ("2026-09-11", "2026-09-12", "2026-09-12"),
        ]:
            self.assertTrue(date_issues(start, end, fixture, today))
        good = dict(
            status="partial",
            days=2,
            errors=[],
            violations=[],
            assessment="budget_indeterminate",
            uncertainties=list(UNCERTAINTIES),
            unknown_amounts=[None],
        )
        self.assertEqual(canonical_issues(good), [])
        for key, value in [
            ("status", "ready"),
            ("unknown_amounts", [0]),
            ("errors", ["error"]),
            ("uncertainties", []),
            ("assessment", "within_budget"),
        ]:
            bad = copy.deepcopy(good)
            bad[key] = value
            self.assertTrue(canonical_issues(bad))

    def test_nonzero_and_error_output_redaction_and_missing_fields(self) -> None:
        for code, output in [
            (7, ""),
            (0, "### Error synthetic"),
            (0, "TimeoutError"),
            (0, "error: synthetic"),
            (0, "os error 123"),
        ]:
            self.assertTrue(command_failed(code, output))
        self.assertFalse(command_failed(0, "0 errors; all checks passed"))
        secret = "synthetic-private-value-never-persist"
        before = diagnostic("tool_readiness", "probe", 0, f"### Error {secret}")
        self.assertEqual(before["request_id"], "NOT_APPLICABLE")
        after = diagnostic(
            "development",
            "recovery",
            1,
            secret,
            {
                "status": "failed",
                "request_id": "synthetic-request-2",
                "http_status": 200,
                "public_code": "provider_unavailable",
                "raw_response": secret,
            },
        )
        self.assertEqual(after["request_id"], "synthetic-request-2")
        self.assertEqual(after["diagnostic_code"], "UNKNOWN")
        self.assertNotIn(secret, json.dumps([before, after]))
        self.assertIn("remaining_product_journey", after["not_run"])

    def test_certificate_hash_version_and_kind_cannot_be_substituted(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="f008-cert-"))
        folder = root / "output/diagnostics"
        folder.mkdir(parents=True)
        refs = {}
        for name in (
            "static",
            "tool_runtime",
            "development",
            "journey_design",
            "diagnostic_capture",
        ):
            path = folder / f"{name}.json"
            path.write_text(json.dumps({"kind": name, "result": "PASS", "fingerprint": "version"}))
            refs[name] = {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        tomorrow = datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)
        contract = dict(
            phase="formal_acceptance",
            status="ACTIVE",
            formal_authorized=True,
            scale_approval="confirmed",
            readiness=refs,
            dates={
                "start": tomorrow.isoformat(),
                "end": (tomorrow + timedelta(days=1)).isoformat(),
                "fixture_start": tomorrow.isoformat(),
            },
            frozen_commands=[list(MYPY)],
        )
        with patch("check_f008_readiness.fingerprint", return_value="version"):
            self.assertEqual(preflight(root, "formal_acceptance", contract), [])
            self.assertEqual(preflight(root, "tool_readiness", contract), [])
            bound = copy.deepcopy(contract)
            bound["artifact_root"] = "output/f008-r5/bound-batch"
            locator = (
                "getByRole('article', { name: '第 1 天，"
                + tomorrow.isoformat()
                + " 行程' }).getByRole('button', { name: '替换活动' }).nth(0)"
            )
            bound_commands = [
                ["playwright-cli", "click", locator],
                [
                    "playwright-cli",
                    "screenshot",
                    "--filename=output/f008-r5/bound-batch/mobile.png",
                ],
            ]
            bound["frozen_commands"] = bound_commands
            self.assertEqual(preflight(root, "formal_acceptance", bound), [])
            bound_commands[0][-1] = locator.replace("nth(0)", "nth(2)")
            self.assertIn("unverified_locator", preflight(root, "formal_acceptance", bound))
            missing = copy.deepcopy(contract)
            missing["readiness"] = {
                key: value for key, value in refs.items() if key != "diagnostic_capture"
            }
            self.assertIn(
                "missing_readiness:diagnostic_capture", preflight(root, "tool_readiness", missing)
            )
            (folder / "static.json").write_text("{}")
            self.assertIn(
                "evidence_hash_mismatch:static", preflight(root, "formal_acceptance", contract)
            )
        with patch("check_f008_readiness.fingerprint", return_value="new-version"):
            self.assertIn(
                "stale_or_inapplicable_evidence:tool_runtime",
                preflight(root, "formal_acceptance", contract),
            )

    def test_inventory_repeat_unique_no_line_loss(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="f008-count-"))
        rows = {"backend/tracked file.py": b"one\r\ntwo", "frontend/new file.ts": b"a\nb\n"}
        for path, data in rows.items():
            f = root / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)

        def fake_git(_root: Path, *args: str) -> bytes:
            self.assertEqual(_root, root)
            if args[0] == "diff":
                return b"3\t1\tbackend/tracked file.py\0"
            if args[0] == "ls-files":
                return b"frontend/new file.ts\0"
            return b"baseline\n"

        with patch("check_f008_readiness.git", side_effect=fake_git):
            first, second = inventory(root), inventory(root)
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"]), 2)
        self.assertEqual(sum(r["net"] for r in first["rows"]), 4)
        self.assertEqual(first["rows"][0]["lines"], 2)

    def test_git_cwd_is_explicit_even_for_backend_invocation(self) -> None:
        from check_f008_readiness import git

        with patch("check_f008_readiness.subprocess.check_output", return_value=b"") as call:
            git(Path("project root"), "ls-files", "-z")
        self.assertEqual(call.call_args.kwargs["cwd"], Path("project root"))
        self.assertEqual(call.call_args.kwargs["stderr"], subprocess.PIPE)


if __name__ == "__main__":
    unittest.main()
