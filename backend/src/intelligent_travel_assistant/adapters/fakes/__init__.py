"""Explicitly synthetic, programmable provider adapters for offline tests."""

from intelligent_travel_assistant.adapters.fakes.f009 import (
    SYNTHETIC_F009_POIS,
    SyntheticF009MapProvider,
    SyntheticF009NarrativeProvider,
    SyntheticF014AdvisorProvider,
)
from intelligent_travel_assistant.adapters.fakes.planning_jobs import (
    SyntheticPlanningJobExecutor,
)
from intelligent_travel_assistant.adapters.fakes.scripted import (
    FakeAmapAdapter,
    FakeCall,
    FakeDeepSeekAdapter,
    FakeOperation,
    FakeQWeatherAdapter,
    FakeScriptError,
)

__all__ = [
    "FakeAmapAdapter",
    "FakeCall",
    "FakeDeepSeekAdapter",
    "FakeOperation",
    "FakeQWeatherAdapter",
    "FakeScriptError",
    "SYNTHETIC_F009_POIS",
    "SyntheticF009MapProvider",
    "SyntheticF009NarrativeProvider",
    "SyntheticF014AdvisorProvider",
    "SyntheticPlanningJobExecutor",
]
