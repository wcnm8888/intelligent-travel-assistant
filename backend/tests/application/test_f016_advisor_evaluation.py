"""Fixed offline evaluation set for the five approved traveler profiles."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.fakes import SyntheticF014AdvisorProvider
from intelligent_travel_assistant.application.f009 import F014AdvisorRequest


@pytest.mark.parametrize(
    ("message", "expected_preferences", "expects_recommendation"),
    (
        ("第一次到杭州，不知道去哪里，请推荐。", set(), True),
        ("亲子出行，希望少走路也避开拥挤。", {"walking_tolerance", "crowd_tolerance"}, False),
        ("老人同行，希望少走路，请推荐。", {"walking_tolerance", "crowd_tolerance"}, True),
        ("为了美食晚起，上午十点后出门。", {"food_preferences", "day_start"}, False),
        ("预算固定，必去地点太多时请先解释冲突。", {"budget_flexibility"}, False),
    ),
)
def test_fixed_profile_extracts_only_bounded_suggestions(
    message: str,
    expected_preferences: set[str],
    expects_recommendation: bool,
) -> None:
    request = F014AdvisorRequest(
        user_message=message,
        confirmed_preferences=(),
        candidates=(
            (1, UUID("94000000-0000-4000-8000-000000000001"), "西湖", "景点"),
            (2, UUID("94000000-0000-4000-8000-000000000002"), "灵隐寺", "景点"),
        ),
    )

    outcome = asyncio.run(SyntheticF014AdvisorProvider().generate(request))

    assert outcome.data is not None
    assert {key for key, _ in outcome.data.preference_values} == expected_preferences
    assert bool(outcome.data.candidate_indices) is expects_recommendation
    assert len(outcome.data.candidate_indices) <= 3
    assert len(outcome.data.candidate_indices) == len(outcome.data.candidate_reasons)
