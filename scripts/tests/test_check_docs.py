"""Tests for the documentation and repository contract checker."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from check_docs import (  # noqa: E402
    BUILD_CONSTRAINTS,
    CI_WORKFLOW,
    REQUIRED_DOCUMENTS,
    collect_issues,
)


class DocumentationChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self._create_valid_project()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _create_valid_project(self) -> None:
        for relative in REQUIRED_DOCUMENTS:
            title = Path(relative).stem.replace("-", " ").title()
            self._write(relative, f"# {title}\n")

        self._write("README.md", "# Project\n\n[Documentation](./docs/README.md)\n")
        self._write(
            "docs/project-management/current-task.md",
            "# Current Task\n\n"
            "- 当前 Step：`Step 1 - Docs（待批准）`\n\n"
            "| Step | Goal | 当前状态 |\n"
            "| --- | --- | --- |\n"
            "| Step 0 | Bootstrap | DONE |\n"
            "| Step 1 | Docs | TODO |\n",
        )
        self._write(
            "docs/project-management/implementation-plan.md",
            "# Plan\n\n等待用户批准 Step 1：Docs。\n",
        )
        self._write(
            "docs/project-management/progress.md",
            "# Progress\n\n- 下一批准动作：Step 1，Docs\n",
        )
        self._write(
            "docs/README.md",
            "# Docs\n\n- 下一步：等待用户批准执行 B-000 Step 1。\n",
        )
        self._write(
            "docs/project-management/roadmap.md",
            "# Roadmap\n\n| Priority | Task | Status | Goal | Dependency |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 0 | B-000 | ACTIVE | Baseline | None |\n",
        )
        self._write(
            ".env.example",
            "AMAP_API_KEY=\n"
            "DEEPSEEK_API_KEY=\n"
            "QWEATHER_API_HOST=\n"
            "QWEATHER_PROJECT_ID=\n"
            "QWEATHER_CREDENTIAL_ID=\n"
            "QWEATHER_PRIVATE_KEY_PATH=\n",
        )
        self._write(
            BUILD_CONSTRAINTS,
            "hatchling==1.32.0 \\\n+    --hash=sha256:a \\\n+    --hash=sha256:b\n"
            "packaging==26.3 \\\n+    --hash=sha256:c \\\n+    --hash=sha256:d\n"
            "pathspec==1.1.1 \\\n+    --hash=sha256:e \\\n+    --hash=sha256:f\n"
            "pluggy==1.6.0 \\\n+    --hash=sha256:g \\\n+    --hash=sha256:h\n"
            "tomlkit==0.15.1 \\\n+    --hash=sha256:i \\\n+    --hash=sha256:j\n"
            "trove-classifiers==2026.6.1.19 \\\n+    --hash=sha256:k \\\n+    --hash=sha256:l\n",
        )
        self._write(
            "scripts/verify.ps1",
            '$env:UV_BUILD_CONSTRAINT = Join-Path $ProjectRoot "backend\\build-constraints.txt"\n',
        )
        self._write(
            CI_WORKFLOW,
            "name: CI\n\n"
            "on:\n"
            "  pull_request:\n"
            "  push:\n"
            "    branches:\n"
            "      - main\n"
            "  workflow_dispatch:\n\n"
            "permissions:\n"
            "  contents: read\n\n"
            "jobs:\n"
            "  verify:\n"
            "    runs-on: windows-latest\n"
            "    timeout-minutes: 20\n"
            "    env:\n"
            '      AMAP_API_KEY: ""\n'
            '      DEEPSEEK_API_KEY: ""\n'
            '      QWEATHER_API_HOST: ""\n'
            '      QWEATHER_PROJECT_ID: ""\n'
            '      QWEATHER_CREDENTIAL_ID: ""\n'
            '      QWEATHER_PRIVATE_KEY_PATH: ""\n'
            "    steps:\n"
            "      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "        with:\n"
            "          persist-credentials: false\n"
            "      - uses: actions/setup-python@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
            "        with:\n"
            "          python-version-file: .python-version\n"
            "      - uses: astral-sh/setup-uv@cccccccccccccccccccccccccccccccccccccccc\n"
            "      - uses: actions/setup-node@dddddddddddddddddddddddddddddddddddddddd\n"
            "        with:\n"
            "          node-version-file: .node-version\n"
            "      - run: powershell.exe -NoProfile -ExecutionPolicy Bypass "
            "-File .\\scripts\\verify.ps1\n",
        )

    def _categories(self) -> set[str]:
        return {issue.category for issue in collect_issues(self.root)}

    def test_valid_project_passes(self) -> None:
        self.assertEqual(collect_issues(self.root), [])

    def test_broken_relative_link_fails(self) -> None:
        self._write("README.md", "# Project\n\n[Missing](./docs/missing.md)\n")
        self.assertIn("broken-relative-link", self._categories())

    def test_missing_required_document_fails(self) -> None:
        (self.root / "docs/architecture.md").unlink()
        self.assertIn("missing-required-document", self._categories())

    def test_non_empty_credential_assignment_fails_without_echoing_value(self) -> None:
        variable = "DEEPSEEK_API_" + "KEY"
        self._write(".env.example", f"{variable}=definitely-not-empty\n")
        issues = collect_issues(self.root)
        rendered = "\n".join(issue.render() for issue in issues)
        self.assertIn("possible-secret", {issue.category for issue in issues})
        self.assertNotIn("definitely-not-empty", rendered)

    def test_qweather_private_key_path_must_remain_empty_in_template(self) -> None:
        path = self.root / ".env.example"
        text = path.read_text(encoding="utf-8").replace(
            "QWEATHER_PRIVATE_KEY_PATH=",
            "QWEATHER_PRIVATE_KEY_PATH=C:/private/account.pem",
        )
        path.write_text(text, encoding="utf-8")

        self.assertIn("environment-template", self._categories())

    def test_deprecated_qweather_api_key_placeholder_fails(self) -> None:
        path = self.root / ".env.example"
        path.write_text(
            path.read_text(encoding="utf-8") + "QWEATHER_API_KEY=\n",
            encoding="utf-8",
        )

        self.assertIn("environment-template", self._categories())

    def test_step_drift_fails(self) -> None:
        self._write(
            "docs/project-management/progress.md",
            "# Progress\n\n- 下一批准动作：Step 2，Different\n",
        )
        self.assertIn("status-consistency", self._categories())

    def test_closed_task_state_allows_zero_active_roadmap_rows(self) -> None:
        self._write(
            "docs/project-management/current-task.md",
            "# Current Task\n\n当前无活动任务。\n",
        )
        self._write(
            "docs/project-management/implementation-plan.md",
            "# Plan\n\n当前无活动任务，因此没有正在执行的 Step。\n",
        )
        self._write(
            "docs/project-management/progress.md",
            "# Progress\n\n- 当前任务：无\n- 下一批准动作：用户从 roadmap 选择候选任务\n",
        )
        self._write(
            "docs/README.md",
            "# Docs\n\n- 当前活动任务：无\n- 下一步：等待用户从 roadmap 选择候选任务。\n",
        )
        self._write(
            "docs/project-management/roadmap.md",
            "# Roadmap\n\n| Priority | Task | Status | Goal | Dependency |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 0 | B-000 | DONE | Baseline | None |\n",
        )
        self.assertEqual(collect_issues(self.root), [])

    def test_closed_task_state_rejects_active_roadmap_row(self) -> None:
        self._write(
            "docs/project-management/current-task.md",
            "# Current Task\n\n当前无活动任务。\n",
        )
        self.assertIn("status-consistency", self._categories())

    def test_closed_task_state_rejects_stale_progress(self) -> None:
        self._write(
            "docs/project-management/current-task.md",
            "# Current Task\n\n当前无活动任务。\n",
        )
        self._write(
            "docs/project-management/implementation-plan.md",
            "# Plan\n\n当前无活动任务，因此没有正在执行的 Step。\n",
        )
        self._write(
            "docs/README.md",
            "# Docs\n\n- 当前活动任务：无\n",
        )
        self.assertIn("status-consistency", self._categories())

    def test_active_task_state_rejects_zero_active_roadmap_rows(self) -> None:
        self._write(
            "docs/project-management/roadmap.md",
            "# Roadmap\n\n| Priority | Task | Status | Goal | Dependency |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 0 | B-000 | DONE | Baseline | None |\n",
        )
        self.assertIn("status-consistency", self._categories())

    def test_active_task_state_accepts_a_non_baseline_task_id(self) -> None:
        self._write(
            "docs/README.md",
            "# Docs\n\n- 下一步：等待用户批准执行 F-001 Step 1。\n",
        )
        self._write(
            "docs/project-management/roadmap.md",
            "# Roadmap\n\n| Priority | Task | Status | Goal | Dependency |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 1 | F-001 | ACTIVE | Vertical slice | B-000 |\n",
        )
        self.assertEqual(collect_issues(self.root), [])

    def test_markdown_trailing_whitespace_fails(self) -> None:
        self._write("docs/product-brief.md", "# Product\n\nTrailing  \n")
        self.assertIn("trailing-whitespace", self._categories())

    def test_missing_ci_workflow_fails(self) -> None:
        (self.root / CI_WORKFLOW).unlink()
        self.assertIn("missing-required-project-file", self._categories())

    def test_ci_secret_reference_fails(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            'DEEPSEEK_API_KEY: ""',
            "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-secret-boundary", self._categories())

    def test_ci_action_requires_full_commit_sha(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            "actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "actions/checkout@v7",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-action-pin", self._categories())

    def test_ci_must_call_unified_verification(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            "-File .\\scripts\\verify.ps1",
            "-File .\\scripts\\other.ps1",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-contract", self._categories())

    def test_version_parser_accepts_ci_diagnostics_and_rejects_drift(self) -> None:
        verification_script = (SCRIPTS_DIR / "verify.ps1").read_text(encoding="utf-8")
        self.assertIn(
            "uv run --quiet --project backend --frozen python --version",
            verification_script,
        )
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPTS_DIR / "verify.ps1"),
                "-VersionParserSelfTest",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Version parser self-test passed.", result.stdout)

    def test_python_version_probe_runs_in_an_isolated_cold_environment(self) -> None:
        with tempfile.TemporaryDirectory() as environment:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPTS_DIR / "verify.ps1"),
                    "-PythonVersionProbe",
                ],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "UV_PROJECT_ENVIRONMENT": environment},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Python: Python 3.13.3", result.stdout)

    def test_ci_bracket_secret_reference_fails(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            'DEEPSEEK_API_KEY: ""',
            "DEEPSEEK_API_KEY: ${{ secrets['DEEPSEEK_API_KEY'] }}",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-secret-boundary", self._categories())

    def test_ci_job_write_all_permission_fails(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            "    runs-on: windows-latest",
            "    permissions: write-all\n    runs-on: windows-latest",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-permission-boundary", self._categories())

    def test_ci_local_or_docker_action_fails(self) -> None:
        path = self.root / CI_WORKFLOW
        text = path.read_text(encoding="utf-8").replace(
            "    steps:",
            "    steps:\n      - uses: docker://alpine:latest",
        )
        path.write_text(text, encoding="utf-8")
        self.assertIn("ci-contract", self._categories())

    def test_build_constraint_drift_fails(self) -> None:
        path = self.root / BUILD_CONSTRAINTS
        text = path.read_text(encoding="utf-8").replace("hatchling==1.32.0", "hatchling>=1.27")
        path.write_text(text, encoding="utf-8")
        self.assertIn("build-constraint", self._categories())


if __name__ == "__main__":
    unittest.main()
