"""Strict DeepSeek proposal admission without model-owned exact times."""

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.fakes import FakeDeepSeekAdapter, FakeOperation
from intelligent_travel_assistant.application.planning import (
    CandidateResolutionErrorCode,
    CandidateValidationError,
    CandidateValidationStage,
    DeepSeekProposalResolver,
    parse_plan_proposal,
)
from intelligent_travel_assistant.application.ports import (
    ActivityDurationClass,
    ActivitySelectionKind,
    CandidateValidationCode,
    ModelTextOutput,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningObservation,
    PlanningToolName,
)
from intelligent_travel_assistant.application.tooling import ToolCallGovernor
from intelligent_travel_assistant.domain import (
    Money,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    SourceRecord,
)

FETCHED_AT = datetime(2026, 8, 15, 2, tzinfo=UTC)
VALID_UNTIL = FETCHED_AT + timedelta(hours=1)
POI_ONE_ID = UUID("91000000-0000-4000-8000-000000000001")
POI_TWO_ID = UUID("91000000-0000-4000-8000-000000000002")
HOTEL_ID = UUID("91000000-0000-4000-8000-000000000010")
AMAP_SOURCE_ID = UUID("41000000-0000-4000-8000-000000000001")
DEEPSEEK_SOURCE_ID = UUID("71000000-0000-4000-8000-000000000001")


def _context() -> PlanningContext:
    return PlanningContext(
        city_name="杭州市",
        city_adcode="330100",
        start_date=date(2026, 8, 16),
        end_date=date(2026, 8, 17),
        travelers=2,
        budget=Money(Decimal("4000.00")),
        interests=("自然", "历史"),
        hard_constraints=(),
        allowed_tools=tuple(PlanningToolName),
        locations=(
            PlanningLocation(POI_ONE_ID, "synthetic scenic POI", "scenic_area", "330100"),
            PlanningLocation(POI_TWO_ID, "synthetic museum POI", "museum", "330100"),
        ),
        observations=(PlanningObservation("pois", "synthetic POIs", (AMAP_SOURCE_ID,)),),
        day_windows=(
            PlanningDayWindow(0, time(8), time(18)),
            PlanningDayWindow(1, time(8), time(18)),
        ),
        accommodation=PlanningLocation(
            HOTEL_ID,
            "synthetic accommodation",
            "accommodation_anchor",
            "330100",
        ),
        activity_source_ids=(AMAP_SOURCE_ID,),
    )


def _proposal_document() -> dict[str, object]:
    return {
        "intent_summary": "杭州双日 synthetic proposal",
        "days": [
            {
                "local_date": "2026-08-16",
                "selections": [
                    {
                        "location_id": str(POI_ONE_ID),
                        "local_date": "2026-08-16",
                        "title": "第一项活动",
                        "priority_rank": 1,
                        "selection_kind": "required",
                        "duration_class": "standard",
                        "source_ids": [str(AMAP_SOURCE_ID)],
                    }
                ],
            },
            {
                "local_date": "2026-08-17",
                "selections": [
                    {
                        "location_id": str(POI_TWO_ID),
                        "local_date": "2026-08-17",
                        "title": "第二项活动",
                        "priority_rank": 1,
                        "selection_kind": "optional",
                        "duration_class": "unknown",
                        "source_ids": [str(AMAP_SOURCE_ID)],
                    }
                ],
            },
        ],
        "explanation": "只选择已验证的 synthetic POI。",
        "warnings": ["时长由代码裁决"],
    }


def _proposal_days(document: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], document["days"])


def _first_selection(document: dict[str, object]) -> dict[str, object]:
    return cast(list[dict[str, object]], _proposal_days(document)[0]["selections"])[0]


