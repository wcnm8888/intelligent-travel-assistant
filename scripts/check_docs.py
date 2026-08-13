"""Validate project documentation and repository safety contracts."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

REQUIRED_DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/product-brief.md",
    "docs/architecture.md",
    "docs/tech-stack.md",
    "docs/design-spec.md",
    "docs/agent-domain-spec.md",
    "docs/testing-strategy.md",
    "docs/decisions.md",
    "docs/project-management/roadmap.md",
    "docs/project-management/current-task.md",
    "docs/project-management/implementation-plan.md",
    "docs/project-management/progress.md",
    "docs/project-management/evidence.md",
)

CI_WORKFLOW = ".github/workflows/ci.yml"
EXPECTED_CI_ACTIONS = {
    "actions/checkout",
    "actions/setup-node",
    "actions/setup-python",
    "astral-sh/setup-uv",
}
PROVIDER_CREDENTIALS = (
    "AMAP_API_KEY",
    "DEEPSEEK_API_KEY",
    "QWEATHER_API_KEY",
)

IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "output",
}

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}

TEXT_FILENAMES = {
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    ".node-version",
    ".npmrc",
    ".python-version",
}

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")
HEADING_ONE = re.compile(r"^#\s+\S", re.MULTILINE)
STEP_ROW = re.compile(
    r"^\|\s*Step\s+(?P<step>\d+)\s*\|.*\|\s*(?P<status>DONE|TODO)\s*\|$", re.MULTILINE
)
ENV_CREDENTIAL = re.compile(
    r"^[ \t]*[A-Z][A-Z0-9_]*?(?:API_KEY|TOKEN|SECRET|PASSWORD)[ \t]*="
    r"[ \t]*(?P<value>[^#\r\n]*?)[ \t]*\r?$",
    re.MULTILINE,
)
PRIVATE_KEY_MARKER = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
TOKEN_PREFIX = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
ACTION_USE = re.compile(
    r"^[ \t]*(?:-[ \t]*)?uses:[ \t]*"
    r"(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(?P<ref>\S+)",
    re.MULTILINE,
)
FULL_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, slots=True)
class Issue:
    category: str
    path: str
    message: str

    def render(self) -> str:
        location = f" [{self.path}]" if self.path else ""
        return f"{self.category}{location}: {self.message}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, child_directories, filenames in os.walk(root):
        child_directories[:] = [
            name for name in child_directories if name not in IGNORED_DIRECTORIES
        ]
        parent = Path(directory)
        for filename in filenames:
            files.append(parent / filename)
    return sorted(files)


def _project_text_files(root: Path) -> list[Path]:
    return [
        path
        for path in _project_files(root)
        if not (path.name.startswith(".env") and path.name != ".env.example")
        and (path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_FILENAMES)
    ]


def _link_path(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]

    if target.startswith(("#", "http://", "https://", "mailto:")):
        return None

    without_fragment = target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]
    return unquote(without_fragment) or None


def check_required_documents(root: Path) -> list[Issue]:
    return [
        Issue("missing-required-document", relative, "required document does not exist")
        for relative in REQUIRED_DOCUMENTS
        if not (root / relative).is_file()
    ]


def check_markdown(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in (candidate for candidate in _project_files(root) if candidate.suffix == ".md"):
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        text = _read_text(path)
        if len(HEADING_ONE.findall(text)) != 1:
            issues.append(
                Issue("markdown-structure", relative, "expected exactly one level-one heading")
            )

        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.endswith((" ", "\t")):
                issues.append(
                    Issue(
                        "trailing-whitespace",
                        relative,
                        f"line {line_number} has trailing whitespace",
                    )
                )

        for match in MARKDOWN_LINK.finditer(text):
            link_path = _link_path(match.group("target"))
            if link_path is None:
                continue
            resolved = (path.parent / link_path).resolve()
            if not resolved.exists():
                issues.append(
                    Issue("broken-relative-link", relative, f"target does not exist: {link_path}")
                )
    return issues


def check_text_files(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _project_text_files(root):
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(Issue("text-encoding", relative, "file is not valid UTF-8"))
            continue

        if raw and not raw.endswith(b"\n"):
            issues.append(Issue("final-newline", relative, "file must end with a newline"))

        for match in ENV_CREDENTIAL.finditer(text):
            if match.group("value").strip().strip("\"'"):
                line = text.count("\n", 0, match.start()) + 1
                issues.append(
                    Issue(
                        "possible-secret",
                        relative,
                        f"line {line} contains a non-empty credential assignment",
                    )
                )

        if PRIVATE_KEY_MARKER.search(text) or TOKEN_PREFIX.search(text):
            issues.append(
                Issue(
                    "possible-secret",
                    relative,
                    "contains a private-key marker or provider token prefix",
                )
            )
    return issues


def _extract_step(text: str, pattern: str, source: str) -> tuple[int | None, Issue | None]:
    match = re.search(pattern, text)
    if match is None:
        return None, Issue("status-consistency", source, "cannot determine the current Step")
    return int(match.group(1)), None


def check_status_consistency(root: Path) -> list[Issue]:
    sources = {
        "current-task": (
            "docs/project-management/current-task.md",
            r"当前 Step：`Step (\d+) -",
        ),
        "implementation-plan": (
            "docs/project-management/implementation-plan.md",
            r"等待用户批准 Step (\d+)",
        ),
        "progress": ("docs/project-management/progress.md", r"下一批准动作：Step (\d+)"),
        "docs-map": ("docs/README.md", r"等待用户批准执行 B-000 Step (\d+)"),
    }

    issues: list[Issue] = []
    steps: dict[str, int] = {}
    for name, (relative, pattern) in sources.items():
        path = root / relative
        if not path.is_file():
            continue
        step, issue = _extract_step(_read_text(path), pattern, relative)
        if issue is not None:
            issues.append(issue)
        elif step is not None:
            steps[name] = step

    if len(set(steps.values())) > 1:
        summary = ", ".join(f"{name}=Step {step}" for name, step in sorted(steps.items()))
        issues.append(
            Issue("status-consistency", "", f"current Step differs across documents: {summary}")
        )

    current_step = steps.get("current-task")
    task_path = root / "docs/project-management/current-task.md"
    if current_step is not None and task_path.is_file():
        rows = {
            int(match.group("step")): match.group("status")
            for match in STEP_ROW.finditer(_read_text(task_path))
        }
        for step in range(current_step):
            if rows.get(step) != "DONE":
                issues.append(
                    Issue(
                        "status-consistency",
                        task_path.relative_to(root).as_posix(),
                        f"Step {step} must be DONE",
                    )
                )
        if rows.get(current_step) != "TODO":
            issues.append(
                Issue(
                    "status-consistency",
                    task_path.relative_to(root).as_posix(),
                    f"current Step {current_step} must be TODO",
                )
            )

    roadmap = root / "docs/project-management/roadmap.md"
    if roadmap.is_file():
        active_rows = re.findall(r"^\|[^\n]*\|\s*ACTIVE\s*\|", _read_text(roadmap), re.MULTILINE)
        if len(active_rows) != 1:
            issues.append(
                Issue(
                    "status-consistency",
                    roadmap.relative_to(root).as_posix(),
                    "expected exactly one ACTIVE roadmap row",
                )
            )
    return issues


def _git_check_ignore(root: Path, relative: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def check_ignore_contract(root: Path) -> list[Issue]:
    if not (root / ".git").is_dir():
        return []

    issues: list[Issue] = []
    for relative in (
        ".env.local",
        ".playwright-cli/session.json",
        "backend/.venv/pyvenv.cfg",
        "frontend/dist/index.html",
        "node_modules/package/index.js",
        "output/playwright/screenshot.png",
    ):
        if not _git_check_ignore(root, relative):
            issues.append(
                Issue("ignore-contract", relative, "local artifact must be ignored by Git")
            )

    if _git_check_ignore(root, ".env.example"):
        issues.append(
            Issue("ignore-contract", ".env.example", "credential template must remain committable")
        )
    return issues


def check_ci_contract(root: Path) -> list[Issue]:
    path = root / CI_WORKFLOW
    if not path.is_file():
        return [
            Issue(
                "missing-required-project-file",
                CI_WORKFLOW,
                "required CI workflow does not exist",
            )
        ]

    text = _read_text(path)
    issues: list[Issue] = []

    required_fragments = {
        "pull request trigger": "  pull_request:",
        "main push trigger": "  push:",
        "manual trigger": "  workflow_dispatch:",
        "read-only permissions": "  contents: read",
        "disabled checkout credentials": "          persist-credentials: false",
        "Windows runner": "    runs-on: windows-latest",
        "job timeout": "    timeout-minutes:",
        "Python version file": "          python-version-file: .python-version",
        "Node version file": "          node-version-file: .node-version",
        "frozen local verification entrypoint": (
            "run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\verify.ps1"
        ),
    }
    for label, fragment in required_fragments.items():
        if fragment not in text:
            issues.append(Issue("ci-contract", CI_WORKFLOW, f"missing required {label}"))

    if re.search(r"(?i)\bsecrets\s*\.", text):
        issues.append(
            Issue(
                "ci-secret-boundary",
                CI_WORKFLOW,
                "default CI must not reference GitHub Secrets",
            )
        )

    if re.search(r"(?im)^permissions:\s*write-all\s*$|^[ \t]+[\w-]+:\s*write\s*$", text):
        issues.append(
            Issue(
                "ci-permission-boundary",
                CI_WORKFLOW,
                "default CI permissions must remain read-only",
            )
        )

    for variable in PROVIDER_CREDENTIALS:
        empty_assignment = re.compile(
            rf"^[ \t]+{re.escape(variable)}:[ \t]*(?:\"\"|'')[ \t]*$",
            re.MULTILINE,
        )
        if not empty_assignment.search(text):
            issues.append(
                Issue(
                    "ci-secret-boundary",
                    CI_WORKFLOW,
                    f"{variable} must be explicitly empty in default CI",
                )
            )

    action_uses = list(ACTION_USE.finditer(text))
    observed_actions = {match.group("action") for match in action_uses}
    for action in sorted(EXPECTED_CI_ACTIONS - observed_actions):
        issues.append(Issue("ci-contract", CI_WORKFLOW, f"missing required action: {action}"))
    for action in sorted(observed_actions - EXPECTED_CI_ACTIONS):
        issues.append(
            Issue("ci-contract", CI_WORKFLOW, f"unexpected action in baseline CI: {action}")
        )
    for match in action_uses:
        action = match.group("action")
        reference = match.group("ref")
        if FULL_COMMIT_SHA.fullmatch(reference) is None:
            issues.append(
                Issue(
                    "ci-action-pin",
                    CI_WORKFLOW,
                    f"{action} must be pinned to a full commit SHA",
                )
            )

    return issues


def collect_issues(root: Path) -> list[Issue]:
    return [
        *check_required_documents(root),
        *check_markdown(root),
        *check_text_files(root),
        *check_status_consistency(root),
        *check_ignore_contract(root),
        *check_ci_contract(root),
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="project root to validate (defaults to the parent of scripts/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    issues = collect_issues(root)
    if issues:
        print(f"Documentation checks failed with {len(issues)} issue(s):", file=sys.stderr)
        for issue in issues:
            print(f"- {issue.render()}", file=sys.stderr)
        return 1

    markdown_count = sum(1 for path in _project_files(root) if path.suffix == ".md")
    print(
        f"Documentation checks passed: {len(REQUIRED_DOCUMENTS)} required documents, "
        f"{markdown_count} Markdown files, CI, status and safety contracts valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
