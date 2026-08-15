"""Treat model text as untrusted data and admit only an exact local schema."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.application.ports import (
    CandidateActivity,
    CandidateDay,
    CandidateTimeFailureCode,
    CandidateValidationCode,
    DeepSeekPort,
    ModelTextOutput,
    PlanCandidate,
    PlanCandidateRepairRequest,
    PlanningContext,
    PlanningDayWindow,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    DailyRoutePlan,
    DomainInvariantError,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    RouteActivity,
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


class CandidateValidationStage(StrEnum):
    GENERATION = "generation"
    REPAIR = "repair"


class CandidateResolutionDiagnosticCode(StrEnum):
    LOCAL_VALIDATION_FAILED = "candidate_local_validation_failed"
    GENERATION_JSON_INVALID = "candidate_generation_json_invalid"
    GENERATION_SCHEMA_INVALID = "candidate_generation_schema_invalid"
    GENERATION_DATE_INVALID = "candidate_generation_date_invalid"
    GENERATION_TIME_INVALID = "candidate_generation_time_invalid"
    GENERATION_ACTIVITY_OUTSIDE_DAY_WINDOW = "candidate_generation_activity_outside_day_window"
    GENERATION_ACCOMMODATION_TO_FIRST_GAP_NOT_POSITIVE = (
        "candidate_generation_accommodation_to_first_gap_not_positive"
    )
    GENERATION_BETWEEN_LOCATIONS_GAP_NOT_POSITIVE = (
        "candidate_generation_between_locations_gap_not_positive"
    )
    GENERATION_LAST_TO_ACCOMMODATION_GAP_NOT_POSITIVE = (
        "candidate_generation_last_to_accommodation_gap_not_positive"
    )
    GENERATION_DAY_SCHEDULE_CAPACITY_EXCEEDED = (
        "candidate_generation_day_schedule_capacity_exceeded"
    )
    GENERATION_POI_REFERENCE_INVALID = "candidate_generation_poi_reference_invalid"
    GENERATION_SOURCE_REFERENCE_INVALID = "candidate_generation_source_reference_invalid"
    GENERATION_UNSAFE_TEXT = "candidate_generation_unsafe_text"
    GENERATION_OUTPUT_TRUNCATED = "candidate_generation_output_truncated"
    REPAIR_JSON_INVALID = "candidate_repair_json_invalid"
    REPAIR_SCHEMA_INVALID = "candidate_repair_schema_invalid"
    REPAIR_DATE_INVALID = "candidate_repair_date_invalid"
    REPAIR_TIME_INVALID = "candidate_repair_time_invalid"
    REPAIR_ACTIVITY_OUTSIDE_DAY_WINDOW = "candidate_repair_activity_outside_day_window"
    REPAIR_ACCOMMODATION_TO_FIRST_GAP_NOT_POSITIVE = (
        "candidate_repair_accommodation_to_first_gap_not_positive"
    )
    REPAIR_BETWEEN_LOCATIONS_GAP_NOT_POSITIVE = (
        "candidate_repair_between_locations_gap_not_positive"
    )
    REPAIR_LAST_TO_ACCOMMODATION_GAP_NOT_POSITIVE = (
        "candidate_repair_last_to_accommodation_gap_not_positive"
    )
    REPAIR_DAY_SCHEDULE_CAPACITY_EXCEEDED = "candidate_repair_day_schedule_capacity_exceeded"
    REPAIR_POI_REFERENCE_INVALID = "candidate_repair_poi_reference_invalid"
    REPAIR_SOURCE_REFERENCE_INVALID = "candidate_repair_source_reference_invalid"
    REPAIR_UNSAFE_TEXT = "candidate_repair_unsafe_text"
    REPAIR_OUTPUT_TRUNCATED = "candidate_repair_output_truncated"

    @classmethod
    def from_failure(
        cls,
        stage: CandidateValidationStage,
        code: CandidateValidationCode,
        time_failure: CandidateTimeFailureCode | None = None,
    ) -> CandidateResolutionDiagnosticCode:
        if code is CandidateValidationCode.TIME_INVALID and time_failure is not None:
            return cls(f"candidate_{stage.value}_{time_failure.value}")
        suffix = code.value.removeprefix("candidate_")
        return cls(f"candidate_{stage.value}_{suffix}")


class CandidateValidationError(ValueError):
    __slots__ = ("code", "repairable", "time_failure")

    def __init__(
        self,
        code: CandidateValidationCode,
        *,
        repairable: bool,
        time_failure: CandidateTimeFailureCode | None = None,
    ) -> None:
        self.code = code
        self.repairable = repairable
        self.time_failure = time_failure
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    result: ProviderResult[PlanCandidate]
    repaired: bool
    error_code: CandidateResolutionErrorCode | None
    validation_stage: CandidateValidationStage | None = None
    validation_code: CandidateValidationCode | None = None
    validation_time_failure: CandidateTimeFailureCode | None = None

    @property
    def diagnostic_code(self) -> CandidateResolutionDiagnosticCode | None:
        if self.validation_stage is None or self.validation_code is None:
            return None
        return CandidateResolutionDiagnosticCode.from_failure(
            self.validation_stage,
            self.validation_code,
            self.validation_time_failure,
        )


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
                return _invalid_resolution(
                    stage=CandidateValidationStage.GENERATION,
                    validation_code=first_error.code,
                    time_failure=first_error.time_failure,
                )
            validation_code = first_error.code
            time_failure = first_error.time_failure
            repaired = await _governed_model_call(
                governor,
                ToolCallCapability.REPAIR_PLAN_CANDIDATE,
                lambda: self._deepseek.repair_plan_candidate(
                    PlanCandidateRepairRequest(
                        context,
                        raw_output,
                        validation_code,
                        time_failure,
                    )
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
            except CandidateValidationError as repair_error:
                return _invalid_resolution(
                    stage=CandidateValidationStage.REPAIR,
                    validation_code=repair_error.code,
                    time_failure=repair_error.time_failure,
                    repaired=True,
                )
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
            CandidateValidationCode.DATE_INVALID,
            repairable=True,
        )
    candidate = PlanCandidate(intent_summary, days, explanation, warnings)
    _validate_route_windows(candidate, context)
    return candidate


def _validate_route_windows(candidate: PlanCandidate, context: PlanningContext) -> None:
    if context.accommodation is None or len(context.day_windows) != 2:
        return
    windows = {item.day_offset: item for item in context.day_windows}
    if set(windows) != {0, 1}:
        return
    try:
        for day_offset, day in enumerate(candidate.days):
            window = windows[day_offset]
            DailyRoutePlan(
                context.accommodation.location_id,
                DailyAvailability(day_offset, window.start_time, window.end_time),
                tuple(
                    RouteActivity(
                        uuid5(
                            NAMESPACE_URL,
                            f"candidate-route:{day_offset}:{index}:{activity.location_id}",
                        ),
                        activity.location_id,
                        activity.start_time,
                        activity.end_time,
                    )
                    for index, activity in enumerate(day.activities)
                ),
                (),
            ).expected_legs()
    except DomainInvariantError as error:
        raise CandidateValidationError(
            CandidateValidationCode.TIME_INVALID,
            repairable=True,
            time_failure=_classify_route_time_failure(
                error,
                day=day,
                window=window,
                accommodation_location_id=context.accommodation.location_id,
            ),
        ) from None


def _classify_route_time_failure(
    error: DomainInvariantError,
    *,
    day: CandidateDay,
    window: PlanningDayWindow,
    accommodation_location_id: UUID,
) -> CandidateTimeFailureCode | None:
    if error.code == "activity_outside_day_window":
        return CandidateTimeFailureCode.ACTIVITY_OUTSIDE_DAY_WINDOW
    if error.code == "activity_visit_order_invalid":
        return CandidateTimeFailureCode.DAY_SCHEDULE_CAPACITY_EXCEEDED
    if error.code != "route_gap_not_positive":
        return None

    previous_location_id = accommodation_location_id
    previous_end = window.start_time
    for index, activity in enumerate(day.activities):
        if previous_location_id != activity.location_id and activity.start_time <= previous_end:
            if index == 0:
                return CandidateTimeFailureCode.ACCOMMODATION_TO_FIRST_GAP_NOT_POSITIVE
            return CandidateTimeFailureCode.BETWEEN_LOCATIONS_GAP_NOT_POSITIVE
        previous_location_id = activity.location_id
        previous_end = activity.end_time
    if previous_location_id != accommodation_location_id and window.end_time <= previous_end:
        return CandidateTimeFailureCode.LAST_TO_ACCOMMODATION_GAP_NOT_POSITIVE
    return None


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
    location_id = _uuid(
        item["location_id"],
        invalid_code=CandidateValidationCode.POI_REFERENCE_INVALID,
    )
    local_date = _date(item["local_date"])
    start_time = _time(item["start_time"])
    end_time = _time(item["end_time"])
    source_ids = _uuid_tuple(
        item["source_ids"],
        min_length=1,
        max_length=20,
        invalid_code=CandidateValidationCode.SOURCE_REFERENCE_INVALID,
    )
    if location_id not in allowed_locations:
        raise CandidateValidationError(
            CandidateValidationCode.POI_REFERENCE_INVALID,
            repairable=True,
        )
    if local_date != parent_date:
        raise CandidateValidationError(
            CandidateValidationCode.DATE_INVALID,
            repairable=True,
        )
    if any(source_id not in allowed_sources for source_id in source_ids):
        raise CandidateValidationError(
            CandidateValidationCode.SOURCE_REFERENCE_INVALID,
            repairable=True,
        )
    if end_time <= start_time:
        raise CandidateValidationError(
            CandidateValidationCode.TIME_INVALID,
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
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise CandidateValidationError(
            CandidateValidationCode.DATE_INVALID,
            repairable=True,
        ) from None
    if parsed.isoformat() != value:
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    return parsed


def _time(value: object) -> time:
    if not isinstance(value, str):
        raise CandidateValidationError(CandidateValidationCode.TIME_INVALID, repairable=True)
    try:
        parsed = time.fromisoformat(value)
    except ValueError:
        raise CandidateValidationError(
            CandidateValidationCode.TIME_INVALID,
            repairable=True,
        ) from None
    if parsed.tzinfo is not None or parsed.microsecond != 0 or parsed.isoformat() != value:
        raise CandidateValidationError(CandidateValidationCode.TIME_INVALID, repairable=True)
    return parsed


def _uuid(value: object, *, invalid_code: CandidateValidationCode) -> UUID:
    if not isinstance(value, str):
        raise CandidateValidationError(invalid_code, repairable=True)
    try:
        parsed = UUID(value)
    except ValueError:
        raise CandidateValidationError(invalid_code, repairable=True) from None
    if str(parsed) != value:
        raise CandidateValidationError(invalid_code, repairable=True)
    return parsed


def _uuid_tuple(
    value: object,
    *,
    min_length: int,
    max_length: int,
    invalid_code: CandidateValidationCode,
) -> tuple[UUID, ...]:
    items = _list(value, min_length=min_length, max_length=max_length)
    parsed = tuple(_uuid(item, invalid_code=invalid_code) for item in items)
    if len(set(parsed)) != len(parsed):
        raise CandidateValidationError(invalid_code, repairable=True)
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


def _invalid_resolution(
    *,
    stage: CandidateValidationStage,
    validation_code: CandidateValidationCode,
    time_failure: CandidateTimeFailureCode | None = None,
    repaired: bool = False,
) -> CandidateResolution:
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
        stage,
        validation_code,
        time_failure,
    )
