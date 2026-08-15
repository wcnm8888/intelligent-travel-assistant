"""Deterministic, offline contract tests for programmable provider fakes."""

import ast
import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeCall,
    FakeDeepSeekAdapter,
    FakeOperation,
    FakeQWeatherAdapter,
    FakeScriptError,
)
from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CandidateActivity,
    CandidateDay,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    ModelTextOutput,
    PlanCandidate,
    PlanningContext,
    PlanningLocation,
    PlanningObservation,
    PlanningToolName,
    PoiCandidate,
    PoiSearchRequest,
    PoiSearchResult,
    QWeatherPort,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    Money,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "intelligent_travel_assistant"
FAKES_ROOT = PACKAGE_ROOT / "adapters" / "fakes"
FETCHED_AT = datetime(2026, 10, 1, 8, tzinfo=UTC)
VALID_UNTIL = FETCHED_AT + timedelta(hours=1)
HOTEL_ID = UUID("10000000-0000-0000-0000-000000000001")
POI_ID = UUID("10000000-0000-0000-0000-000000000002")
SOURCE_ID = UUID("20000000-0000-0000-0000-000000000001")
COORDINATES = Coordinates(
    longitude=Decimal("120.1551"),
    latitude=Decimal("30.2741"),
    coordinate_system=CoordinateSystem.PROVIDER_NATIVE,
)


def _source(provider: Provider) -> SourceRecord:
    return SourceRecord(
        source_id=SOURCE_ID,
        provider=provider,
        source_type="synthetic_contract_fixture",
        fetched_at=FETCHED_AT,
        valid_until=VALID_UNTIL,
    )


def _available_result[T](
    provider: Provider,
    data: T,
    *,
    status: ProviderResultStatus = ProviderResultStatus.OK,
    error: ProviderError | None = None,
) -> ProviderResult[T]:
    return ProviderResult(
        status=status,
        provider=provider,
        data=data,
        fetched_at=FETCHED_AT,
        valid_until=VALID_UNTIL,
        warnings=("synthetic test data; not a live provider response",),
        error=error,
        source_records=(_source(provider),),
    )


def _unavailable_result[T](
    provider: Provider,
    category: ProviderErrorCategory,
) -> ProviderResult[T]:
    return ProviderResult(
        status=ProviderResultStatus.UNAVAILABLE,
        provider=provider,
        data=None,
        fetched_at=None,
        valid_until=None,
        warnings=("synthetic test failure; no live provider was called",),
        error=ProviderError(category),
        source_records=(),
    )


def _city(name: str) -> CityResolution:
    return CityResolution(
        city_name=name,
        adcode="330100",
        citycode="0571",
        center=COORDINATES,
    )


def _planning_context() -> PlanningContext:
    return PlanningContext(
        city_name="杭州",
        city_adcode="330100",
        start_date=date(2026, 10, 2),
        end_date=date(2026, 10, 3),
        travelers=1,
        budget=Money(Decimal("1000")),
        interests=("历史",),
        hard_constraints=(),
        allowed_tools=tuple(PlanningToolName),
        locations=(PlanningLocation(HOTEL_ID, "住宿", "hotel", "330100"),),
        observations=(PlanningObservation("weather", "synthetic summary", (SOURCE_ID,)),),
    )


def _candidate() -> PlanCandidate:
    activity = CandidateActivity(
        location_id=POI_ID,
        local_date=date(2026, 10, 2),
        title="synthetic visit",
        start_time=time(9),
        end_time=time(10),
        source_ids=(SOURCE_ID,),
    )
    return PlanCandidate(
        intent_summary="synthetic candidate",
        days=(CandidateDay(date(2026, 10, 2), (activity,)),),
        explanation="synthetic explanation",
        warnings=("synthetic",),
    )


