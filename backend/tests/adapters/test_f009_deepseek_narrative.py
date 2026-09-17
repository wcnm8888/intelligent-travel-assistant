"""F-013 tests for the index-only V5 narrative boundary."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

from intelligent_travel_assistant.adapters.providers.deepseek import DeepSeekAdapter
from intelligent_travel_assistant.adapters.providers.f009_deepseek import (
    F009DeepSeekNarrativeProvider,
)
from intelligent_travel_assistant.application.f009 import (
    F009NarrativeRequest,
    F009ProviderFailureKind,
)


class FakeDeepSeekAdapter:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    async def _complete(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=SimpleNamespace(content=json.dumps(self.payload)),
            error=None,
        )


def request() -> F009NarrativeRequest:
    return F009NarrativeRequest(
        days=(
            (
                date(2026, 10, 1),
                ((UUID("70000000-0000-4000-8000-000000000001"), "西湖", "景点"),),
            ),
            (
                date(2026, 10, 2),
                (
                    (UUID("70000000-0000-4000-8000-000000000002"), "灵隐寺", "景点"),
                    (UUID("70000000-0000-4000-8000-000000000003"), "飞来峰", "景点"),
                ),
            ),
        ),
        pace="balanced",
        uncertainties=("营业时间未核验",),
    )


def test_index_only_output_is_mapped_to_immutable_dates_and_location_ids() -> None:
    adapter = FakeDeepSeekAdapter(
        {
            "days": [
                {
                    "day_index": 1,
                    "pace_note": "从容开始。",
                    "stop_narratives": ["沿湖慢行。"],
                    "rationale": "减少折返。",
                },
                {
                    "day_index": 2,
                    "pace_note": "连续游览。",
                    "stop_narratives": ["先看寺院。", "再看石刻。"],
                    "rationale": "相邻地点连续安排。",
                },
            ],
            "global_notes": ["营业时间请临行确认。"],
        }
    )
    provider = F009DeepSeekNarrativeProvider(cast(DeepSeekAdapter, adapter))

    outcome = asyncio.run(provider.generate(request()))

    assert outcome.failure is None
    assert outcome.data is not None
    assert tuple(day.local_date for day in outcome.data.days) == (
        date(2026, 10, 1),
        date(2026, 10, 2),
    )
    assert outcome.data.days[1].location_ids == (
        UUID("70000000-0000-4000-8000-000000000002"),
        UUID("70000000-0000-4000-8000-000000000003"),
    )
    frozen_days = adapter.calls[0]["user_payload"]["frozen_days"]
    assert "location_id" not in json.dumps(frozen_days)
    assert "local_date" not in json.dumps(frozen_days)


def test_wrong_day_or_stop_count_is_a_schema_failure() -> None:
    adapter = FakeDeepSeekAdapter(
        {
            "days": [
                {
                    "day_index": 1,
                    "pace_note": "说明。",
                    "stop_narratives": ["一项。"],
                    "rationale": "理由。",
                }
            ],
            "global_notes": [],
        }
    )
    provider = F009DeepSeekNarrativeProvider(cast(DeepSeekAdapter, adapter))

    outcome = asyncio.run(provider.generate(request()))

    assert outcome.data is None
    assert outcome.failure is not None
    assert outcome.failure.kind is F009ProviderFailureKind.SCHEMA
