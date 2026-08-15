"""Prevent framework and infrastructure imports from entering the domain package."""

import ast
from pathlib import Path

DOMAIN_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "intelligent_travel_assistant" / "domain"
)
FORBIDDEN_ROOTS = {
    "fastapi",
    "httpx",
    "httpx2",
    "openai",
    "pydantic",
    "pydantic_settings",
    "requests",
    "sqlalchemy",
    "sqlite3",
}


def test_domain_package_uses_only_approved_dependency_roots() -> None:
    observed_forbidden: list[str] = []

    for path in DOMAIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: tuple[str, ...]
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                continue
            for module in modules:
                if module.split(".", 1)[0] in FORBIDDEN_ROOTS:
                    observed_forbidden.append(f"{path.name}:{module}")

    assert observed_forbidden == []
