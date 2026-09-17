"""F-016 browser fixture isolation checks."""

from __future__ import annotations

import asyncio
from datetime import date
from uuid import UUID

from intelligent_travel_assistant.application.f009 import F009NarrativeRequest
from tests.browser_f010_support import InvalidSyntheticNarrativeProvider


def _request() -> F009NarrativeRequest:
    return F009NarrativeRequest(
        days=(
            (
                date(2026, 10, 1),
                ((UUID("70000000-0000-4000-8000-000000000001"), "西湖", "景点"),),
            ),
        ),
        pace="balanced",
        uncertainties=("营业时间未核验",),
    )


def test_retry_fixture_repeats_the_same_three_call_cycle_per_journey() -> None:
    provider = InvalidSyntheticNarrativeProvider("retry")
    request = _request()

    first_cycle = (
        asyncio.run(provider.generate(request)),
        asyncio.run(provider.repair(request)),
        asyncio.run(provider.generate(request)),
    )
    second_cycle = (
        asyncio.run(provider.generate(request)),
        asyncio.run(provider.repair(request)),
        asyncio.run(provider.generate(request)),
    )

    expected_ids = tuple(item[0] for item in request.days[0][1])
    for cycle in (first_cycle, second_cycle):
        assert cycle[0].data is not None
        assert cycle[0].data.days[0].location_ids != expected_ids
        assert cycle[1].data is not None
        assert cycle[1].data.days[0].location_ids != expected_ids
        assert cycle[2].data is not None
        assert cycle[2].data.days[0].location_ids == expected_ids
