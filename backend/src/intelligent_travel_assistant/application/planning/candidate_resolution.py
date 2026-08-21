"""Treat model text as untrusted data and admit only an exact local schema."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, time, timedelta
from enum import StrEnum
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.application.ports import (
    ActivityDurationClass,
    ActivitySelection,
    ActivitySelectionKind,
    CandidateActivity,
    CandidateDay,
    CandidateTimeFailureCode,
    CandidateValidationCode,
    DeepSeekPort,
    ModelTextOutput,
    PlanCandidate,
    PlanningContext,
    PlanningDayWindow,
    PlanProposal,
    PlanRepairBrief,
    PlanRepairLocation,
    ProposalDay,
    bounded_display_label,
    bounded_project_token,
)
from intelligent_travel_assistant.application.tooling import (
    ProviderAttemptRuntime,
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
    provider_result_from_attempt_outcome,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    DailyRoutePlan,
    DomainInvariantError,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderOperation,
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
_PROPOSAL_DAY_FIELDS: Final = frozenset({"local_date", "selections"})
_MULTICITY_PROPOSAL_DAY_FIELDS: Final = frozenset(
    {
        "local_date",
        "departure_city_index",
        "arrival_city_index",
        "overnight_city_index",
        "selections",
    }
)
_SELECTION_FIELDS: Final = frozenset(
    {
        "location_id",
        "local_date",
        "title",
        "priority_rank",
        "selection_kind",
        "duration_class",
        "source_ids",
    }
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


@dataclass(frozen=True, slots=True)
class ProposalResolution:
    result: ProviderResult[PlanProposal]
    repaired: bool
    error_code: CandidateResolutionErrorCode | None
    validation_stage: CandidateValidationStage | None = None
    validation_code: CandidateValidationCode | None = None

    @property
    def diagnostic_code(self) -> CandidateResolutionDiagnosticCode | None:
        if self.validation_stage is None or self.validation_code is None:
            return None
        return CandidateResolutionDiagnosticCode.from_failure(
            self.validation_stage,
            self.validation_code,
        )


class DeepSeekCandidateResolver:
    __slots__ = ("_deepseek",)

    def __init__(self, deepseek: DeepSeekPort) -> None:
        self._deepseek = deepseek

    async def resolve(
        self,
        context: PlanningContext,
        governor: ToolCallGovernor,
        attempt_runtime: ProviderAttemptRuntime | None = None,
    ) -> CandidateResolution:
        generated = await _governed_model_call(
            governor,
            ToolCallCapability.GENERATE_PLAN_CANDIDATE,
            lambda: self._deepseek.generate_plan_candidate(context),
            attempt_runtime=attempt_runtime,
            provider_operation=ProviderOperation.GENERATE_PLAN_CANDIDATE,
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
                    _repair_brief(context, validation_code, time_failure)
                ),
                attempt_runtime=attempt_runtime,
                provider_operation=ProviderOperation.REPAIR_PLAN_CANDIDATE,
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


class DeepSeekProposalResolver:
    """Admit only an unordered-time proposal and perform at most one repair."""

    __slots__ = ("_deepseek",)

    def __init__(self, deepseek: DeepSeekPort) -> None:
        self._deepseek = deepseek

    async def resolve(
        self,
        context: PlanningContext,
        governor: ToolCallGovernor,
        attempt_runtime: ProviderAttemptRuntime | None = None,
    ) -> ProposalResolution:
        generated = await _governed_model_call(
            governor,
            ToolCallCapability.GENERATE_PLAN_CANDIDATE,
            lambda: self._deepseek.generate_plan_candidate(context),
            attempt_runtime=attempt_runtime,
            provider_operation=ProviderOperation.GENERATE_PLAN_CANDIDATE,
        )
        if generated.status is ProviderResultStatus.UNAVAILABLE:
            return ProposalResolution(_copy_proposal_unavailable(generated), False, None)

        generated_output = _require_model_output(generated)
        raw_output = generated_output.content
        try:
            if generated_output.truncated:
                raise CandidateValidationError(
                    CandidateValidationCode.OUTPUT_TRUNCATED,
                    repairable=True,
                )
            proposal = parse_plan_proposal(raw_output, context)
        except CandidateValidationError as first_error:
            if not first_error.repairable:
                return _invalid_proposal_resolution(
                    CandidateValidationStage.GENERATION,
                    first_error.code,
                )
            validation_code = first_error.code
            repaired = await _governed_model_call(
                governor,
                ToolCallCapability.REPAIR_PLAN_CANDIDATE,
                lambda: self._deepseek.repair_plan_candidate(
                    _repair_brief(context, validation_code)
                ),
                attempt_runtime=attempt_runtime,
                provider_operation=ProviderOperation.REPAIR_PLAN_CANDIDATE,
            )
            if repaired.status is ProviderResultStatus.UNAVAILABLE:
                return ProposalResolution(_copy_proposal_unavailable(repaired), True, None)
            repaired_output = _require_model_output(repaired)
            try:
                if repaired_output.truncated:
                    raise CandidateValidationError(
                        CandidateValidationCode.OUTPUT_TRUNCATED,
                        repairable=False,
                    )
                proposal = parse_plan_proposal(repaired_output.content, context)
            except CandidateValidationError as repair_error:
                return _invalid_proposal_resolution(
                    CandidateValidationStage.REPAIR,
                    repair_error.code,
                    repaired=True,
                )
            return ProposalResolution(_with_proposal(repaired, proposal), True, None)
        return ProposalResolution(_with_proposal(generated, proposal), False, None)


def _repair_brief(
    context: PlanningContext,
    validation_code: CandidateValidationCode,
    time_failure: CandidateTimeFailureCode | None = None,
) -> PlanRepairBrief:
    return PlanRepairBrief(
        request_version=context.request_version,
        expected_dates=_expected_dates(context),
        day_windows=context.day_windows,
        day_city_indices=context.day_city_indices,
        city_adcodes=context.city_adcodes,
        locations=tuple(
            PlanRepairLocation(
                location.location_id,
                bounded_display_label(f"location:{location.location_id}"),
                bounded_project_token(location.category),
                location.city_adcode,
            )
            for location in context.locations
        ),
        activity_source_ids=context.activity_source_ids,
        validation_code=validation_code,
        validation_time_failure=time_failure,
    )


def parse_plan_proposal(raw_output: str, context: PlanningContext) -> PlanProposal:
    """Parse the exact LLM proposal boundary; execution facts are forbidden extras."""

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
    expected_dates = _expected_dates(context)
    days_value = _list(root["days"], exact_length=len(expected_dates))
    locations = {item.location_id: item for item in context.locations}
    allowed_locations = set(locations)
    allowed_sources = set(context.activity_source_ids)
    days = tuple(
        _parse_proposal_day(
            item,
            allowed_locations=allowed_locations,
            allowed_sources=allowed_sources,
            location_city_adcodes={key: value.city_adcode for key, value in locations.items()},
            context=context,
            day_offset=day_offset,
        )
        for day_offset, item in enumerate(days_value)
    )
    if tuple(item.local_date for item in days) != expected_dates:
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    return PlanProposal(
        _safe_text(root["intent_summary"], max_length=120),
        days,
        _safe_text(root["explanation"], max_length=500),
        _string_tuple(root["warnings"], max_items=10, max_length=500),
    )


def _parse_proposal_day(
    value: object,
    *,
    allowed_locations: set[UUID],
    allowed_sources: set[UUID],
    location_city_adcodes: dict[UUID, str],
    context: PlanningContext,
    day_offset: int,
) -> ProposalDay:
    is_multicity = context.request_version == "3"
    item = _exact_object(
        value,
        _MULTICITY_PROPOSAL_DAY_FIELDS if is_multicity else _PROPOSAL_DAY_FIELDS,
    )
    local_date = _date(item["local_date"])
    minimum = 0 if is_multicity else 1
    maximum = 1 if is_multicity and _is_transfer_day(context, day_offset) else 2
    selections = tuple(
        _parse_selection(
            selection,
            parent_date=local_date,
            allowed_locations=allowed_locations,
            allowed_sources=allowed_sources,
        )
        for selection in _list(item["selections"], min_length=minimum, max_length=maximum)
    )
    if tuple(selection.priority_rank for selection in selections) != tuple(
        range(1, len(selections) + 1)
    ):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    if not is_multicity:
        return ProposalDay(local_date, selections)
    if day_offset >= len(context.day_city_indices):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    indices = tuple(
        item[field]
        for field in (
            "departure_city_index",
            "arrival_city_index",
            "overnight_city_index",
        )
    )
    if (
        any(type(index) is not int for index in indices)
        or indices != context.day_city_indices[day_offset]
    ):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    allowed_city_adcodes = {context.city_adcodes[indices[0]], context.city_adcodes[indices[1]]}
    if any(
        location_city_adcodes[item.location_id] not in allowed_city_adcodes for item in selections
    ):
        raise CandidateValidationError(
            CandidateValidationCode.POI_REFERENCE_INVALID,
            repairable=True,
        )
    return ProposalDay(local_date, selections, *indices)


def _is_transfer_day(context: PlanningContext, day_offset: int) -> bool:
    if day_offset >= len(context.day_city_indices):
        return False
    departure, arrival, _overnight = context.day_city_indices[day_offset]
    return departure != arrival


def _parse_selection(
    value: object,
    *,
    parent_date: date,
    allowed_locations: set[UUID],
    allowed_sources: set[UUID],
) -> ActivitySelection:
    item = _exact_object(value, _SELECTION_FIELDS)
    location_id = _uuid(
        item["location_id"],
        invalid_code=CandidateValidationCode.POI_REFERENCE_INVALID,
    )
    if location_id not in allowed_locations:
        raise CandidateValidationError(
            CandidateValidationCode.POI_REFERENCE_INVALID,
            repairable=True,
        )
    local_date = _date(item["local_date"])
    if local_date != parent_date:
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    source_ids = _uuid_tuple(
        item["source_ids"],
        min_length=1,
        max_length=20,
        invalid_code=CandidateValidationCode.SOURCE_REFERENCE_INVALID,
    )
    if any(source_id not in allowed_sources for source_id in source_ids):
        raise CandidateValidationError(
            CandidateValidationCode.SOURCE_REFERENCE_INVALID,
            repairable=True,
        )
    priority_rank = item["priority_rank"]
    if (
        not isinstance(priority_rank, int)
        or isinstance(priority_rank, bool)
        or priority_rank not in (1, 2)
    ):
        raise CandidateValidationError(CandidateValidationCode.SCHEMA_INVALID, repairable=True)
    selection_kind_value = item["selection_kind"]
    duration_class_value = item["duration_class"]
    if not isinstance(selection_kind_value, str) or not isinstance(duration_class_value, str):
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        )
    try:
        selection_kind = ActivitySelectionKind(selection_kind_value)
        duration_class = ActivityDurationClass(duration_class_value)
    except (TypeError, ValueError):
        raise CandidateValidationError(
            CandidateValidationCode.SCHEMA_INVALID,
            repairable=True,
        ) from None
    return ActivitySelection(
        location_id,
        local_date,
        _safe_text(item["title"], max_length=120),
        priority_rank,
        selection_kind,
        duration_class,
        source_ids,
    )


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
    expected_dates = _expected_dates(context)
    days_value = _list(root["days"], exact_length=len(expected_dates))

    allowed_locations = {item.location_id for item in context.locations}
    allowed_sources = set(context.activity_source_ids)
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
    expected_dates = _expected_dates(context)
    if context.accommodation is None or len(context.day_windows) != len(expected_dates):
        return
    windows = {item.day_offset: item for item in context.day_windows}
    if set(windows) != set(range(len(expected_dates))):
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


def _expected_dates(context: PlanningContext) -> tuple[date, ...]:
    day_count = (context.end_date - context.start_date).days + 1
    if not 2 <= day_count <= 7:
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    derived = tuple(context.start_date + timedelta(days=offset) for offset in range(day_count))
    if context.request_version is None:
        if day_count != 2 or (context.expected_dates and context.expected_dates != derived):
            raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
        return derived
    if context.request_version not in {"2", "3"} or context.expected_dates != derived:
        raise CandidateValidationError(CandidateValidationCode.DATE_INVALID, repairable=True)
    return derived


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
    *,
    attempt_runtime: ProviderAttemptRuntime | None = None,
    provider_operation: ProviderOperation,
) -> ProviderResult[ModelTextOutput]:
    try:
        permit = governor.reserve(capability, PlanningStatus.PLANNING)
    except ToolCallGovernanceError as error:
        if attempt_runtime is None or error.code not in {
            ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING,
            ToolCallGovernanceErrorCode.CALL_TIMEOUT,
            ToolCallGovernanceErrorCode.TASK_TIMEOUT,
        }:
            raise
        return ProviderResult(
            ProviderResultStatus.UNAVAILABLE,
            Provider.DEEPSEEK,
            None,
            None,
            None,
            (),
            ProviderError(
                ProviderErrorCategory.TIMEOUT,
                reason=ProviderErrorReason.RETRY_DEADLINE_EXHAUSTED,
            ),
            (),
        )
    result: ProviderResult[ModelTextOutput] | None = None
    try:
        if attempt_runtime is None:
            result = await operation()
        else:
            outcome = await attempt_runtime.execute(
                provider=Provider.DEEPSEEK,
                operation=provider_operation,
                call=operation,
            )
            result = provider_result_from_attempt_outcome(outcome)
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


def _with_proposal(
    source: ProviderResult[ModelTextOutput],
    proposal: PlanProposal,
) -> ProviderResult[PlanProposal]:
    return ProviderResult(
        source.status,
        source.provider,
        proposal,
        source.fetched_at,
        source.valid_until,
        source.warnings,
        source.error,
        source.source_records,
    )


def _copy_proposal_unavailable(
    source: ProviderResult[ModelTextOutput],
) -> ProviderResult[PlanProposal]:
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


def _invalid_proposal_resolution(
    stage: CandidateValidationStage,
    validation_code: CandidateValidationCode,
    *,
    repaired: bool = False,
) -> ProposalResolution:
    return ProposalResolution(
        ProviderResult(
            ProviderResultStatus.UNAVAILABLE,
            Provider.DEEPSEEK,
            None,
            None,
            None,
            (),
            ProviderError(ProviderErrorCategory.SCHEMA),
            (),
        ),
        repaired,
        CandidateResolutionErrorCode.MODEL_OUTPUT_INVALID,
        stage,
        validation_code,
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