def test_amap_scripts_are_ordered_and_independent_per_operation() -> None:
    city_request = CityResolutionRequest("杭州")
    poi_request = PoiSearchRequest("330100", ("博物馆",), ("attraction",), 3)
    first = _available_result(Provider.AMAP, _city("杭州-1"))
    second = _available_result(Provider.AMAP, _city("杭州-2"))
    pois = _available_result(Provider.AMAP, PoiSearchResult(()))
    fake = FakeAmapAdapter(
        resolve_city_results=(first, second),
        search_pois_results=(pois,),
    )

    assert asyncio.run(fake.resolve_city(city_request)) is first
    assert asyncio.run(fake.search_pois(poi_request)) is pois
    assert asyncio.run(fake.resolve_city(city_request)) is second
    assert fake.calls == (
        FakeCall(1, FakeOperation.RESOLVE_CITY, city_request),
        FakeCall(2, FakeOperation.SEARCH_POIS, poi_request),
        FakeCall(3, FakeOperation.RESOLVE_CITY, city_request),
    )


def test_calls_are_immutable_snapshots_and_include_failed_attempts() -> None:
    request = CityResolutionRequest("杭州")
    fake = FakeAmapAdapter(resolve_city_results=())

    with pytest.raises(FakeScriptError, match="fake_script_exhausted") as raised:
        asyncio.run(fake.resolve_city(request))

    snapshot = fake.calls
    assert raised.value.code == "fake_script_exhausted"
    assert snapshot == (FakeCall(1, FakeOperation.RESOLVE_CITY, request),)
    with pytest.raises(FrozenInstanceError):
        snapshot[0].sequence = 2  # type: ignore[misc]


def test_unconfigured_and_exhausted_scripts_fail_differently_without_fallback() -> None:
    request = CityResolutionRequest("杭州")

    with pytest.raises(FakeScriptError) as unconfigured:
        asyncio.run(FakeAmapAdapter().resolve_city(request))
    with pytest.raises(FakeScriptError) as exhausted:
        asyncio.run(FakeAmapAdapter(resolve_city_results=()).resolve_city(request))

    assert unconfigured.value.code == "fake_script_unconfigured"
    assert exhausted.value.code == "fake_script_exhausted"
    assert unconfigured.value.operation is FakeOperation.RESOLVE_CITY
    assert "杭州" not in str(unconfigured.value)


def test_all_three_fakes_satisfy_async_port_contracts() -> None:
    city_result = _available_result(Provider.AMAP, _city("杭州"))
    weather_result = _available_result(
        Provider.QWEATHER,
        WeatherForecastResult(location_id=HOTEL_ID, days=()),
    )
    candidate_result = _available_result(Provider.DEEPSEEK, ModelTextOutput("synthetic text"))
    amap = FakeAmapAdapter(resolve_city_results=(city_result,))
    qweather = FakeQWeatherAdapter(weather_forecast_results=(weather_result,))
    deepseek = FakeDeepSeekAdapter(generation_results=(candidate_result,))

    async def exercise(
        amap_port: AmapPort,
        qweather_port: QWeatherPort,
        deepseek_port: DeepSeekPort,
    ) -> tuple[object, object, object]:
        return (
            await amap_port.resolve_city(CityResolutionRequest("杭州")),
            await qweather_port.get_weather_forecast(
                WeatherForecastRequest(HOTEL_ID, COORDINATES, date(2026, 10, 2), date(2026, 10, 3))
            ),
            await deepseek_port.generate_plan_candidate(_planning_context()),
        )

    assert asyncio.run(exercise(amap, qweather, deepseek)) == (
        city_result,
        weather_result,
        candidate_result,
    )
    assert amap.is_synthetic and qweather.is_synthetic and deepseek.is_synthetic


def test_every_amap_operation_can_be_scripted() -> None:
    poi = PoiCandidate(POI_ID, "博物馆", "attraction", "330100", None, COORDINATES)
    route = RouteLeg(HOTEL_ID, POI_ID, RouteMode.WALKING, 1000, 15, (SOURCE_ID,))
    poi_result = _available_result(Provider.AMAP, PoiSearchResult((poi,)))
    route_result = _available_result(Provider.AMAP, route)
    fake = FakeAmapAdapter(
        search_pois_results=(poi_result,),
        calculate_routes_results=(route_result,),
    )

    assert (
        asyncio.run(fake.search_pois(PoiSearchRequest("330100", ("博物馆",), ("attraction",), 3)))
        is poi_result
    )
    assert (
        asyncio.run(
            fake.calculate_routes(
                RouteCalculationRequest(
                    HOTEL_ID,
                    POI_ID,
                    COORDINATES,
                    COORDINATES,
                    "0571",
                    "0571",
                    RouteMode.WALKING,
                )
            )
        )
        is route_result
    )


