"""Treat model text as untrusted data and admit only an exact local schema."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.application.ports import (
    CandidateActivity,
    CandidateDay,
    CandidateValidationCode,
    DeepSeekPort,
    ModelTextOutput,
    PlanCandidate,
    PlanCandidateRepairRequest,
    PlanningContext,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
)

MAX_MODEL_OUTPUT_LENGTH: Final = 32_000
_ROOT_FIELDS: Final = frozenset({"intent_summary", "days", "explanation", "warnings"})
_DAY_FIELDS: Final = frozenset({"local_date", "activities"})
_ACTIVITY_FIELDS: Final = frozenset(
    {"location_id", "local_date", "title", "start_time", "end_time", "source_ids"}
)
_UNSAFE_TEXT: Final = re.compile(
    r"ignore\s+(?:all\s+)?previous\s+instructions|<\|(?:system|assistant|tool)\|>|"
    r"assistant\s+to=|system\s+prompt|arbitrary_http",
    re.IGNORECASE,
)


class CandidateResolutionErrorCode(StrEnum):
    MODEL_OUTPUT_INVALID = "model_output_invalid"


class CandidateValidationError(ValueError):
    __slots__ = ("code", "repairable")

    def __init__(self, code: CandidateValidationCode, *, repairable: bool) -> None:
        self.code = code
        self.repairable = repairable
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    result: ProviderResult[PlanCandidate]
    repaired: bool
    error_code: CandidateResolutionErrorCode | None


class DeepSeekCandidateResolver:
    __slots__ = ("_deepseek",)

    def __init__(self, deepseek: DeepSeekPort) -> None:
        self._deepseek = deepseek

    async def resolve(
        self,
        context: PlanningContext,
        governor: ToolCallGovernor,
    ) -> CandidateResolution:
        generated = await _governed_model_call(
            governor,
            ToolCallCapability.GENERATE_PLAN_CANDIDATE,
            lambda: self._deepseek.generate_plan_candidate(context),
        )
        if generated.status is ProviderResultStatus.UNAVAILABLE:
            return CandidateResolution(_copy_unavailable(generated), False, None)

        generated_output = _require_model_output(generated)
        raw_output = generated_output.content
        try:
            if generated_output.truncated:
                raise CandidateValidationError(
                    CandidateValidationCode.OUTPUT_TRUNCATED,
                    repairable=True,
                )
            candidate = parse_plan_candidate(raw_output, context)
        except CandidateValidationError as first_error:
            if not first_error.repairable:
                return _invalid_resolution()
            validation_code = first_error.code
            repaired = await _governed_model_call(
                governor,
                ToolCallCapability.REPAIR_PLAN_CANDIDATE,
                lambda: self._deepseek.repair_plan_candidate(
                    PlanCandidateRepairRequest(context, raw_output, validation_code)
                ),
            )
            if repaired.status is ProviderResultStatus.UNAVAILABLE:
                return CandidateResolution(_copy_unavailable(repaired), True, None)
            repaired_output = _require_model_output(repaired)
            try:
                if repaired_output.truncated:
                    raise CandidateValidationError(
                        CandidateValidationCode.OUTPUT_TRUNCATED,
                        repairable=False,
                    )
                candidate = parse_plan_candidate(repaired_output.content, context)
            except CandidateValidationError:
                return _invalid_resolution(repaired=True)
            return CandidateResolution(_with_candidate(repaired, candidate), True, None)
        return CandidateResolution(_with_candidate(generated, candidate), False, None)


def parse_plan_candidate(raw_output: str, context: PlanningContext) -> PlanCandidate:
    if (
        not isinstance(raw_output, str)
        or not raw_output
        or len(raw_output) > MAX_MODEL_OUTPUT_LENGTH
    ):
        raise CandidateValidationError(CandidateValidationCode.JSON_INVALID, repairable=True)
    try:
        value = json.loads(raw_output, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, RecursionError):
        raise CandidateValidationError(
            CandidateValidationCode.JSON_INVALID,
            repairable=True,
        ) from None
    root = _exact_object(value, _ROOT_FIELDS)
    intent_summary = _safe_text(root["intent_summary"], max_length=120)
    explanation = _safe_text(root["explanation"], max_length=500)
    warnings = _string_tuple(root["warnings"], max_items=10, max_length=500)
    days_value = _list(root["days"], exact_length=2)

    allowed_locations = {item.location_id for item in context.locations}
    allowed_sources = set(context.activity_source_ids)
    expected_dates = (context.start_date, context.end_date)
    days = tuple(
        _parse_day(item, allowed_locations=allowed_locations, allowed_sources=allowed_sources)
        for item in days_value
    )
    if tuple(item.local_date for item in days) != expected_dates:
        raise CandidateValidationError(
            CandidateValidationCode.REFERENCE_INVALID,
            repairable=True,
        )
    return PlanCandidate(intent_summary, days, explanation, warnings)


def _parse_day(
    value: object,
    *,
    allowed_locations: set[UUID],
    allowed_sources: set[UUID],
) -> CandidateDay:
    item = _exact_object(value, _DAY_FIELDS)
    local_date = _date(item["local_date"])
    activities_value = _list(item["activities"], min_length=1, max_length=3)
    activities = tuple(
        _parse_activity(
            activity,
            parent_date=local_date,
            allowed_locations=allowed_locations,
            allowed_sources=allowed_sources,
        )
        for activity in activities_value
    )
    return CandidateDay(local_date, activities)


def _parse_activity(
    value: object,
    *,
    parent_date: date,
    allowed_locations: set[UUID],
    allowed_sources: set[UUID],
) -> CandidateActivity:
    item = _exact_object(value, _ACTIVITY_FIELDS)
    location_id = _uuid(item["location_id"])
    local_date = _date(item["local_date"])
    start_time = _time(item["start_time"])
    end_time = _time(item["end_time"])
    source_ids = _uuid_tuple(item["source_ids"], min_length=1, max_length=20)
    if (
        location_id not in allowed_locations
        or local_date != parent_date
        or any(source_id not in allowed_sources for source_id in source_ids)
    ):
        raise CandidateValidationError(
            CandidateValidationCode.REFERENCE_INVALID,
            repairable=True,
        )
    if end_time <= start_time:
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        )
    return CandidateActivity(
        location_id,
        local_date,
        _safe_text(item["title"], max_length=120),
        start_time,
        end_time,
        source_ids,
    )


def _exact_object(value: object, fields: frozenset[str]) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or not all(isinstance(key, str) for key in value)
    ):
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        )
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateValidationError(
                CandidateValidationCode.SCHEMA_INVALID,
                repairable=True,
            )
        value[key] = item
    return value


def _list(
    value: object,
    *,
    exact_length: int | None = None,
    min_length: int = 0,
    max_length: int = 100,
) -> list[object]:
    if (
        not isinstance(value, list)
        or (exact_length is not None and len(value) != exact_length)
        or not min_length <= len(value) <= max_length
    ):
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        )
    return value


def _safe_text(value: object, *, max_length: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > max_length
        or "\n" in value
        or "\r" in value
    ):
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        )
    if _UNSAFE_TEXT.search(value) is not None:
        raise CandidateValidationError(
            CandidateValidationCode.UNSAFE_TEXT,
            repairable=False,
        )
    return value


def _string_tuple(value: object, *, max_items: int, max_length: int) -> tuple[str, ...]:
    items = _list(value, max_length=max_items)
    return tuple(_safe_text(item, max_length=max_length) for item in items)


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        ) from None
    if parsed.isoformat() != value:
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    return parsed


def _time(value: object) -> time:
    if not isinstance(value, str):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        ) from None
    if parsed.tzinfo is not None or parsed.isoformat() != value:
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    return parsed


def _uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise CandidateValidationError(CandidateValidationCode.REFERENCE_INVALID, repairable=True)
    try:
        parsed = UUID(value)
    except ValueError:
        raise CandidateValidationError(
            CandidateValidationCode.REFERENCE_INVALID,
            repairable=True,
        ) from None
    if str(parsed) != value:
        raise CandidateValidationError(CandidateValidationCode.REFERENCE_INVALID, repairable=True)
    return parsed


def _uuid_tuple(value: object, *, min_length: int, max_length: int) -> tuple[UUID, ...]:
    items = _list(value, min_length=min_length, max_length=max_length)
    parsed = tuple(_uuid(item) for item in items)
    if len(set(parsed)) != len(parsed):
        raise CandidateValidationError(CandidateValidationCode.REFERENCE_INVALID, repairable=True)
    return parsed


async def _governed_model_call(
    governor: ToolCallGovernor,
    capability: ToolCallCapability,
    operation: Callable[[], Awaitable[ProviderResult[ModelTextOutput]]],
) -> ProviderResult[ModelTextOutput]:
    permit = governor.reserve(capability, PlanningStatus.PLANNING)
    result: ProviderResult[ModelTextOutput] | None = None
    try:
        result = await operation()
    finally:
        try:
            governor.complete(permit)
        except ToolCallGovernanceError as error:
            provider_timeout = (
                result is not None
                and result.error is not None
                and result.error.category is ProviderErrorCategory.TIMEOUT
            )
            if error.code is not ToolCallGovernanceErrorCode.CALL_TIMEOUT or not provider_timeout:
                raise
    assert result is not None
    return result


def _require_model_output(result: ProviderResult[ModelTextOutput]) -> ModelTextOutput:
    if result.data is None:
        raise AssertionError("available model result must contain data")
    return result.data


def _with_candidate(
    source: ProviderResult[ModelTextOutput],
    candidate: PlanCandidate,
) -> ProviderResult[PlanCandidate]:
    return ProviderResult(
        source.status,
        source.provider,
        candidate,
        source.fetched_at,
        source.valid_until,
        source.warnings,
        source.error,
        source.source_records,
    )


def _copy_unavailable(
    source: ProviderResult[ModelTextOutput],
) -> ProviderResult[PlanCandidate]:
    return ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        source.provider,
        None,
        None,
        None,
        source.warnings,
        source.error,
        (),
    )


def _invalid_resolution(*, repaired: bool = False) -> CandidateResolution:
    result: ProviderResult[PlanCandidate] = ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        Provider.DEEPSEEK,
        None,
        None,
        None,
        ("model candidate failed local validation",),
        ProviderError(ProviderErrorCategory.SCHEMA),
        (),
    )
    return CandidateResolution(
        result,
        repaired,
        CandidateResolutionErrorCode.MODEL_OUTPUT_INVALID,
    )