def _result(content: str) -> ProviderResult[ModelTextOutput]:
    source = SourceRecord(
        DEEPSEEK_SOURCE_ID,
        Provider.DEEPSEEK,
        "synthetic_model_plan_proposal",
        FETCHED_AT,
        VALID_UNTIL,
        "https://api.deepseek.com",
    )
    return ProviderResult(
        ProviderResultStatus.OK,
        Provider.DEEPSEEK,
        ModelTextOutput(content),
        FETCHED_AT,
        VALID_UNTIL,
        ("synthetic model output",),
        None,
        (source,),
    )


def test_parser_accepts_exact_two_day_proposal_without_times() -> None:
    proposal = parse_plan_proposal(json.dumps(_proposal_document()), _context())

    assert tuple(day.local_date for day in proposal.days) == (
        date(2026, 8, 16),
        date(2026, 8, 17),
    )
    first = proposal.days[0].selections[0]
    assert first.selection_kind is ActivitySelectionKind.REQUIRED
    assert first.duration_class is ActivityDurationClass.STANDARD
    assert not hasattr(first, "start_time")
    assert not hasattr(first, "end_time")


@pytest.mark.parametrize(
    "forbidden",
    (
        "start_time",
        "end_time",
        "routes",
        "route_duration_minutes",
        "verified",
        "status",
        "provider",
    ),
)
def test_parser_rejects_model_owned_execution_fields(forbidden: str) -> None:
    document = _proposal_document()
    selection = _first_selection(document)
    selection[forbidden] = "09:00:00"

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


def test_parser_rejects_more_than_two_daily_activities() -> None:
    document = _proposal_document()
    selections = cast(list[dict[str, object]], _proposal_days(document)[0]["selections"])
    selections.extend((dict(selections[0]), dict(selections[0])))

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("priority_rank", 0),
        ("priority_rank", True),
        ("selection_kind", "maybe"),
        ("duration_class", "ninety_minutes"),
    ),
)
def test_parser_rejects_invalid_priority_kind_and_duration(field: str, value: object) -> None:
    document = _proposal_document()
    _first_selection(document)[field] = value

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


