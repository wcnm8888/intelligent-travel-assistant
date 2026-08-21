"""Strict typed values for the fixed F-005 offline evaluation suite."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class EvalSlice(StrEnum):
    LEGACY = "legacy"
    V2 = "v2"
    V3 = "v3"
    F003 = "f003"


class EvalCategory(StrEnum):
    NORMAL = "normal"
    PROVIDER_FAILURE = "provider_failure"
    FRESHNESS = "freshness"
    SECURITY = "security"


class EvalScenario(StrEnum):
    NORMAL = "normal"
    BOUNDARY = "boundary"
    CONFLICT = "conflict"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_SCHEMA = "provider_schema"
    STALE = "stale"
    UNKNOWN_VALIDITY = "unknown_validity"
    UNKNOWN_COST = "unknown_cost"
    INJECTION = "injection"
    SOURCE_FORGERY = "source_forgery"
    TOOL_OVERRIDE = "tool_override"


class EvalTerminal(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    FAILED = "failed"


_CASE_FIELDS: Final = frozenset(
    {
        "id",
        "slice",
        "category",
        "scenario",
        "terminal",
        "allowed_source_ids",
        "selected_source_ids",
        "model_fields",
        "model_text",
        "logical_calls",
        "http_attempts",
        "logical_budget",
        "attempt_budget",
        "requested_extra_calls",
    }
)


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    slice: EvalSlice
    category: EvalCategory
    scenario: EvalScenario
    terminal: EvalTerminal
    allowed_source_ids: tuple[str, ...]
    selected_source_ids: tuple[str, ...]
    model_fields: tuple[str, ...]
    model_text: str
    logical_calls: int
    http_attempts: int
    logical_budget: int
    attempt_budget: int
    requested_extra_calls: int

    @classmethod
    def from_json(cls, value: object) -> EvalCase:
        if not isinstance(value, dict) or set(value) != _CASE_FIELDS:
            raise ValueError("eval_case_shape_invalid")
        case_id = _safe_id(value["id"])
        string_lists = {
            field: _string_tuple(value[field], field=field)
            for field in (
                "allowed_source_ids",
                "selected_source_ids",
                "model_fields",
            )
        }
        model_text = value["model_text"]
        if (
            not isinstance(model_text, str)
            or not model_text
            or len(model_text) > 240
            or "\n" in model_text
            or "\r" in model_text
        ):
            raise ValueError("eval_model_text_invalid")
        integers = {
            field: _nonnegative_int(value[field], field=field)
            for field in (
                "logical_calls",
                "http_attempts",
                "logical_budget",
                "attempt_budget",
                "requested_extra_calls",
            )
        }
        if integers["logical_budget"] != 2 or integers["attempt_budget"] != 2:
            raise ValueError("eval_case_budget_invalid")
        scenario = EvalScenario(value["scenario"])
        category = EvalCategory(value["category"])
        expected_calls = (
            2 if scenario in {EvalScenario.SOURCE_FORGERY, EvalScenario.TOOL_OVERRIDE} else 1
        )
        if (
            integers["logical_calls"] != expected_calls
            or integers["http_attempts"] != expected_calls
        ):
            raise ValueError("eval_case_expected_calls_invalid")
        expected_extra_calls = 99 if category is EvalCategory.SECURITY else 0
        if integers["requested_extra_calls"] != expected_extra_calls:
            raise ValueError("eval_case_requested_extra_calls_invalid")
        return cls(
            case_id,
            EvalSlice(value["slice"]),
            category,
            scenario,
            EvalTerminal(value["terminal"]),
            string_lists["allowed_source_ids"],
            string_lists["selected_source_ids"],
            string_lists["model_fields"],
            model_text,
            integers["logical_calls"],
            integers["http_attempts"],
            integers["logical_budget"],
            integers["attempt_budget"],
            integers["requested_extra_calls"],
        )


@dataclass(frozen=True, slots=True)
class EvalSuite:
    suite_version: str
    cases: tuple[EvalCase, ...]

    @classmethod
    def from_json(cls, value: object) -> EvalSuite:
        if not isinstance(value, dict) or set(value) != {"suite_version", "cases"}:
            raise ValueError("eval_suite_shape_invalid")
        if value["suite_version"] != "f005-v1":
            raise ValueError("eval_suite_version_invalid")
        raw_cases = value["cases"]
        if not isinstance(raw_cases, list):
            raise ValueError("eval_cases_invalid")
        cases = tuple(EvalCase.from_json(item) for item in raw_cases)
        if len({item.case_id for item in cases}) != len(cases):
            raise ValueError("eval_case_id_duplicate")
        return cls("f005-v1", cases)


def _safe_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 80
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in value)
    ):
        raise ValueError("eval_case_id_invalid")
    return value


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, str) and item and len(item) <= 80 for item in value)
        or len(value) > 20
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"eval_{field}_invalid")
    return tuple(value)


def _nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"eval_{field}_invalid")
    return value
