"""Offline proof for the live-capable planning-job executor bridge."""

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
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
from intelligent_travel_assistant.application.services import (
    OfflinePlanningOrchestrator,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.tooling import ToolCallGovernor
from intelligent_travel_assistant.contracts import (
    AccommodationRequirement,
    DailyTimeWindow,
    PlanningStatus,
    TransportMode,
    TripPlanRequest,
)
from intelligent_travel_assistant.contracts import (
    Money as ApiMoney,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

NOW = datetime(2026, 8, 14, 2, tzinfo=UTC)
FETCHED_AT = NOW + timedelta(seconds=1)
VALID_UNTIL = NOW + timedelta(hours=1)
JOB_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
HOTEL_ID = UUID("90000000-0000-4000-8000-000000000001")
POI_ONE_ID = UUID("90000000-0000-4000-8000-000000000002")
POI_TWO_ID = UUID("90000000-0000-4000-8000-000000000003")
HOTEL_COORDS = Coordinates(Decimal("120.15"), Decimal("30.25"), CoordinateSystem.PROVIDER_NATIVE)
POI_ONE_COORDS = Coordinates(Decimal("120.16"), Decimal("30.24"), CoordinateSystem.PROVIDER_NATIVE)
POI_TWO_COORDS = Coordinates(Decimal("120.14"), Decimal("30.26"), CoordinateSystem.PROVIDER_NATIVE)


def _source(provider: Provider, suffix: str, *, attribution: bool = False) -> SourceRecord:
    return SourceRecord(
        uuid5(NAMESPACE_URL, f"synthetic:{provider.value}:{suffix}"),
        provider,
        f"synthetic_{suffix}",
        FETCHED_AT,
        VALID_UNTIL if provider is Provider.QWEATHER else None,
        "https://www.qweather.com" if attribution else None,
        ("QWeather attribution from fixture",) if attribution else (),
    )


def _result[T](provider: Provider, data: T, suffix: str) -> ProviderResult[T]:
    return ProviderResult(
        ProviderResultStatus.OK,
        provider,
        data,
        FETCHED_AT,
        VALID_UNTIL if provider is Provider.QWEATHER else None,
        (f"synthetic {suffix}",),
        None,
        (_source(provider, suffix, attribution=provider is Provider.QWEATHER),),
    )


def _request() -> TripPlanRequest:
    return TripPlanRequest(
        client_request_id=UUID("11111111-1111-4111-8111-111111111111"),
        city="杭州",
        start_date=date(2026, 8, 15),
        travelers=2,
        total_budget=ApiMoney(amount=Decimal("4000.00")),
        transport_modes=(TransportMode.PUBLIC_TRANSIT,),
        accommodation=AccommodationRequirement(
            area_or_poi="西湖附近",
            one_night_cost=ApiMoney(amount=Decimal("700.00")),
        ),
        day_windows=(
            DailyTimeWindow(day_offset=0, start_time=time(8), end_time=time(18)),
            DailyTimeWindow(day_offset=1, start_time=time(8), end_time=time(18)),
        ),
        intercity_transport_cost=ApiMoney(amount=Decimal("1000.00")),
    )


def _candidate_json(poi_source_id: UUID) -> str:
    return json.dumps(
        {
            "intent_summary": "synthetic two day plan",
            "days": [
                {
                    "local_date": "2026-08-15",
                    "activities": [
                        {
                            "location_id": str(POI_ONE_ID),
                            "local_date": "2026-08-15",
                            "title": "西湖步行",
                            "start_time": "10:00:00",
                            "end_time": "12:00:00",
                            "source_ids": [str(poi_source_id)],
                        }
                    ],
                },
                {
                    "local_date": "2026-08-16",
                    "activities": [
                        {
                            "location_id": str(POI_TWO_ID),
                            "local_date": "2026-08-16",
                            "title": "博物馆参观",
                            "start_time": "10:00:00",
                            "end_time": "12:00:00",
                            "source_ids": [str(poi_source_id)],
                        }
                    ],
                },
            ],
            "explanation": "synthetic candidate",
            "warnings": ["synthetic candidate"],
        }
    )


async def _execute(
    *,
    model_output_invalid: bool = False,
    provider_schema_invalid: bool = False,
) -> tuple[PlanningJob, FakeAmapAdapter]:
    accommodation_result = _result(
        Provider.AMAP,
        PoiSearchResult(
            (
                PoiCandidate(
                    HOTEL_ID,
                    "西湖附近住宿锚点",
                    "lodging",
                    "330100",
                    "synthetic address",
                    HOTEL_COORDS,
                ),
            )
        ),
        "accommodation",
    )
    poi_result = _result(
        Provider.AMAP,
        PoiSearchResult(
            (
                PoiCandidate(POI_ONE_ID, "西湖", "scenic_area", "330100", None, POI_ONE_COORDS),
                PoiCandidate(POI_TWO_ID, "博物馆", "museum", "330100", None, POI_TWO_COORDS),
            )
        ),
        "pois",
    )
    poi_source_id = poi_result.source_records[0].source_id
    route_source = _source(Provider.AMAP, "route")
    route_pairs = (
        (HOTEL_ID, POI_ONE_ID, 20),
        (POI_ONE_ID, HOTEL_ID, 22),
        (HOTEL_ID, POI_TWO_ID, 30),
        (POI_TWO_ID, HOTEL_ID, 32),
    )
    routes = tuple(
        ProviderResult(
            ProviderResultStatus.OK,
            Provider.AMAP,
            RouteLeg(
                origin,
                destination,
                RouteMode.PUBLIC_TRANSIT,
                3000,
                minutes,
                (route_source.source_id,),
            ),
            FETCHED_AT,
            None,
            ("synthetic route",),
            None,
            (route_source,),
        )
        for origin, destination, minutes in route_pairs
    )
    amap = FakeAmapAdapter(
        resolve_city_results=(
            _result(
                Provider.AMAP,
                CityResolution("杭州市", "330100", "0571", HOTEL_COORDS),
                "city",
            ),
        ),
        search_pois_results=(accommodation_result, poi_result),
        calculate_routes_results=routes,
    )
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=(
            _result(
                Provider.QWEATHER,
                WeatherForecastResult(
                    HOTEL_ID,
                    (
                        DailyWeather(
                            date(2026, 8, 15), "多云", "多云", Decimal("25"), Decimal("34")
                        ),
                        DailyWeather(
                            date(2026, 8, 16), "阵雨", "多云", Decimal("24"), Decimal("32")
                        ),
                    ),
                ),
                "forecast",
            ),
        ),
        weather_alert_results=(
            _result(Provider.QWEATHER, WeatherAlertsResult(HOTEL_ID, ()), "alerts"),
        ),
    )
    if provider_schema_invalid:
        deepseek = FakeDeepSeekAdapter(
            generation_results=(
                ProviderResult(
                    ProviderResultStatus.UNAVAILABLE,
                    Provider.DEEPSEEK,
                    None,
                    None,
                    None,
                    ("synthetic provider schema failure",),
                    ProviderError(
                        ProviderErrorCategory.SCHEMA,
                        ProviderErrorReason.RESPONSE_ENVELOPE_INVALID,
                    ),
                    (),
                ),
            )
        )
    elif model_output_invalid:
        deepseek = FakeDeepSeekAdapter(
            generation_results=(
                _result(Provider.DEEPSEEK, ModelTextOutput("{invalid"), "candidate"),
            ),
            repair_results=(
                _result(Provider.DEEPSEEK, ModelTextOutput("{still-invalid"), "repair"),
            ),
        )
    else:
        deepseek = FakeDeepSeekAdapter(
            generation_results=(
                _result(
                    Provider.DEEPSEEK,
                    ModelTextOutput(_candidate_json(poi_source_id)),
                    "candidate",
                ),
            )
        )
    repository = InMemoryPlanningJobRepository(
        clock=lambda: NOW,
        id_factory=iter(
            (
                JOB_ID,
                UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            )
        ).__next__,
    )
    reserved = await repository.get_or_create(_request())
    orchestrator = OfflinePlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        lambda: ToolCallGovernor(clock=lambda: 0.0),
    )
    executor = ProviderPlanningJobExecutor(repository, orchestrator, clock=lambda: NOW)
    await executor.execute(reserved.job.job_id)
    return await repository.get(reserved.job.job_id), amap


