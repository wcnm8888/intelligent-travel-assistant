"""Read-only readiness check for whichever task is declared current."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TASK = re.compile(r"^- 当前任务：`(F-\d{3}) ([^`]+)`$", re.MULTILINE)
STATUS = re.compile(r"^- 状态：`([^`]+)`$", re.MULTILINE)
BASELINE = re.compile(r"^- 基线证据：`([^`]+)`$", re.MULTILINE)


def readiness_issues(root: Path, phase: str) -> list[str]:
    path = root / "docs/project-management/current-task.md"
    if not path.is_file():
        return ["current_task_missing"]
    text = path.read_text(encoding="utf-8")
    tasks = TASK.findall(text)
    statuses = STATUS.findall(text)
    issues: list[str] = []
    if len(tasks) != 1:
        issues.append("exactly_one_current_task_required")
    if len(statuses) != 1:
        issues.append("exactly_one_current_status_required")
    task_id = tasks[0][0] if len(tasks) == 1 else "UNKNOWN"
    status = statuses[0] if len(statuses) == 1 else "UNKNOWN"
    if phase == "development" and not status.startswith("ACTIVE / IMPLEMENTATION_AUTHORIZED"):
        issues.append("development_task_not_active_or_authorized")
    if phase == "tool_readiness" and "AUTHORIZED" not in status:
        issues.append("task_not_authorized")
    if phase == "formal_acceptance" and status != "ACTIVE / FORMAL_ACCEPTANCE_AUTHORIZED":
        issues.append("formal_acceptance_not_authorized")
    if task_id == "F-008" and status.startswith("ACTIVE"):
        issues.append("archived_f008_must_not_be_reactivated")
    if "F-008 保持 `DONE / ARCHIVED`" not in text:
        issues.append("f008_archive_boundary_missing")
    if "未授权 commit、push、PR、CI、merge 或 remote 修改" not in text:
        issues.append("git_delivery_boundary_missing")
    if "真实高德、DeepSeek、和风及真实地图加载均未授权" not in text:
        issues.append("real_provider_boundary_missing")
    baselines = BASELINE.findall(text)
    if len(baselines) != 1:
        issues.append("exactly_one_baseline_required")
    else:
        relative = baselines[0]
        baseline = (root / relative).resolve()
        allowed = (root / f"output/{task_id.lower().replace('-', '')}").resolve()
        if (
            not baseline.is_relative_to(allowed)
            or not baseline.is_dir()
            or not (baseline / "git-status-porcelain-v2.bin").is_file()
        ):
            issues.append("current_task_baseline_invalid")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--phase",
        choices=("development", "tool_readiness", "formal_acceptance"),
        required=True,
    )
    args = parser.parse_args()
    issues = readiness_issues(args.root.resolve(), args.phase)
    print(
        json.dumps(
            {
                "kind": "current_task_readiness",
                "phase": args.phase,
                "result": "PASS" if not issues else "REFUSED",
                "issues": issues,
            },
            ensure_ascii=False,
        )
    )
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