def test_parser_requires_unique_contiguous_priority_ranks() -> None:
    document = _proposal_document()
    first = _first_selection(document)
    second = dict(first)
    second["location_id"] = str(POI_TWO_ID)
    _proposal_days(document)[0]["selections"] = [first, second]

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ('"intent_summary":', '"intent_summary":"duplicate","intent_summary":'),
        (
            '"local_date":"2026-08-16","selections"',
            '"local_date":"2026-08-16","local_date":"2026-08-16","selections"',
        ),
        (
            '"location_id":"91000000-0000-4000-8000-000000000001"',
            '"location_id":"duplicate","location_id":"91000000-0000-4000-8000-000000000001"',
        ),
    ),
)
def test_parser_rejects_duplicate_keys_at_every_object_level(needle: str, replacement: str) -> None:
    raw = json.dumps(_proposal_document(), separators=(",", ":"))

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(raw.replace(needle, replacement, 1), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


@pytest.mark.parametrize("scope", ("root", "day"))
def test_parser_rejects_unknown_root_and_day_fields(scope: str) -> None:
    document = _proposal_document()
    target = document if scope == "root" else _proposal_days(document)[0]
    target["unexpected"] = "synthetic forbidden field"

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SCHEMA_INVALID


@pytest.mark.parametrize("case", ("swapped_days", "child_date_mismatch"))
def test_parser_rejects_day_order_and_parent_child_date_mismatch(case: str) -> None:
    document = _proposal_document()
    if case == "swapped_days":
        _proposal_days(document).reverse()
    else:
        _first_selection(document)["local_date"] = "2026-08-17"

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.DATE_INVALID


def test_parser_rejects_location_outside_frozen_catalog() -> None:
    document = _proposal_document()
    _first_selection(document)["location_id"] = "91000000-0000-4000-8000-000000000099"

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.POI_REFERENCE_INVALID


@pytest.mark.parametrize(
    "source_ids",
    (
        ["not-a-uuid"],
        ["41000000-0000-4000-8000-000000000099"],
        [str(AMAP_SOURCE_ID), str(AMAP_SOURCE_ID)],
    ),
)
def test_parser_rejects_invalid_external_and_duplicate_sources(source_ids: list[str]) -> None:
    document = _proposal_document()
    _first_selection(document)["source_ids"] = source_ids

    with pytest.raises(CandidateValidationError) as error:
        parse_plan_proposal(json.dumps(document), _context())

    assert error.value.code is CandidateValidationCode.SOURCE_REFERENCE_INVALID


def test_same_proposal_parses_identically_across_repeated_runs_and_catalog_order() -> None:
    raw = json.dumps(_proposal_document(), sort_keys=True)
    context = _context()
    reordered = PlanningContext(
        city_name=context.city_name,
        city_adcode=context.city_adcode,
        start_date=context.start_date,
        end_date=context.end_date,
        travelers=context.travelers,
        budget=context.budget,
        interests=context.interests,
        hard_constraints=context.hard_constraints,
        allowed_tools=context.allowed_tools,
        locations=tuple(reversed(context.locations)),
        observations=context.observations,
        free_text=context.free_text,
        route_mode=context.route_mode,
        day_windows=context.day_windows,
        accommodation=context.accommodation,
        activity_source_ids=context.activity_source_ids,
    )

    values = tuple(parse_plan_proposal(raw, context) for _ in range(10))

    assert all(value == values[0] for value in values)
    assert parse_plan_proposal(raw, reordered) == values[0]


def test_proposal_resolution_repairs_once_and_never_adds_model_time() -> None:
    fake = FakeDeepSeekAdapter(
        generation_results=(_result("{invalid"),),
        repair_results=(_result(json.dumps(_proposal_document())),),
    )

    resolution = asyncio.run(
        DeepSeekProposalResolver(fake).resolve(_context(), ToolCallGovernor(clock=lambda: 0.0))
    )

    assert resolution.error_code is None
    assert resolution.repaired is True
    assert resolution.result.data is not None
    assert not hasattr(resolution.result.data.days[0].selections[0], "start_time")
    assert [call.operation for call in fake.calls] == [
        FakeOperation.GENERATE_PLAN_CANDIDATE,
        FakeOperation.REPAIR_PLAN_CANDIDATE,
    ]


def test_proposal_resolution_stops_after_one_failed_repair() -> None:
    generation_secret = "{synthetic-generation-secret"
    repair_secret = "{synthetic-repair-secret"
    fake = FakeDeepSeekAdapter(
        generation_results=(_result(generation_secret),),
        repair_results=(_result(repair_secret),),
    )

    resolution = asyncio.run(
        DeepSeekProposalResolver(fake).resolve(_context(), ToolCallGovernor(clock=lambda: 0.0))
    )

    assert resolution.error_code is CandidateResolutionErrorCode.MODEL_OUTPUT_INVALID
    assert resolution.validation_stage is CandidateValidationStage.REPAIR
    assert resolution.validation_code is CandidateValidationCode.JSON_INVALID
    assert len(fake.calls) == 2
    assert generation_secret not in repr(resolution)
    assert repair_secret not in repr(resolution)


def test_proposal_resolution_preserves_provider_unavailable_without_repair() -> None:
    unavailable = ProviderResult[ModelTextOutput](
        ProviderResultStatus.UNAVAILABLE,
        Provider.DEEPSEEK,
        None,
        None,
        None,
        ("synthetic provider timeout",),
        ProviderError(ProviderErrorCategory.TIMEOUT),
        (),
    )
    fake = FakeDeepSeekAdapter(generation_results=(unavailable,))

    resolution = asyncio.run(
        DeepSeekProposalResolver(fake).resolve(_context(), ToolCallGovernor(clock=lambda: 0.0))
    )

    assert resolution.result.status is ProviderResultStatus.UNAVAILABLE
    assert resolution.repaired is False
    assert len(fake.calls) == 1
