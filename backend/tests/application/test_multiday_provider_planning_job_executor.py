"""F-004A multiday provider orchestration through the real executor and repository."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
    FakeOperation,
    FakeQWeatherAdapter,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.ports import (
    CityResolution,
    DailyWeather,
    ModelTextOutput,
    PoiCandidate,
    PoiSearchResult,
    WeatherAlertsResult,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.repositories import PlanningJob
from intelligent_travel_assistant.application.services.offline_planning import (
    OfflinePlanningOrchestrator,
    OfflinePlanningRequest,
)
from intelligent_travel_assistant.application.services.provider_planning_jobs import (
    ProviderPlanningJobExecutor,
    _offline_request,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernor,
    multiday_task_timeout_seconds,
    multiday_tool_call_policies,
)
from intelligent_travel_assistant.contracts import (
    AccommodationRequirement,
    MultiDayTimeWindow,
    PlanningStatus,
    TransportMode,
    TripPlanRequestV2,
    TripPlanV2,
)
from intelligent_travel_assistant.contracts import (
    Money as ApiMoney,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    MultiDayTripRequestInput,
    Provider,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)
START = date(2026, 8, 15)
HOTEL_ID = UUID("92000000-0000-4000-8000-000000000010")
HOTEL_COORDS = Coordinates(Decimal("120.150"), Decimal("30.270"), CoordinateSystem.PROVIDER_NATIVE)


def _id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"f-004a:{value}")


def _source(provider: Provider, value: str) -> SourceRecord:
    return SourceRecord(_id(f"source:{value}"), provider, f"synthetic_{value}", NOW, None)


def _result[T](provider: Provider, data: T, value: str) -> ProviderResult[T]:
    source = _source(provider, value)
    return ProviderResult(
        ProviderResultStatus.OK,
        provider,
        data,
        NOW,
        None,
        ("synthetic provider result",),
        None,
        (source,),
    )


def _request(day_count: int) -> TripPlanRequestV2:
    return TripPlanRequestV2(
        request_version="2",
        client_request_id=_id(f"request:{day_count}"),
        city="杭州",
        start_date=START,
        end_date=START + timedelta(days=day_count - 1),
        travelers=2,
        total_budget=ApiMoney(amount=Decimal("8000.00")),
        transport_modes=(TransportMode.PUBLIC_TRANSIT,),
        accommodation=AccommodationRequirement(
            area_or_poi="西湖附近",
            one_night_cost=ApiMoney(amount=Decimal("700.00")),
        ),
        day_windows=tuple(
            MultiDayTimeWindow(day_offset=offset, start_time=time(8), end_time=time(18))
            for offset in range(day_count)
        ),
        meal_budget_per_person_per_day=ApiMoney(amount=Decimal("100.00")),
        intercity_transport_cost=ApiMoney(amount=Decimal("1000.00")),
    )


def _proposal(day_count: int, poi_source_id: UUID) -> str:
    return json.dumps(
        {
            "intent_summary": "synthetic multiday proposal",
            "days": [
                {
                    "local_date": (START + timedelta(days=offset)).isoformat(),
                    "selections": [
                        {
                            "location_id": str(_id(f"poi:{offset}")),
                            "local_date": (START + timedelta(days=offset)).isoformat(),
                            "title": f"synthetic activity {offset}",
                            "priority_rank": 1,
                            "selection_kind": "required",
                            "duration_class": "standard",
                            "source_ids": [str(poi_source_id)],
                        }
                    ],
                }
                for offset in range(day_count)
            ],
            "explanation": "synthetic multiday candidate",
            "warnings": [],
        }
    )


async def _execute(day_count: int) -> tuple[PlanningJob, FakeAmapAdapter, ToolCallGovernor]:
    request = _request(day_count)
    pois = tuple(
        PoiCandidate(
            _id(f"poi:{offset}"),
            f"synthetic POI {offset}",
            "scenic_area",
            "330100",
            None,
            Coordinates(
                Decimal("120.16") + Decimal(offset) / 100,
                Decimal("30.28") + Decimal(offset) / 100,
                CoordinateSystem.PROVIDER_NATIVE,
            ),
        )
        for offset in range(day_count)
    )
    accommodation = _result(
        Provider.AMAP,
        PoiSearchResult(
            (PoiCandidate(HOTEL_ID, "synthetic hotel", "lodging", "330100", None, HOTEL_COORDS),)
        ),
        "accommodation",
    )
    poi_result = _result(Provider.AMAP, PoiSearchResult(pois), "pois")
    route_results = tuple(
        _result(
            Provider.AMAP,
            RouteLeg(
                origin,
                destination,
                RouteMode.PUBLIC_TRANSIT,
                3000,
                20,
                (_id(f"source:route:{index}"),),
            ),
            f"route:{index}",
        )
        for index, (origin, destination) in enumerate(
            pair
            for poi in pois
            for pair in ((HOTEL_ID, poi.location_id), (poi.location_id, HOTEL_ID))
        )
    )
    amap = FakeAmapAdapter(
        resolve_city_results=(
            _result(
                Provider.AMAP,
                CityResolution("杭州市", "330100", "0571", HOTEL_COORDS),
                "city",
            ),
        ),
        search_pois_results=(accommodation, poi_result),
        calculate_routes_results=route_results,
    )
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=(
            _result(
                Provider.QWEATHER,
                WeatherForecastResult(
                    HOTEL_ID,
                    tuple(
                        DailyWeather(
                            START + timedelta(days=offset),
                            "多云",
                            "晴",
                            Decimal("20"),
                            Decimal("30"),
                        )
                        for offset in range(day_count)
                    ),
                ),
                "weather",
            ),
        ),
        weather_alert_results=(
            _result(Provider.QWEATHER, WeatherAlertsResult(HOTEL_ID, ()), "alerts"),
        ),
    )
    deepseek = FakeDeepSeekAdapter(
        generation_results=(
            _result(
                Provider.DEEPSEEK,
                ModelTextOutput(_proposal(day_count, poi_result.source_records[0].source_id)),
                "proposal",
            ),
        )
    )
    governor: ToolCallGovernor | None = None

    def request_governor_factory(value: OfflinePlanningRequest) -> ToolCallGovernor:
        nonlocal governor
        count = value.day_count
        governor = ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multiday_tool_call_policies(count),
            task_timeout_seconds=multiday_task_timeout_seconds(count),
        )
        return governor

    repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
    reserved = await repository.get_or_create(request)
    orchestrator = OfflinePlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        lambda: ToolCallGovernor(clock=lambda: 0.0),
        request_governor_factory=request_governor_factory,
    )
    await ProviderPlanningJobExecutor(repository, orchestrator, clock=lambda: NOW).execute(
        reserved.job.job_id
    )
    assert governor is not None
    return await repository.get(reserved.job.job_id), amap, governor


@pytest.mark.parametrize("day_count", (3, 7))
def test_multiday_executor_publishes_typed_plan_with_bounded_provider_calls(
    day_count: int,
) -> None:
    job, amap, governor = asyncio.run(_execute(day_count))
    assert job.result is not None
    assert job.status is PlanningStatus.PARTIAL
    assert isinstance(job.result.plan, TripPlanV2)
    assert len(job.result.plan.days) == day_count
    assert job.result.plan.end_date == START + timedelta(days=day_count - 1)
    assert job.result.plan.budget_summary.unknown_count == 1
    assert all(
        item.amount is None
        for item in job.result.plan.budget_summary.cost_items
        if item.confidence.value == "unknown"
    )
    meal = next(
        item for item in job.result.plan.budget_summary.cost_items if item.category.value == "meal"
    )
    assert meal.description == f"按用户每日餐饮预算计算的{day_count}日估算"
    route_calls = [call for call in amap.calls if call.operation is FakeOperation.CALCULATE_ROUTES]
    assert len(route_calls) == 2 * day_count
    assert governor.snapshot().count_for(ToolCallCapability.CALCULATE_ROUTES) == 2 * day_count
    assert governor.snapshot().active_route_calls == 0


@pytest.mark.parametrize(("day_count", "poi_limit"), ((2, 6), (3, 8), (7, 16)))
def test_multiday_offline_request_scales_dates_budget_and_poi_limit(
    day_count: int,
    poi_limit: int,
) -> None:
    value = _offline_request(_request(day_count), job_id=_id("job"), evaluated_at=NOW)

    assert isinstance(value.trip, MultiDayTripRequestInput)
    assert value.trip.day_count == day_count
    assert value.poi_limit == poi_limit
    costs = {item.category.value: item for item in value.cost_items}
    assert costs["meal"].amount is not None
    assert costs["meal"].amount.amount == Decimal(200 * day_count)
    assert costs["accommodation"].amount is not None
    assert costs["accommodation"].amount.amount == Decimal(700 * (day_count - 1))
    assert costs["ticket"].amount is None