def test_executor_publishes_real_orchestration_shape_using_only_offline_ports() -> None:
    job, amap = asyncio.run(_execute())

    assert job.status is PlanningStatus.PARTIAL
    assert job.result is not None
    assert job.result.plan is not None
    assert job.result.plan.days[0].accommodation_location_id == HOTEL_ID
    assert len(job.result.plan.days[0].routes) == 2
    assert len(job.result.plan.days[1].routes) == 2
    assert job.result.plan.days[0].weather is not None
    assert job.result.plan.budget_summary.known_total.amount == Decimal("2180.00")
    assert job.result.plan.budget_summary.unknown_count == 1
    assert any(source.provider.value == "qweather" for source in job.result.sources)
    qweather_sources = tuple(
        source for source in job.result.sources if source.provider.value == "qweather"
    )
    assert all(
        source.attributions == ("QWeather attribution from fixture",) for source in qweather_sources
    )
    assert any(source.provider.value == "deepseek" for source in job.result.sources)
    assert [call.operation.value for call in amap.calls[:3]] == [
        "resolve_city",
        "search_pois",
        "search_pois",
    ]


def test_local_candidate_failure_is_not_mislabeled_as_provider_schema() -> None:
    job, _ = asyncio.run(_execute(model_output_invalid=True))

    assert job.status is PlanningStatus.FAILED
    assert job.result is not None
    assert [(error.code.value, error.retryable) for error in job.result.errors] == [
        ("model_output_invalid", False)
    ]
    assert job.result.errors[0].diagnostic_code == "candidate_local_validation_failed"
    assert any(source.provider.value == "amap" for source in job.result.sources)
    assert any(source.provider.value == "qweather" for source in job.result.sources)
    assert all(source.provider.value != "deepseek" for source in job.result.sources)


def test_adapter_schema_failure_keeps_stable_provider_error_distinct() -> None:
    job, _ = asyncio.run(_execute(provider_schema_invalid=True))

    assert job.status is PlanningStatus.FAILED
    assert job.result is not None
    assert [(error.code.value, error.retryable) for error in job.result.errors] == [
        ("provider_schema_invalid", False)
    ]
    assert job.result.errors[0].diagnostic_code == "response_envelope_invalid"
