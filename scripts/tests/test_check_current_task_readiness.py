from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_current_task_readiness import readiness_issues  # noqa: E402


class CurrentTaskReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="current-task-readiness-"))
        (self.root / "docs/project-management").mkdir(parents=True)
        baseline = self.root / "output/f010/run-baseline"
        baseline.mkdir(parents=True)
        (baseline / "git-status-porcelain-v2.bin").write_bytes(b"status")

    def write_task(self, status: str = "ACTIVE / IMPLEMENTATION_AUTHORIZED") -> None:
        (self.root / "docs/project-management/current-task.md").write_text(
            "\n".join(
                (
                    "# 当前任务",
                    "",
                    "- 当前任务：`F-010 地图优先统一规划流程与 DeepSeek 安全降级`",
                    f"- 状态：`{status}`",
                    "- 执行边界：本地离线开发；真实高德、DeepSeek、和风及真实地图加载均未授权",
                    "- 基线证据：`output/f010/run-baseline/`",
                    "- Git 交付：未授权 commit、push、PR、CI、merge 或 remote 修改",
                    "- F-008 保持 `DONE / ARCHIVED`",
                )
            ),
            encoding="utf-8",
        )

    def test_development_accepts_one_authorized_current_task(self) -> None:
        self.write_task()
        self.assertEqual(readiness_issues(self.root, "development"), [])

    def test_formal_acceptance_is_independently_refused(self) -> None:
        self.write_task()
        self.assertIn(
            "formal_acceptance_not_authorized",
            readiness_issues(self.root, "formal_acceptance"),
        )

    def test_missing_baseline_and_f008_boundary_are_rejected(self) -> None:
        self.write_task()
        (self.root / "output/f010/run-baseline/git-status-porcelain-v2.bin").unlink()
        task = self.root / "docs/project-management/current-task.md"
        task.write_text(
            task.read_text(encoding="utf-8").replace("- F-008 保持 `DONE / ARCHIVED`", ""),
            encoding="utf-8",
        )
        issues = readiness_issues(self.root, "development")
        self.assertIn("current_task_baseline_invalid", issues)
        self.assertIn("f008_archive_boundary_missing", issues)


if __name__ == "__main__":
    unittest.main()
