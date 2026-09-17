"""F-008 bounded preflight and synthetic contracts; never starts a product service."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CONTRACT = re.compile(r"```f008-execution\s*\n(.*?)\n```", re.DOTALL)
UNCERTAINTIES = {
    "activity_duration_estimated_model",
    "travel_buffer_estimated",
    "budget_indeterminate",
    "source_validity_unknown",
}
MYPY = ("uv", "run", "--directory", "backend", "--frozen", "mypy", "src", "tests", "../scripts")
ERRORS = re.compile(
    r"### Error|TimeoutError|(?im:^\s*(?:error|fatal|exception|traceback)\b)|os error \d+"
)
STACK2 = {
    "backend/src/intelligent_travel_assistant/application/planning/scheduling.py",
    "backend/src/intelligent_travel_assistant/application/services/multicity_planning.py",
    "backend/tests/application/test_offline_planning_orchestrator.py",
    "backend/tests/application/test_multicity_provider_planning.py",
    "backend/tests/application/test_provider_planning_job_executor.py",
}
STACK3_BACKEND = {
    "backend/src/intelligent_travel_assistant/adapters/providers/deepseek.py",
    "backend/src/intelligent_travel_assistant/application/planning/candidate_resolution.py",
    "backend/tests/adapters/test_deepseek_adapter.py",
    "backend/tests/application/test_deepseek_candidate_resolution.py",
    "backend/tests/browser_f008_support.py",
    "backend/tests/browser_f008_production_support.py",
    "backend/tests/test_f008_local_acceptance.py",
}
SHARED_STACKS = {
    # Current task core ownership and subsequent cross-stack repairs overlap.
    # Do not invent a historical hunk split or move costs to a more generous stack.
    "backend/tests/application/test_provider_planning_job_executor.py": "1/2_shared",
    "backend/src/intelligent_travel_assistant/application/planning/candidate_resolution.py": (
        "2/3_pending"
    ),
    "backend/src/intelligent_travel_assistant/adapters/providers/deepseek.py": "1/3_pending",
    "backend/tests/adapters/test_deepseek_adapter.py": "1/3_pending",
    "backend/tests/application/test_deepseek_candidate_resolution.py": "1/3_pending",
}
LOCATORS = {
    "getByLabel('目的地城市 *')",
    "getByLabel('总预算 *')",
    "getByLabel('住宿区域或 POI *')",
    "getByText('自然', { exact: true })",
    "getByText('历史', { exact: true })",
    "getByText('博物馆 / 文化', { exact: true })",
    "getByText('景区 / 自然', { exact: true })",
    "getByRole('button', { name: '生成2日计划' })",
    "getByRole('button', { name: '取消并保留原计划' })",
    "getByRole('textbox', { name: '新的开始时间' })",
    "getByRole('textbox', { name: '新的结束时间' })",
    "getByLabel('开始日期 *')",
    "getByLabel('结束日期 *')",
    "getByRole('button', { name: '分析影响' })",
    "getByRole('button', { name: '准备影响分析' })",
    "getByRole('button', { name: '确认并生成新版本' })",
    "getByRole('button', { name: '关闭局部调整' })",
    "getByRole('button', { name: '重新发起调整' })",
    "getByRole('checkbox', { name: '博物馆 / 文化' })",
    "getByRole('checkbox', { name: '景区 / 自然' })",
}
LAYOUT_PROBE = "JSON.stringify({viewport:innerWidth,document:document.documentElement.scrollWidth})"


def journey_locators(dates: dict[str, str]) -> set[str]:
    """Bind only observed day controls to the task's canonical dates, not arbitrary code."""
    result = set(LOCATORS)
    for day, key in ((1, "start"), (2, "end")):
        value = dates.get(key, "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            continue
        try:
            date.fromisoformat(value)
        except ValueError:
            continue
        article = f"getByRole('article', {{ name: '第 {day} 天，{value} 行程' }})"
        result.add(article + ".getByRole('button', { name: '替换活动' }).nth(0)")
        if day == 1:
            result.add(article + ".getByRole('button', { name: '删除活动' }).nth(1)")
        else:
            result.add(article + ".getByRole('button', { name: '调整时间' }).nth(0)")
            result.add(article + ".getByRole('button', { name: '调整当天顺序' })")
            result.add(
                f"getByRole('region', {{ name: '调整 {value} 活动顺序' }})"
                ".getByRole('button', { name: '下移' }).nth(0)"
            )
    return result


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE)


