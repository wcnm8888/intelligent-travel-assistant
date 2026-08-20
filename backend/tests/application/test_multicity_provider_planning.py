"""F-004B1 Step 4 offline multi-city planning and call governance."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from tests.contracts.test_multicity_trip_planning_contracts import money, request_payload

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
    FakeOperation,
    FakeQWeatherAdapter,
)
from intelligent_travel_assistant.adapters.providers.deepseek import _planning_context_payload
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.planning import (
    CandidateValidationError,
    DeepSeekProposalResolver,
    parse_plan_proposal,
)
from intelligent_travel_assistant.application.ports import (
    CityResolution,
    CityResolutionRequest,
    DailyWeather,
    ModelTextOutput,
    PlanCandidateRepairRequest,
    PlanningContext,
    PoiCandidate,
    PoiSearchRequest,
    PoiSearchResult,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.repositories import PlanningJob, PlanningJobResultV3
from intelligent_travel_assistant.application.services import (
    MultiCityPlanningOrchestrator,
    OfflinePlanningOrchestrator,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernor,
    multicity_task_timeout_seconds,
    multicity_tool_call_policies,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequestV3
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

NOW = datetime(2026, 8, 20, 4, tzinfo=UTC)


def _id(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"f-004b1-step4:{value}")


def _source(provider: Provider, value: str) -> SourceRecord:
    return SourceRecord(_id(f"source:{value}"), provider, f"synthetic_{value}", NOW, None)


def _result[T](provider: Provider, data: T, value: str) -> ProviderResult[T]:
    return ProviderResult(
        ProviderResultStatus.OK,
        provider,
        data,
        NOW,
        None,
        ("synthetic provider result",),
        None,
        (_source(provider, value),),
    )


def _request() -> TripPlanRequestV3:
    payload = request_payload()
    city_stays = cast(list[dict[str, object]], payload["city_stays"])
    for stay in city_stays:
        accommodation = cast(dict[str, object], stay["accommodation"])
        accommodation["one_night_cost"] = money("500.00")
    return TripPlanRequestV3.model_validate(payload)


def _proposal(poi_a: UUID, poi_b: UUID, source_a: UUID, source_b: UUID) -> str:
    return json.dumps(
        {
            "intent_summary": "synthetic multi-city proposal",
            "days": [
                {
                    "local_date": "2026-08-21",
                    "departure_city_index": 0,
                    "arrival_city_index": 0,
                    "overnight_city_index": 0,
                    "selections": [
                        {
                            "location_id": str(poi_a),
                            "local_date": "2026-08-21",
                            "title": "synthetic Hangzhou activity",
                            "priority_rank": 1,
                            "selection_kind": "required",
                            "duration_class": "short",
                            "source_ids": [str(source_a)],
                        }
                    ],
                },
                {
                    "local_date": "2026-08-22",
                    "departure_city_index": 0,
                    "arrival_city_index": 1,
                    "overnight_city_index": 1,
                    "selections": [],
                },
                {
                    "local_date": "2026-08-23",
                    "departure_city_index": 1,
                    "arrival_city_index": 1,
                    "overnight_city_index": 1,
                    "selections": [
                        {
                            "location_id": str(poi_b),
                            "local_date": "2026-08-23",
                            "title": "synthetic Shanghai activity",
                            "priority_rank": 1,
                            "selection_kind": "required",
                            "duration_class": "short",
                            "source_ids": [str(source_b)],
                        }
                    ],
                },
            ],
            "explanation": "synthetic offline result",
            "warnings": [],
        }
    )


def _orchestrator() -> tuple[
    MultiCityPlanningOrchestrator,
    FakeAmapAdapter,
    FakeQWeatherAdapter,
    FakeDeepSeekAdapter,
    list[ToolCallGovernor],
]:
    coordinates = (
        Coordinates(Decimal("120.15"), Decimal("30.27"), CoordinateSystem.PROVIDER_NATIVE),
        Coordinates(Decimal("121.47"), Decimal("31.23"), CoordinateSystem.PROVIDER_NATIVE),
    )
    hotels = tuple(
        PoiCandidate(_id(f"hotel:{index}"), f"hotel {index}", "lodging", adcode, None, coord)
        for index, (adcode, coord) in enumerate(zip(("330100", "310000"), coordinates, strict=True))
    )
    pois = tuple(
        PoiCandidate(
            _id(f"poi:{index}"),
            f"poi {index}",
            "scenic_area",
            adcode,
            None,
            coord,
        )
        for index, (adcode, coord) in enumerate(zip(("330100", "310000"), coordinates, strict=True))
    )
    stations = tuple(
        PoiCandidate(
            _id(f"station:{index}"),
            name,
            "rail_station",
            adcode,
            None,
            coord,
        )
        for index, (name, adcode, coord) in enumerate(
            zip(("杭州站", "上海站"), ("330100", "310000"), coordinates, strict=True)
        )
    )
    search_results = tuple(
        value
        for index in range(2)
        for value in (
            _result(Provider.AMAP, PoiSearchResult((hotels[index],)), f"hotel:{index}"),
            _result(Provider.AMAP, PoiSearchResult((pois[index],)), f"poi:{index}"),
            _result(Provider.AMAP, PoiSearchResult((stations[index],)), f"station:{index}"),
        )
    )
    route_pairs = (
        (hotels[0], pois[0]),
        (pois[0], hotels[0]),
        (hotels[1], pois[1]),
        (pois[1], hotels[1]),
    )
    route_results = tuple(
        _result(
            Provider.AMAP,
            RouteLeg(
                origin.location_id,
                destination.location_id,
                RouteMode.PUBLIC_TRANSIT,
                1000,
                15,
                (_id(f"source:route:{index}"),),
            ),
            f"route:{index}",
        )
        for index, (origin, destination) in enumerate(route_pairs)
    )
    amap = FakeAmapAdapter(
        resolve_city_results=(
            _result(
                Provider.AMAP,
                CityResolution("杭州市", "330100", "0571", coordinates[0]),
                "city:0",
            ),
            _result(
                Provider.AMAP,
                CityResolution("上海市", "310000", "021", coordinates[1]),
                "city:1",
            ),
        ),
        search_pois_results=search_results,
        calculate_routes_results=route_results,
    )
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=tuple(
            _result(
                Provider.QWEATHER,
                WeatherForecastResult(
                    hotels[index].location_id,
                    tuple(
                        DailyWeather(
                            date(2026, 8, 21) + timedelta(days=offset),
                            "晴",
                            "晴",
                            Decimal("20"),
                            Decimal("30"),
                        )
                        for offset in range(3)
                    ),
                ),
                f"weather:{index}",
            )
            for index in range(2)
        ),
        weather_alert_results=tuple(
            _result(
                Provider.QWEATHER,
                WeatherAlertsResult(hotels[index].location_id, ()),
                f"alert:{index}",
            )
            for index in range(2)
        ),
    )
    poi_sources = tuple(
        search_results[index * 3 + 1].source_records[0].source_id for index in range(2)
    )
    deepseek = FakeDeepSeekAdapter(
        generation_results=(
            _result(
                Provider.DEEPSEEK,
                ModelTextOutput(_proposal(pois[0].location_id, pois[1].location_id, *poi_sources)),
                "model",
            ),
        )
    )
    governors: list[ToolCallGovernor] = []

    def governor_factory(city_count: int, day_count: int) -> ToolCallGovernor:
        value = ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multicity_tool_call_policies(
                city_count=city_count,
                day_count=day_count,
            ),
            task_timeout_seconds=multicity_task_timeout_seconds(
                city_count=city_count,
                day_count=day_count,
            ),
        )
        governors.append(value)
        return value

    return (
        MultiCityPlanningOrchestrator(amap, qweather, deepseek, governor_factory),
        amap,
        qweather,
        deepseek,
        governors,
    )


def test_multicity_governance_scales_city_facts_but_not_model_calls() -> None:
    policies = multicity_tool_call_policies(city_count=3, day_count=7)

    assert policies[ToolCallCapability.RESOLVE_CITY].max_calls == 3
    assert policies[ToolCallCapability.SEARCH_POIS].max_calls == 9
    assert policies[ToolCallCapability.GET_WEATHER_FORECAST].max_calls == 3
    assert policies[ToolCallCapability.GET_CURRENT_WEATHER_ALERTS].max_calls == 3
    assert policies[ToolCallCapability.GENERATE_PLAN_CANDIDATE].max_calls == 1
    assert policies[ToolCallCapability.REPAIR_PLAN_CANDIDATE].max_calls == 1
    assert policies[ToolCallCapability.CALCULATE_ROUTES].max_calls == 28
    assert multicity_task_timeout_seconds(city_count=3, day_count=7) == 180.0


def test_multicity_orchestrator_is_a_distinct_application_boundary() -> None:
    assert MultiCityPlanningOrchestrator.__name__ == "MultiCityPlanningOrchestrator"


def test_multicity_orchestrator_builds_v3_plan_with_global_model_and_no_intercity_provider() -> (
    None
):
    orchestrator, amap, qweather, deepseek, governors = _orchestrator()

    result = asyncio.run(orchestrator.plan(_request(), job_id=_id("job"), evaluated_at=NOW))

    assert result.status is PlanningStatus.READY
    assert result.plan is not None
    assert result.plan.plan_format_version == "3"
    assert result.plan.city_adcodes == ("330100", "310000")
    assert [day.overnight_city_index for day in result.plan.days] == [0, 1, 1]
    assert result.plan.days[1].intercity_segment_id is not None
    assert result.plan.days[1].activities == ()
    assert len(result.plan.days[0].routes) == 2
    assert len(result.plan.days[2].routes) == 2
    assert len([call for call in amap.calls if call.operation is FakeOperation.RESOLVE_CITY]) == 2
    assert len([call for call in amap.calls if call.operation is FakeOperation.SEARCH_POIS]) == 6
    assert (
        len([call for call in amap.calls if call.operation is FakeOperation.CALCULATE_ROUTES]) == 4
    )
    assert len(qweather.calls) == 4
    assert len(deepseek.calls) == 1
    context = deepseek.calls[0].request
    assert isinstance(context, PlanningContext)
    assert context.request_version == "3"
    assert context.day_city_indices == ((0, 0, 0), (0, 1, 1), (1, 1, 1))
    assert governors[0].snapshot().active_route_calls == 0
    assert governors[0].snapshot().count_for(ToolCallCapability.GENERATE_PLAN_CANDIDATE) == 1


def test_v3_model_boundary_rejects_city_index_drift_and_omits_intercity_raw_values() -> None:
    orchestrator, _amap, _qweather, deepseek, _governors = _orchestrator()
    asyncio.run(orchestrator.plan(_request(), job_id=_id("model-boundary"), evaluated_at=NOW))
    context = deepseek.calls[0].request
    assert isinstance(context, PlanningContext)
    payload = _planning_context_payload(context)

    assert "intercity_segments" not in payload
    assert "杭州站" not in json.dumps(payload, ensure_ascii=False)
    assert "上海站" not in json.dumps(payload, ensure_ascii=False)

    invalid = json.loads(
        _proposal(
            context.locations[0].location_id,
            context.locations[1].location_id,
            context.activity_source_ids[0],
            context.activity_source_ids[1],
        )
    )
    invalid["days"][0]["overnight_city_index"] = 1
    with pytest.raises(CandidateValidationError):
        parse_plan_proposal(json.dumps(invalid), context)


def test_v3_repair_receives_only_safe_context_and_one_diagnostic() -> None:
    async def scenario() -> None:
        orchestrator, _amap, _qweather, deepseek, _governors = _orchestrator()
        await orchestrator.plan(_request(), job_id=_id("repair-context"), evaluated_at=NOW)
        context = deepseek.calls[0].request
        assert isinstance(context, PlanningContext)
        valid = _proposal(
            context.locations[0].location_id,
            context.locations[1].location_id,
            context.activity_source_ids[0],
            context.activity_source_ids[1],
        )
        invalid = json.loads(valid)
        invalid["days"][0]["overnight_city_index"] = 1
        repair_deepseek = FakeDeepSeekAdapter(
            generation_results=(
                _result(
                    Provider.DEEPSEEK,
                    ModelTextOutput(json.dumps(invalid)),
                    "invalid-model",
                ),
            ),
            repair_results=(
                _result(
                    Provider.DEEPSEEK,
                    ModelTextOutput(valid),
                    "repair-model",
                ),
            ),
        )
        governor = ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multicity_tool_call_policies(city_count=2, day_count=3),
            task_timeout_seconds=multicity_task_timeout_seconds(city_count=2, day_count=3),
        )

        resolution = await DeepSeekProposalResolver(repair_deepseek).resolve(context, governor)

        assert resolution.result.data is not None
        assert resolution.repaired is True
        assert len(repair_deepseek.calls) == 2
        repair_request = repair_deepseek.calls[1].request
        assert isinstance(repair_request, PlanCandidateRepairRequest)
        assert repair_request.invalid_output == ""
        assert repair_request.context.free_text == ""
        assert repair_request.context.interests == ()
        assert repair_request.context.hard_constraints == ()

    asyncio.run(scenario())


def test_provider_executor_persists_v3_terminal_result_through_existing_repository() -> None:
    async def execute() -> PlanningJob:
        multicity, amap, qweather, deepseek, _governors = _orchestrator()
        repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
        reservation = await repository.get_or_create(_request())
        legacy = OfflinePlanningOrchestrator(
            amap,
            qweather,
            deepseek,
            lambda: ToolCallGovernor(clock=lambda: 0.0),
        )
        executor = ProviderPlanningJobExecutor(
            repository,
            legacy,
            clock=lambda: NOW,
            multicity_orchestrator=multicity,
        )
        await executor.execute(reservation.job.job_id)
        return await repository.get(reservation.job.job_id)

    job = asyncio.run(execute())

    assert job.status is PlanningStatus.READY
    assert isinstance(job.result, PlanningJobResultV3)
    assert job.result.plan is not None
    assert job.result.plan.plan_format_version == "3"


def test_multicity_deadline_rejects_before_first_provider_call() -> None:
    _original, amap, qweather, deepseek, _governors = _orchestrator()
    readings = iter((0.0, 175.0))
    orchestrator = MultiCityPlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        lambda city_count, day_count: ToolCallGovernor(
            clock=lambda: next(readings),
            policies=multicity_tool_call_policies(
                city_count=city_count,
                day_count=day_count,
            ),
            task_timeout_seconds=multicity_task_timeout_seconds(
                city_count=city_count,
                day_count=day_count,
            ),
        ),
    )

    result = asyncio.run(orchestrator.plan(_request(), job_id=_id("deadline"), evaluated_at=NOW))

    assert result.status is PlanningStatus.FAILED
    assert result.errors[0].diagnostic_code == "insufficient_time_remaining"
    assert amap.calls == ()
    assert qweather.calls == ()
    assert deepseek.calls == ()


def test_multicity_city_fact_fanout_is_bounded_at_two() -> None:
    async def scenario() -> None:
        _original, amap, qweather, deepseek, governors = _orchestrator()

        class ConcurrentCities:
            def __init__(self) -> None:
                self.active = 0
                self.maximum = 0
                self.release = asyncio.Event()
                self.first_city_searches = 0
                self.first_city_done = asyncio.Event()

            async def resolve_city(
                self, request: CityResolutionRequest
            ) -> ProviderResult[CityResolution]:
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                result = await amap.resolve_city(request)
                if self.active == 2:
                    self.release.set()
                await self.release.wait()
                try:
                    return result
                finally:
                    self.active -= 1

            async def search_pois(
                self, request: PoiSearchRequest
            ) -> ProviderResult[PoiSearchResult]:
                if request.city_adcode == "310000":
                    await self.first_city_done.wait()
                result = await amap.search_pois(request)
                if request.city_adcode == "330100":
                    self.first_city_searches += 1
                    if self.first_city_searches == 3:
                        self.first_city_done.set()
                return result

            async def calculate_routes(
                self, request: RouteCalculationRequest
            ) -> ProviderResult[RouteLeg]:
                return await amap.calculate_routes(request)

        concurrent = ConcurrentCities()
        orchestrator = MultiCityPlanningOrchestrator(
            concurrent,
            qweather,
            deepseek,
            lambda city_count, day_count: _captured_governor(
                governors,
                city_count=city_count,
                day_count=day_count,
            ),
        )
        result = await orchestrator.plan(_request(), job_id=_id("fanout"), evaluated_at=NOW)
        assert result.status is PlanningStatus.READY
        assert concurrent.maximum == 2
        assert concurrent.active == 0

    asyncio.run(scenario())


def test_multicity_cancellation_drains_two_inflight_route_peers_and_starts_no_more() -> None:
    async def scenario() -> None:
        _original, amap, qweather, deepseek, governors = _orchestrator()

        class BlockingRoutes:
            def __init__(self) -> None:
                self.active = 0
                self.maximum = 0
                self.calls = 0
                self.started = asyncio.Event()

            async def resolve_city(
                self, request: CityResolutionRequest
            ) -> ProviderResult[CityResolution]:
                return await amap.resolve_city(request)

            async def search_pois(
                self, request: PoiSearchRequest
            ) -> ProviderResult[PoiSearchResult]:
                return await amap.search_pois(request)

            async def calculate_routes(
                self, request: RouteCalculationRequest
            ) -> ProviderResult[RouteLeg]:
                self.calls += 1
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                if self.active == 2:
                    self.started.set()
                try:
                    await asyncio.Event().wait()
                    raise AssertionError("blocked route unexpectedly resumed")
                finally:
                    self.active -= 1

        blocking = BlockingRoutes()
        orchestrator = MultiCityPlanningOrchestrator(
            blocking,
            qweather,
            deepseek,
            lambda city_count, day_count: _captured_governor(
                governors,
                city_count=city_count,
                day_count=day_count,
            ),
        )
        task = asyncio.create_task(
            orchestrator.plan(_request(), job_id=_id("cancel"), evaluated_at=NOW)
        )
        await blocking.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert blocking.maximum == 2
        assert blocking.calls == 2
        assert blocking.active == 0
        assert governors[-1].snapshot().active_route_calls == 0

    asyncio.run(scenario())


def _captured_governor(
    values: list[ToolCallGovernor],
    *,
    city_count: int,
    day_count: int,
) -> ToolCallGovernor:
    governor = ToolCallGovernor(
        clock=lambda: 0.0,
        policies=multicity_tool_call_policies(city_count=city_count, day_count=day_count),
        task_timeout_seconds=multicity_task_timeout_seconds(
            city_count=city_count,
            day_count=day_count,
        ),
    )
    values.append(governor)
    return governor