def test_every_qweather_operation_can_be_scripted() -> None:
    forecast = _available_result(
        Provider.QWEATHER, WeatherForecastResult(location_id=HOTEL_ID, days=())
    )
    alerts = _available_result(
        Provider.QWEATHER, WeatherAlertsResult(location_id=HOTEL_ID, alerts=())
    )
    fake = FakeQWeatherAdapter(
        weather_forecast_results=(forecast,),
        weather_alert_results=(alerts,),
    )

    assert (
        asyncio.run(
            fake.get_weather_forecast(
                WeatherForecastRequest(HOTEL_ID, COORDINATES, date(2026, 10, 2), date(2026, 10, 3))
            )
        )
        is forecast
    )
    assert (
        asyncio.run(
            fake.get_current_weather_alerts(CurrentWeatherAlertsRequest(HOTEL_ID, COORDINATES))
        )
        is alerts
    )


@pytest.mark.parametrize("category", tuple(ProviderErrorCategory))
def test_all_safe_error_categories_are_injectable_without_retry_or_sleep(
    category: ProviderErrorCategory,
) -> None:
    result: ProviderResult[CityResolution] = _unavailable_result(Provider.AMAP, category)
    fake = FakeAmapAdapter(resolve_city_results=(result,))

    observed = asyncio.run(fake.resolve_city(CityResolutionRequest("杭州")))

    assert observed is result
    assert observed.error is not None
    assert observed.error.category is category


def test_partial_result_is_injectable_without_being_upgraded() -> None:
    result = _available_result(
        Provider.AMAP,
        _city("杭州"),
        status=ProviderResultStatus.PARTIAL,
        error=ProviderError(ProviderErrorCategory.EMPTY_RESULT),
    )
    fake = FakeAmapAdapter(resolve_city_results=(result,))

    assert asyncio.run(fake.resolve_city(CityResolutionRequest("杭州"))).status is (
        ProviderResultStatus.PARTIAL
    )


def test_fake_rejects_wrong_provider_or_non_synthetic_script_data() -> None:
    wrong_provider = _available_result(Provider.QWEATHER, _city("杭州"))
    live_source = SourceRecord(
        source_id=SOURCE_ID,
        provider=Provider.AMAP,
        source_type="geocoding_api",
        fetched_at=FETCHED_AT,
        valid_until=VALID_UNTIL,
    )
    non_synthetic = ProviderResult(
        status=ProviderResultStatus.OK,
        provider=Provider.AMAP,
        data=_city("杭州"),
        fetched_at=FETCHED_AT,
        valid_until=VALID_UNTIL,
        warnings=(),
        error=None,
        source_records=(live_source,),
    )

    with pytest.raises(FakeScriptError) as mismatch:
        FakeAmapAdapter(resolve_city_results=(wrong_provider,))
    with pytest.raises(FakeScriptError) as not_synthetic:
        FakeAmapAdapter(resolve_city_results=(non_synthetic,))

    assert mismatch.value.code == "fake_result_provider_mismatch"
    assert not_synthetic.value.code == "fake_result_not_synthetic"


def test_fake_implementation_has_no_network_environment_sleep_or_real_adapter_imports() -> None:
    forbidden_import_roots = {
        "aiohttp",
        "httpx",
        "httpx2",
        "openai",
        "os",
        "requests",
        "socket",
        "urllib",
    }
    observed_imports: list[str] = []
    observed_calls: list[str] = []
    for path in FAKES_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                modules = ()
            observed_imports.extend(
                module for module in modules if module.split(".", 1)[0] in forbidden_import_roots
            )
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func).lower()
                if "sleep" in rendered or "getenv" in rendered or "environ" in rendered:
                    observed_calls.append(rendered)

    assert observed_imports == []
    assert observed_calls == []


def test_production_entrypoints_do_not_import_or_default_wire_fakes() -> None:
    for name in ("app.py", "main.py"):
        rendered = (PACKAGE_ROOT / name).read_text(encoding="utf-8").lower()
        assert "adapters.fakes" not in rendered
        assert "fakeamapadapter" not in rendered
        assert "fakeqweatheradapter" not in rendered
        assert "fakedeepseekadapter" not in rendered