def classification(path: str) -> tuple[str, str]:
    if path.startswith("output/"):
        return "diagnostic", "none"
    if path.startswith("docs/") or path.endswith(".md"):
        return "documentation", "none"
    if path.startswith("scripts/"):
        return "mechanism", "separate"
    kind = "test" if "/tests/" in path or ".test." in path else "code"
    if path in SHARED_STACKS:
        return kind, SHARED_STACKS[path]
    if path in STACK2:
        return kind, "2"
    if path.startswith("frontend/") or path in STACK3_BACKEND:
        return kind, "3"
    if path.startswith("backend/"):
        return kind, "1"
    return "other", "unassigned"


def inventory(root: Path) -> dict[str, Any]:
    """HEAD diff includes staged+unstaged; untracked counted once, never via status folders."""
    rows: dict[str, dict[str, Any]] = {}
    raw = git(root, "diff", "--no-renames", "--numstat", "-z", "HEAD").decode("utf-8")
    for record in filter(None, raw.split("\0")):
        added, deleted, path = record.split("\t", 2)
        rows[path] = {
            "path": path,
            "tracked": True,
            "added": int(added) if added != "-" else None,
            "deleted": int(deleted) if deleted != "-" else None,
        }
    for path in filter(
        None, git(root, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    ):
        if path in rows:
            raise ValueError("duplicate_inventory_path")
        rows[path] = {"path": path, "tracked": False, "added": None, "deleted": 0}
    for path, row in rows.items():
        kind, stack = classification(path)
        row.update(category=kind, stack=stack)
        f = root / path
        # Only source/document text; database, credentials, and old browser evidence never read.
        safe = (
            kind != "other"
            and f.suffix in {".py", ".ps1", ".ts", ".tsx", ".css", ".md", ".json"}
            and not path.startswith("output/playwright/")
            and not f.is_symlink()
        )
        if f.is_file() and safe:
            data = f.read_bytes()
            row.update(sha256=hashlib.sha256(data).hexdigest(), lines=len(data.splitlines()))
            if not row["tracked"]:
                row["added"] = row["lines"]
        row["net"] = (
            row["added"] - row["deleted"]
            if row["added"] is not None and row["deleted"] is not None
            else None
        )
    ordered = [rows[p] for p in sorted(rows)]
    summary = {}
    for key in sorted({r["category"] for r in ordered}):
        selected = [r for r in ordered if r["category"] == key]
        summary[key] = {
            "files": len(selected),
            "net": sum(r["net"] or 0 for r in selected),
            "uncounted": sum(r["net"] is None for r in selected),
        }
    return {
        "baseline": git(root, "rev-parse", "HEAD").decode().strip(),
        "rows": ordered,
        "summary": summary,
        "boundary": (
            "Git tracked changes plus nonignored untracked; "
            "ignored runtime artifacts excluded, not read"
        ),
    }


def fingerprint(root: Path) -> str:
    paths = set(filter(None, git(root, "ls-files", "-z").decode().split("\0")))
    paths.update(
        filter(
            None, git(root, "ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
        )
    )
    digest = hashlib.sha256()
    for name in sorted(paths):
        if not name.startswith(("backend/", "frontend/", "scripts/")):
            continue
        if Path(name).suffix not in {
            ".py",
            ".js",
            ".ps1",
            ".ts",
            ".tsx",
            ".css",
            ".toml",
            ".json",
            ".yaml",
            ".txt",
            ".lock",
        }:
            continue
        path = root / name
        digest.update(name.encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"MISSING")
    return digest.hexdigest()


def read_contract(root: Path) -> dict[str, Any]:
    matches = CONTRACT.findall(
        (root / "docs/project-management/current-task.md").read_text(encoding="utf-8")
    )
    if len(matches) != 1:
        raise ValueError("exactly_one_execution_contract_required")
    value: dict[str, Any] = json.loads(matches[0])
    return value


def failure_action(phase: str, repairs_used: int, limit: int = 2) -> str:
    if phase == "formal_acceptance":
        return "FREEZE_ORIGINAL_BATCH"
    return "STOP_REPAIR_LIMIT" if repairs_used >= limit else "REPAIR_WITHIN_AUTHORIZATION"


def command_issues(
    argv: list[str],
    *,
    root: Path | None = None,
    approved_scripts: dict[str, str] | None = None,
    dates: dict[str, str] | None = None,
    artifact_root: Path | None = None,
) -> list[str]:
    if not argv:
        return ["missing_command"]
    if "mypy" in argv and tuple(argv) != MYPY:
        return ["use_authoritative_mypy_source_roots"]
    if argv[0] == "New-Item" and ("-LiteralPath" in argv or "-Path" not in argv):
        return ["new_item_requires_path"]
    if argv[0] == "rg" and any("*" in a and ("/" in a or "\\" in a) for a in argv[1:]):
        return ["rg_use_directory_and_glob_filter"]
    if argv[0] == "playwright-cli":
        args = [a for a in argv[1:] if not a.startswith("-s=") and a != "--raw"]
        if not args:
            return ["missing_browser_command"]
        arity = {
            "resize": 2,
            "fill": 2,
            "click": 1,
            "press": 1,
            "eval": 2,
            "open": 1,
            "close": 0,
            "reload": 0,
            "snapshot": 0,
            "requests": 0,
            "run-code": 1,
            "console": 0,
            "localstorage-get": 1,
            "screenshot": 1,
        }
        cmd = args[0]
        if args == ["requests", "--static"] or args == ["eval", LAYOUT_PROBE]:
            return []
        if cmd not in arity or len(args) - 1 != arity[cmd]:
            return ["browser_command_arity"]
        if cmd == "open" and args[1] not in {
            "http://127.0.0.1:18008",
            "http://127.0.0.1:18008/",
        }:
            return ["browser_origin_denied"]
        if cmd == "localstorage-get" and args[1] != "ita.last-local-job":
            return ["unverified_storage_key"]
        if cmd == "screenshot":
            if root is None or artifact_root is None or not args[1].startswith("--filename="):
                return ["screenshot_requires_owned_png"]
            path = (root / args[1].removeprefix("--filename=")).resolve()
            owned = artifact_root.resolve()
            if (
                not owned.is_relative_to((root / "output").resolve())
                or not path.is_relative_to(owned)
                or path.suffix != ".png"
                or path.exists()
            ):
                return ["screenshot_requires_new_owned_png"]
        if cmd == "run-code":
            relative = "scripts/capture_f008_replan.js"
            if root is None or not args[1].startswith("--filename="):
                return ["capture_requires_pinned_file"]
            candidate = root / args[1].removeprefix("--filename=")
            path = candidate.resolve()
            if candidate.is_symlink() or path != (root / relative).resolve() or not path.is_file():
                return ["capture_requires_pinned_file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != (approved_scripts or {}).get(
                relative
            ):
                return ["capture_script_hash_mismatch"]
        if cmd == "resize" and not all(x.isdigit() for x in args[1:]):
            return ["resize_requires_two_numbers"]
        if cmd in {"click", "fill", "eval"}:
            target = args[2] if cmd == "eval" else args[1]
            if target not in journey_locators(dates or {}):
                return ["unverified_locator"]
            if cmd == "fill" and dates is not None:
                for label, key in (("开始日期 *", "start"), ("结束日期 *", "end")):
                    if target == f"getByLabel('{label}')" and args[2] != dates.get(key):
                        return ["date_input_differs_from_canonical"]
            if cmd == "eval" and args[1] not in {
                "el => el.checked",
                "el => el.value",
                "el => el.textContent",
            }:
                return ["unverified_state_probe"]
    return []


def date_issues(start: str, end: str, fixture_start: str, today: date) -> list[str]:
    values = [start, end, fixture_start]
    if any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is None for v in values):
        return ["date_requires_iso_input_value"]
    try:
        first, last, fixture = map(date.fromisoformat, values)
    except ValueError:
        return ["invalid_calendar_date"]
    return (
        []
        if today + timedelta(days=1) <= first <= today + timedelta(days=5)
        and last == first + timedelta(days=1)
        and fixture == first
        else ["canonical_date_mismatch_or_stale"]
    )


def canonical_issues(value: dict[str, Any]) -> list[str]:
    valid = (
        value.get("status") == "partial"
        and value.get("days") == 2
        and value.get("errors") == []
        and value.get("violations") == []
        and value.get("assessment") == "budget_indeterminate"
        and set(value.get("uncertainties", [])) == UNCERTAINTIES
        and bool(value.get("unknown_amounts"))
        and all(x is None for x in value["unknown_amounts"])
    )
    return [] if valid else ["canonical_partial_contract_mismatch"]


def command_failed(exit_code: int, output: str) -> bool:
    return exit_code != 0 or ERRORS.search(output) is not None


def diagnostic(
    phase: str, case: str, exit_code: int, output: str, product: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Store allowlisted fields only, never raw command output or response payload."""
    result: dict[str, Any] = {
        "phase": phase,
        "case": case,
        "command": "synthetic-contract",
        "exit_code": exit_code,
        "failed": command_failed(exit_code, output),
        "error_marker": bool(ERRORS.search(output)),
        "expected": "no command error",
        "actual": "error" if command_failed(exit_code, output) else "ok",
        "not_run": ["remaining_product_journey"],
        "product_result": "NOT_REACHED" if product is None else "OBSERVED",
    }
    for key in (
        "http_status",
        "request_id",
        "replan_id",
        "public_code",
        "diagnostic_code",
        "status",
        "plan_id",
        "version",
    ):
        value = product.get(key) if product is not None else None
        # Missing after product reached is UNKNOWN, not a guessed value or N/A.
        safe = (
            isinstance(value, (str, int))
            and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", str(value)) is not None
        )
        result[key] = value if safe else ("UNKNOWN" if product is not None else "NOT_APPLICABLE")
    return result


def preflight(root: Path, phase: str, contract: dict[str, Any]) -> list[str]:
    issues = []
    if phase == "development":
        if contract.get("development_authorized") is not True:
            issues.append("business_development_not_authorized_use_mechanism_only")
        if contract.get("phase") != "development" or contract.get("status") != "ACTIVE":
            issues.append("execution_not_active")
        return issues
    if phase == "formal_acceptance":
        if contract.get("phase") != "formal_acceptance":
            issues.append("actual_phase_is_not_formal_acceptance")
        if contract.get("status") != "ACTIVE":
            issues.append("execution_not_active")
        if contract.get("formal_authorized") is not True:
            issues.append("new_formal_batch_not_authorized")
        if contract.get("scale_approval") != "confirmed":
            issues.append("scale_approval_unresolved")
    current = fingerprint(root)
    required = ["static", "tool_runtime", "diagnostic_capture"]
    if phase == "formal_acceptance":
        required.extend(("development", "journey_design"))
    for name in required:
        ref = contract.get("readiness", {}).get(name)
        if not isinstance(ref, dict):
            issues.append(f"missing_readiness:{name}")
            continue
        relative = ref.get("path", "")
        path = (root / relative).resolve()
        if (
            not path.is_relative_to(root.resolve())
            or not relative.startswith("output/diagnostics/")
            or path.suffix != ".json"
            or not path.is_file()
        ):
            issues.append(f"invalid_evidence_path:{name}")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != ref.get("sha256"):
            issues.append(f"evidence_hash_mismatch:{name}")
            continue
        evidence = json.loads(data)
        if (
            evidence.get("kind") != name
            or evidence.get("result") != "PASS"
            or evidence.get("fingerprint") != current
        ):
            issues.append(f"stale_or_inapplicable_evidence:{name}")
    today = datetime.now(timezone(timedelta(hours=8))).date()
    dates = contract.get("dates", {})
    issues.extend(
        date_issues(
            dates.get("start", ""), dates.get("end", ""), dates.get("fixture_start", ""), today
        )
    )
    commands = contract.get("frozen_commands", [])
    if not commands:
        issues.append("missing_frozen_commands")
    for command in commands:
        issues.extend(
            command_issues(
                command,
                root=root,
                approved_scripts=contract.get("capture_scripts"),
                dates=dates,
                artifact_root=(
                    root / contract["artifact_root"] if contract.get("artifact_root") else None
                ),
            )
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--phase",
        choices=["development", "tool_readiness", "formal_acceptance"],
        default="tool_readiness",
    )
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.inventory:
        first, second = inventory(root), inventory(root)
        if first != second:
            raise ValueError("inventory_changed_between_reads")
        with args.inventory.open("x", encoding="utf-8") as stream:
            json.dump(first, stream, ensure_ascii=False, indent=2)
        print("Inventory repeat comparison PASS; snapshot precedes this output file")
        return 0
    try:
        issues = preflight(root, args.phase, read_contract(root))
    except (ValueError, OSError, TypeError, KeyError):
        issues = ["invalid_or_unreadable_readiness_contract"]
    print(
        json.dumps(
            {
                "phase": args.phase,
                "kind": "static_preflight",
                "result": "BLOCKED" if issues else "PASS",
                "proof_scope": "recorded_evidence_only; does not run tools or prove authorization",
                "issues": issues,
                "product_result": "NOT_REACHED",
                "batch_created": False,
            },
            ensure_ascii=False,
        )
    )
    return 2 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
