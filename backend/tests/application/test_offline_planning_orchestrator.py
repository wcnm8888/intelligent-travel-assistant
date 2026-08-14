"""Offline application orchestration over typed ports and the state machine."""

import ast
import asyncio
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
    FakeOperation,
    FakeQWeatherAdapter,
)
from intelligent_travel_assistant.application.planning import (
    AccommodationAnchor,
    FinalValidationIssueCode,
)
from intelligent_travel_assistant.application.ports import (
    CandidateActivity,
    CandidateDay,
    CityResolution,
    DailyWeather,
    ModelTextOutput,
    PlanCandidate,
    PlanningContext,
    PoiCandidate,
    PoiSearchResult,
    WeatherAlertsResult,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.services import (
    OfflinePlanningOrchestrator,
    OfflinePlanningRequest,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    BudgetCostItem,
    Coordinates,
    CoordinateSystem,
    CostCategory,
    CostConfidence,
    DailyAvailability,
    Money,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
    TripRequestInput,
)

SERVICE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "application"
    / "services"
)
NOW = datetime(2026, 8, 13, 2, tzinfo=UTC)
FETCHED_AT = NOW + timedelta(seconds=1)
VALID_UNTIL = FETCHED_AT + timedelta(hours=1)
WEATHER_LOCATION_ID = UUID("90000000-0000-4000-8000-000000000001")
POI_ONE_ID = UUID("90000000-0000-4000-8000-000000000002")
POI_TWO_ID = UUID("90000000-0000-4000-8000-000000000003")
HOTEL_ID = UUID("90000000-0000-4000-8000-000000000010")
SOURCE_IDS = {
    Provider.AMAP: uuid5(NAMESPACE_URL, "synthetic:amap:poi_search"),
    Provider.QWEATHER: UUID("60000000-0000-4000-8000-000000000001"),
    Provider.DEEPSEEK: UUID("70000000-0000-4000-8000-000000000001"),
}
CITY_CENTER = Coordinates(
    Decimal("120.1551"),
    Decimal("30.2741"),
    CoordinateSystem.PROVIDER_NATIVE,
)
POI_ONE_COORDINATES = Coordinates(
    Decimal("120.1600"),
    Decimal("30.2500"),
    CoordinateSystem.PROVIDER_NATIVE,
)
POI_TWO_COORDINATES = Coordinates(
    Decimal("120.1400"),
    Decimal("30.2600"),
    CoordinateSystem.PROVIDER_NATIVE,
)
HOTEL_COORDINATES = Coordinates(
    Decimal("120.1500"),
    Decimal("30.2550"),
    CoordinateSystem.PROVIDER_NATIVE,
)


def _source(provider: Provider, source_type: str) -> SourceRecord:
    return SourceRecord(
        uuid5(NAMESPACE_URL, f"synthetic:{provider.value}:{source_type}"),
        provider,
        f"synthetic_{source_type}",
        FETCHED_AT,
        VALID_UNTIL,
    )


def _available[T](
    provider: Provider,
    data: T,
    *,
    status: ProviderResultStatus = ProviderResultStatus.OK,
    error: ProviderError | None = None,
    source_type: str = "fixture",
) -> ProviderResult[T]:
    return ProviderResult(
        status,
        provider,
        data,
        FETCHED_AT,
        VALID_UNTIL,
        ("synthetic offline orchestration fixture",),
        error,
        (_source(provider, source_type),),
    )


def _unavailable[T](
    provider: Provider,
    category: ProviderErrorCategory,
) -> ProviderResult[T]:
    return ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        provider,
        None,
        None,
        None,
        ("synthetic offline provider failure",),
        ProviderError(category),
        (),
    )


def _request() -> OfflinePlanningRequest:
    return OfflinePlanningRequest(
        trip=TripRequestInput(
            city="杭州",
            start_date=date(2026, 8, 15),
            end_date=date(2026, 8, 16),
            travelers=2,
            interests=("自然", "历史"),
            free_text="节奏不要太赶",
            evaluated_at=NOW,
        ),
        budget=Money(Decimal("4000.00")),
        hard_constraints=(),
        weather_location_id=WEATHER_LOCATION_ID,
        poi_keywords=("西湖", "博物馆"),
        poi_categories=("scenic_area", "museum"),
        poi_limit=3,
        route_mode=RouteMode.PUBLIC_TRANSIT,
        accommodation=AccommodationAnchor(HOTEL_ID, "330100", HOTEL_COORDINATES),
        day_windows=(
            DailyAvailability(0, time(8), time(18)),
            DailyAvailability(1, time(8), time(18)),
        ),
        cost_items=(),
        evaluated_at=FETCHED_AT + timedelta(minutes=1),
    )


def _city() -> CityResolution:
    return CityResolution("杭州市", "330100", "0571", CITY_CENTER)


def _pois() -> PoiSearchResult:
    return PoiSearchResult(
        (
            PoiCandidate(
                POI_ONE_ID,
                "西湖 synthetic POI",
                "scenic_area",
                "330100",
                "synthetic address",
                POI_ONE_COORDINATES,
            ),
            PoiCandidate(
                POI_TWO_ID,
                "博物馆 synthetic POI",
                "museum",
                "330100",
                "synthetic address",
                POI_TWO_COORDINATES,
            ),
        )
    )


def _forecast() -> WeatherForecastResult:
    return WeatherForecastResult(
        WEATHER_LOCATION_ID,
        (
            DailyWeather(date(2026, 8, 15), "多云", "多云", Decimal("26"), Decimal("34")),
            DailyWeather(date(2026, 8, 16), "阵雨", "多云", Decimal("25"), Decimal("32")),
        ),
    )


def _candidate() -> PlanCandidate:
    return PlanCandidate(
        intent_summary="synthetic two-day candidate",
        days=(
            CandidateDay(
                date(2026, 8, 15),
                (
                    CandidateActivity(
                        POI_ONE_ID,
                        date(2026, 8, 15),
                        "西湖步行",
                        time(10),
                        time(12),
                        (SOURCE_IDS[Provider.AMAP],),
                    ),
                ),
            ),
            CandidateDay(
                date(2026, 8, 16),
                (
                    CandidateActivity(
                        POI_TWO_ID,
                        date(2026, 8, 16),
                        "博物馆参观",
                        time(10),
                        time(12),
                        (SOURCE_IDS[Provider.AMAP],),
                    ),
                ),
            ),
        ),
        explanation="synthetic candidate; pending deterministic validation",
        warnings=("synthetic",),
    )


def _candidate_json() -> str:
    candidate = _candidate()
    return json.dumps(
        {
            "intent_summary": candidate.intent_summary,
            "days": [
                {
                    "local_date": day.local_date.isoformat(),
                    "activities": [
                        {
                            "location_id": str(activity.location_id),
                            "local_date": activity.local_date.isoformat(),
                            "title": activity.title,
                            "start_time": activity.start_time.isoformat(),
                            "end_time": activity.end_time.isoformat(),
                            "source_ids": [str(item) for item in activity.source_ids],
                        }
                        for activity in day.activities
                    ],
                }
                for day in candidate.days
            ],
            "explanation": candidate.explanation,
            "warnings": list(candidate.warnings),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _route(origin: UUID, destination: UUID, *, minutes: int = 30) -> RouteLeg:
    return RouteLeg(
        origin,
        destination,
        RouteMode.PUBLIC_TRANSIT,
        3000,
        minutes,
        (uuid5(NAMESPACE_URL, "synthetic:amap:route"),),
    )


def _routes() -> tuple[RouteLeg, ...]:
    return (
        _route(HOTEL_ID, POI_ONE_ID),
        _route(POI_ONE_ID, HOTEL_ID),
        _route(HOTEL_ID, POI_TWO_ID),
        _route(POI_TWO_ID, HOTEL_ID),
    )


def _build_orchestrator(
    *,
    city: ProviderResult[CityResolution] | None = None,
    pois: ProviderResult[PoiSearchResult] | None = None,
    forecast: ProviderResult[WeatherForecastResult] | None = None,
    alerts: ProviderResult[WeatherAlertsResult] | None = None,
    candidate: ProviderResult[ModelTextOutput] | None = None,
    routes: tuple[ProviderResult[RouteLeg], ...] | None = None,
    copies: int = 1,
) -> tuple[
    OfflinePlanningOrchestrator,
    FakeAmapAdapter,
    FakeQWeatherAdapter,
    FakeDeepSeekAdapter,
]:
    city_result = city or _available(Provider.AMAP, _city(), source_type="geocode")
    poi_result = pois or _available(Provider.AMAP, _pois(), source_type="poi_search")
    forecast_result = forecast or _available(Provider.QWEATHER, _forecast(), source_type="forecast")
    alert_result = alerts or _available(
        Provider.QWEATHER,
        WeatherAlertsResult(WEATHER_LOCATION_ID, ()),
        source_type="alerts",
    )
    candidate_result = candidate or _available(
        Provider.DEEPSEEK,
        ModelTextOutput(_candidate_json()),
        source_type="plan_candidate",
    )
    route_results = routes or tuple(
        _available(Provider.AMAP, item, source_type="route") for item in _routes()
    )
    amap = FakeAmapAdapter(
        resolve_city_results=(city_result,) * copies,
        search_pois_results=(poi_result,) * copies,
        calculate_routes_results=route_results * copies,
    )
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=(forecast_result,) * copies,
        weather_alert_results=(alert_result,) * copies,
    )
    deepseek = FakeDeepSeekAdapter(generation_results=(candidate_result,) * copies)
    return (
        OfflinePlanningOrchestrator(
            amap,
            qweather,
            deepseek,
            governor_factory=lambda: ToolCallGovernor(clock=lambda: 0.0),
        ),
        amap,
        qweather,
        deepseek,
    )


def test_happy_path_completes_four_route_legs_and_finishes_ready() -> None:
    orchestrator, amap, qweather, deepseek = _build_orchestrator()

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.READY
    assert outcome.state_history == (
        PlanningStatus.DRAFT,
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.ENRICHING_ROUTES,
        PlanningStatus.VALIDATING,
        PlanningStatus.READY,
    )
    assert outcome.city_result is not None and outcome.city_result.data == _city()
    assert outcome.poi_result is not None and outcome.poi_result.data == _pois()
    assert outcome.weather_result is not None and outcome.weather_result.data == _forecast()
    assert outcome.alert_result is not None
    assert outcome.candidate_result is not None and outcome.candidate_result.data == _candidate()
    assert tuple(item.result.data for item in outcome.route_enrichments if item.result) == _routes()
    assert outcome.final_validation is not None
    assert outcome.final_validation.status is PlanningStatus.READY
    assert outcome.final_validation.issues == ()
    assert tuple(record.capability for record in outcome.tool_calls.records) == (
        ToolCallCapability.RESOLVE_CITY,
        ToolCallCapability.SEARCH_POIS,
        ToolCallCapability.GET_WEATHER_FORECAST,
        ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
        ToolCallCapability.GENERATE_PLAN_CANDIDATE,
        ToolCallCapability.CALCULATE_ROUTES,
        ToolCallCapability.CALCULATE_ROUTES,
        ToolCallCapability.CALCULATE_ROUTES,
        ToolCallCapability.CALCULATE_ROUTES,
    )
    assert [call.operation for call in amap.calls] == [
        FakeOperation.RESOLVE_CITY,
        FakeOperation.SEARCH_POIS,
        FakeOperation.CALCULATE_ROUTES,
        FakeOperation.CALCULATE_ROUTES,
        FakeOperation.CALCULATE_ROUTES,
        FakeOperation.CALCULATE_ROUTES,
    ]
    assert [call.operation for call in qweather.calls] == [
        FakeOperation.GET_WEATHER_FORECAST,
        FakeOperation.GET_CURRENT_WEATHER_ALERTS,
    ]
    assert [call.operation for call in deepseek.calls] == [FakeOperation.GENERATE_PLAN_CANDIDATE]
    planning_context = cast(PlanningContext, deepseek.calls[0].request)
    assert planning_context.city_name == "杭州市"
    assert planning_context.budget == Money(Decimal("4000.00"))
    assert planning_context.free_text == _request().trip.free_text
    assert planning_context.route_mode is RouteMode.PUBLIC_TRANSIT
    assert tuple(item.day_offset for item in planning_context.day_windows) == (
        0,
        1,
    )
    assert planning_context.accommodation is not None
    assert planning_context.accommodation.location_id == HOTEL_ID
    assert planning_context.activity_source_ids == (SOURCE_IDS[Provider.AMAP],)
    assert "provider result ok" not in " ".join(
        item.summary for item in planning_context.observations
    )
    assert tuple(item.location_id for item in planning_context.locations) == (
        POI_ONE_ID,
        POI_TWO_ID,
    )


def test_default_weather_anchor_uses_matching_accommodation_coordinates() -> None:
    orchestrator, _, qweather, _ = _build_orchestrator()
    request = replace(_request(), weather_location_id=None)

    asyncio.run(orchestrator.plan(request))

    forecast_request = qweather.calls[0].request
    alert_request = qweather.calls[1].request
    assert forecast_request.location_id == HOTEL_ID  # type: ignore[union-attr]
    assert forecast_request.coordinates == HOTEL_COORDINATES  # type: ignore[union-attr]
    assert alert_request.location_id == HOTEL_ID  # type: ignore[union-attr]
    assert alert_request.coordinates == HOTEL_COORDINATES  # type: ignore[union-attr]


def test_noncritical_weather_failure_is_preserved_and_finishes_partial() -> None:
    weather_failure: ProviderResult[WeatherForecastResult] = _unavailable(
        Provider.QWEATHER,
        ProviderErrorCategory.TIMEOUT,
    )
    orchestrator, amap, _, deepseek = _build_orchestrator(forecast=weather_failure)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.state_history[-2:] == (
        PlanningStatus.VALIDATING,
        PlanningStatus.PARTIAL,
    )
    assert outcome.weather_result is weather_failure
    assert outcome.weather_result.error is not None
    assert outcome.weather_result.error.category is ProviderErrorCategory.TIMEOUT
    assert outcome.candidate_result is not None
    assert len(amap.calls) == 6
    assert len(deepseek.calls) == 1


def test_route_unavailable_finishes_partial_without_claiming_validation() -> None:
    route_failure: ProviderResult[RouteLeg] = _unavailable(
        Provider.AMAP,
        ProviderErrorCategory.TIMEOUT,
    )
    orchestrator, _, _, _ = _build_orchestrator(
        routes=(route_failure,)
        + tuple(_available(Provider.AMAP, item, source_type="route") for item in _routes()[1:])
    )

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.state_history[-2:] == (
        PlanningStatus.VALIDATING,
        PlanningStatus.PARTIAL,
    )
    assert outcome.route_result is route_failure
    assert outcome.candidate_result is not None
    assert len(outcome.route_enrichments) == 4


def test_deepseek_unavailable_is_critical_and_never_calls_route() -> None:
    model_failure: ProviderResult[ModelTextOutput] = _unavailable(
        Provider.DEEPSEEK,
        ProviderErrorCategory.SERVER,
    )
    orchestrator, amap, qweather, deepseek = _build_orchestrator(candidate=model_failure)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.FAILED
    assert outcome.state_history[-2:] == (PlanningStatus.PLANNING, PlanningStatus.FAILED)
    assert outcome.candidate_result is not None
    assert outcome.candidate_result.status is model_failure.status
    assert outcome.candidate_result.warnings == model_failure.warnings
    assert outcome.candidate_result.error == model_failure.error
    assert outcome.candidate_result.source_records == model_failure.source_records
    assert outcome.candidate_result.error is not None
    assert outcome.candidate_result.error.retryable is True
    assert [call.operation for call in amap.calls] == [
        FakeOperation.RESOLVE_CITY,
        FakeOperation.SEARCH_POIS,
    ]
    assert len(qweather.calls) == 2
    assert len(deepseek.calls) == 1
    assert outcome.route_result is None


def test_city_unavailable_fails_fast_without_inventing_downstream_results() -> None:
    city_failure: ProviderResult[CityResolution] = _unavailable(
        Provider.AMAP,
        ProviderErrorCategory.EMPTY_RESULT,
    )
    orchestrator, amap, qweather, deepseek = _build_orchestrator(city=city_failure)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.FAILED
    assert outcome.state_history == (
        PlanningStatus.DRAFT,
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.FAILED,
    )
    assert outcome.city_result is city_failure
    assert outcome.poi_result is None
    assert outcome.candidate_result is None
    assert [call.operation for call in amap.calls] == [FakeOperation.RESOLVE_CITY]
    assert qweather.calls == ()
    assert deepseek.calls == ()


def test_poi_unavailable_fails_before_weather_or_model_calls() -> None:
    poi_failure: ProviderResult[PoiSearchResult] = _unavailable(
        Provider.AMAP,
        ProviderErrorCategory.EMPTY_RESULT,
    )
    orchestrator, amap, qweather, deepseek = _build_orchestrator(pois=poi_failure)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.FAILED
    assert outcome.poi_result is poi_failure
    assert [call.operation for call in amap.calls] == [
        FakeOperation.RESOLVE_CITY,
        FakeOperation.SEARCH_POIS,
    ]
    assert qweather.calls == ()
    assert deepseek.calls == ()


def test_partial_available_provider_result_is_not_upgraded_to_full_candidate() -> None:
    partial_pois = _available(
        Provider.AMAP,
        _pois(),
        status=ProviderResultStatus.PARTIAL,
        error=ProviderError(ProviderErrorCategory.EMPTY_RESULT),
        source_type="poi_search",
    )
    orchestrator, _, _, _ = _build_orchestrator(pois=partial_pois)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.poi_result is partial_pois
    assert outcome.poi_result.status is ProviderResultStatus.PARTIAL


def test_known_over_budget_conflict_has_priority_over_partial_provider_data() -> None:
    partial_forecast = _available(
        Provider.QWEATHER,
        _forecast(),
        status=ProviderResultStatus.PARTIAL,
        error=ProviderError(ProviderErrorCategory.EMPTY_RESULT),
        source_type="partial_forecast",
    )
    request = _request()
    over_budget = BudgetCostItem(
        UUID("93000000-0000-4000-8000-000000000001"),
        CostCategory.ACCOMMODATION,
        CostConfidence.USER_PROVIDED,
        Money(Decimal("4000.01")),
    )
    request = OfflinePlanningRequest(
        request.trip,
        request.budget,
        request.hard_constraints,
        request.weather_location_id,
        request.poi_keywords,
        request.poi_categories,
        request.poi_limit,
        request.route_mode,
        request.accommodation,
        request.day_windows,
        (over_budget,),
        request.evaluated_at,
    )
    orchestrator, _, _, _ = _build_orchestrator(forecast=partial_forecast)

    outcome = asyncio.run(orchestrator.plan(request))

    assert outcome.status is PlanningStatus.CONFLICT
    assert outcome.final_validation is not None
    assert outcome.final_validation.budget.known_total == Money(Decimal("4000.01"))


def test_unknown_cost_never_becomes_zero_and_finishes_partial() -> None:
    request = _request()
    unknown = BudgetCostItem(
        UUID("93000000-0000-4000-8000-000000000002"),
        CostCategory.TICKET,
        CostConfidence.UNKNOWN,
        None,
    )
    request = OfflinePlanningRequest(
        request.trip,
        request.budget,
        request.hard_constraints,
        request.weather_location_id,
        request.poi_keywords,
        request.poi_categories,
        request.poi_limit,
        request.route_mode,
        request.accommodation,
        request.day_windows,
        (unknown,),
        request.evaluated_at,
    )
    orchestrator, _, _, _ = _build_orchestrator()

    outcome = asyncio.run(orchestrator.plan(request))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.final_validation is not None
    assert outcome.final_validation.budget.unknown_count == 1
    assert outcome.final_validation.budget.known_total == Money(Decimal("0.00"))


def test_route_result_with_wrong_endpoints_is_rejected_as_partial() -> None:
    wrong = _available(
        Provider.AMAP,
        _route(POI_ONE_ID, POI_TWO_ID),
        source_type="route",
    )
    good = tuple(_available(Provider.AMAP, item, source_type="route") for item in _routes()[1:])
    orchestrator, _, _, _ = _build_orchestrator(routes=(wrong,) + good)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.ROUTE_RESULT_INVALID in {
        item.code for item in outcome.final_validation.issues
    }


def test_missing_accommodation_coordinates_skips_calls_and_remains_partial() -> None:
    request = _request()
    request = OfflinePlanningRequest(
        request.trip,
        request.budget,
        request.hard_constraints,
        request.weather_location_id,
        request.poi_keywords,
        request.poi_categories,
        request.poi_limit,
        request.route_mode,
        AccommodationAnchor(HOTEL_ID, "330100", None),
        request.day_windows,
        request.cost_items,
        request.evaluated_at,
    )
    orchestrator, amap, _, _ = _build_orchestrator()

    outcome = asyncio.run(orchestrator.plan(request))

    assert outcome.status is PlanningStatus.PARTIAL
    assert [item.operation for item in amap.calls].count(FakeOperation.CALCULATE_ROUTES) == 0
    assert len(outcome.route_enrichments) == 4


def test_weather_that_does_not_cover_both_dates_remains_partial() -> None:
    forecast = WeatherForecastResult(WEATHER_LOCATION_ID, (_forecast().days[0],))
    orchestrator, _, _, _ = _build_orchestrator(
        forecast=_available(Provider.QWEATHER, forecast, source_type="forecast")
    )

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.WEATHER_INCOMPLETE in {
        item.code for item in outcome.final_validation.issues
    }


def test_weather_for_wrong_location_remains_partial() -> None:
    forecast = WeatherForecastResult(POI_ONE_ID, _forecast().days)
    orchestrator, _, _, _ = _build_orchestrator(
        forecast=_available(Provider.QWEATHER, forecast, source_type="forecast")
    )

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.WEATHER_INCOMPLETE in {
        item.code for item in outcome.final_validation.issues
    }


def test_unavailable_alerts_prevent_ready_without_erasing_plan() -> None:
    alert_failure: ProviderResult[WeatherAlertsResult] = _unavailable(
        Provider.QWEATHER,
        ProviderErrorCategory.TIMEOUT,
    )
    orchestrator, _, _, _ = _build_orchestrator(alerts=alert_failure)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.candidate_result is not None
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.PROVIDER_DEGRADED in {
        item.code for item in outcome.final_validation.issues
    }


@pytest.mark.parametrize("category", tuple(ProviderErrorCategory), ids=lambda item: item.value)
@pytest.mark.parametrize("boundary", ("city", "poi", "deepseek"))
def test_critical_provider_failure_matrix_fails_and_short_circuits(
    boundary: str,
    category: ProviderErrorCategory,
) -> None:
    if boundary == "city":
        city_failure: ProviderResult[CityResolution] = _unavailable(Provider.AMAP, category)
        orchestrator, amap, qweather, deepseek = _build_orchestrator(city=city_failure)
        expected_result: ProviderResult[object] = city_failure
        expected_calls = (1, 0, 0)
    elif boundary == "poi":
        poi_failure: ProviderResult[PoiSearchResult] = _unavailable(Provider.AMAP, category)
        orchestrator, amap, qweather, deepseek = _build_orchestrator(pois=poi_failure)
        expected_result = poi_failure
        expected_calls = (2, 0, 0)
    else:
        model_failure: ProviderResult[ModelTextOutput] = _unavailable(
            Provider.DEEPSEEK,
            category,
        )
        orchestrator, amap, qweather, deepseek = _build_orchestrator(candidate=model_failure)
        expected_result = model_failure
        expected_calls = (2, 2, 1)

    outcome = asyncio.run(orchestrator.plan(_request()))

    observed = cast(ProviderResult[object] | None, outcome.city_result)
    if boundary == "poi":
        observed = cast(ProviderResult[object] | None, outcome.poi_result)
    elif boundary == "deepseek":
        observed = cast(ProviderResult[object] | None, outcome.candidate_result)
    assert outcome.status is PlanningStatus.FAILED
    assert outcome.final_validation is None
    assert outcome.route_enrichments == ()
    assert observed == expected_result
    assert observed is not None and observed.error is not None
    assert observed.error.category is category
    assert observed.error.retryable is (category in _RETRYABLE_FAILURES)
    assert (len(amap.calls), len(qweather.calls), len(deepseek.calls)) == expected_calls


@pytest.mark.parametrize("category", tuple(ProviderErrorCategory), ids=lambda item: item.value)
@pytest.mark.parametrize("boundary", ("forecast", "alerts", "route"))
def test_noncritical_provider_failure_matrix_preserves_plan_and_degrades(
    boundary: str,
    category: ProviderErrorCategory,
) -> None:
    if boundary == "forecast":
        forecast_failure: ProviderResult[WeatherForecastResult] = _unavailable(
            Provider.QWEATHER,
            category,
        )
        orchestrator, _, _, _ = _build_orchestrator(forecast=forecast_failure)
        expected_result: ProviderResult[object] = forecast_failure
    elif boundary == "alerts":
        alert_failure: ProviderResult[WeatherAlertsResult] = _unavailable(
            Provider.QWEATHER,
            category,
        )
        orchestrator, _, _, _ = _build_orchestrator(alerts=alert_failure)
        expected_result = alert_failure
    else:
        route_failure: ProviderResult[RouteLeg] = _unavailable(Provider.AMAP, category)
        other_routes = tuple(
            _available(Provider.AMAP, item, source_type="route") for item in _routes()[1:]
        )
        orchestrator, _, _, _ = _build_orchestrator(routes=(route_failure, *other_routes))
        expected_result = route_failure

    outcome = asyncio.run(orchestrator.plan(_request()))

    observed = cast(ProviderResult[object] | None, outcome.weather_result)
    if boundary == "alerts":
        observed = cast(ProviderResult[object] | None, outcome.alert_result)
    elif boundary == "route":
        observed = cast(ProviderResult[object] | None, outcome.route_result)
    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.candidate_result is not None and outcome.candidate_result.data is not None
    assert outcome.final_validation is not None
    assert observed == expected_result
    assert observed is not None and observed.error is not None
    assert observed.error.category is category
    assert observed.error.retryable is (category in _RETRYABLE_FAILURES)


_RETRYABLE_FAILURES = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMITED,
        ProviderErrorCategory.SERVER,
    }
)


def test_route_longer_than_available_gap_is_a_hard_conflict() -> None:
    too_long = _available(
        Provider.AMAP,
        _route(HOTEL_ID, POI_ONE_ID, minutes=121),
        source_type="route",
    )
    good = tuple(_available(Provider.AMAP, item, source_type="route") for item in _routes()[1:])
    orchestrator, _, _, _ = _build_orchestrator(routes=(too_long,) + good)

    outcome = asyncio.run(orchestrator.plan(_request()))

    assert outcome.status is PlanningStatus.CONFLICT
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.ROUTE_CONFLICT in {
        item.code for item in outcome.final_validation.issues
    }


def test_stale_source_blocks_ready_without_becoming_conflict() -> None:
    request = _request()
    request = OfflinePlanningRequest(
        request.trip,
        request.budget,
        request.hard_constraints,
        request.weather_location_id,
        request.poi_keywords,
        request.poi_categories,
        request.poi_limit,
        request.route_mode,
        request.accommodation,
        request.day_windows,
        request.cost_items,
        VALID_UNTIL + timedelta(seconds=1),
    )
    orchestrator, _, _, _ = _build_orchestrator()

    outcome = asyncio.run(orchestrator.plan(request))

    assert outcome.status is PlanningStatus.PARTIAL
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.SOURCE_STALE in {
        item.code for item in outcome.final_validation.issues
    }


def test_activity_outside_explicit_window_finishes_conflict() -> None:
    request = _request()
    request = OfflinePlanningRequest(
        request.trip,
        request.budget,
        request.hard_constraints,
        request.weather_location_id,
        request.poi_keywords,
        request.poi_categories,
        request.poi_limit,
        request.route_mode,
        request.accommodation,
        (
            DailyAvailability(0, time(11), time(18)),
            DailyAvailability(1, time(8), time(18)),
        ),
        request.cost_items,
        request.evaluated_at,
    )
    orchestrator, _, _, _ = _build_orchestrator()

    outcome = asyncio.run(orchestrator.plan(request))

    assert outcome.status is PlanningStatus.CONFLICT
    assert outcome.final_validation is not None
    assert FinalValidationIssueCode.SCHEDULE_CONFLICT in {
        item.code for item in outcome.final_validation.issues
    }


def test_each_run_has_an_independent_immutable_state_history() -> None:
    orchestrator, _, _, _ = _build_orchestrator(copies=2)

    first = asyncio.run(orchestrator.plan(_request()))
    second = asyncio.run(orchestrator.plan(_request()))

    assert first.state_history == second.state_history
    assert first.state_history is not second.state_history
    with pytest.raises(FrozenInstanceError):
        first.status = PlanningStatus.READY  # type: ignore[misc]


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    (
        ("ready", PlanningStatus.READY),
        ("partial", PlanningStatus.PARTIAL),
        ("conflict", PlanningStatus.CONFLICT),
        ("failed", PlanningStatus.FAILED),
    ),
)
def test_deterministic_agent_evaluation_repeats_identical_terminal_decisions(
    scenario: str,
    expected_status: PlanningStatus,
) -> None:
    request = _request()
    if scenario == "partial":
        weather_failure: ProviderResult[WeatherForecastResult] = _unavailable(
            Provider.QWEATHER,
            ProviderErrorCategory.TIMEOUT,
        )
        orchestrator, _, _, _ = _build_orchestrator(forecast=weather_failure, copies=10)
    elif scenario == "conflict":
        too_long = _available(
            Provider.AMAP,
            _route(HOTEL_ID, POI_ONE_ID, minutes=121),
            source_type="route",
        )
        remaining = tuple(
            _available(Provider.AMAP, item, source_type="route") for item in _routes()[1:]
        )
        orchestrator, _, _, _ = _build_orchestrator(
            routes=(too_long, *remaining),
            copies=10,
        )
    elif scenario == "failed":
        model_failure: ProviderResult[ModelTextOutput] = _unavailable(
            Provider.DEEPSEEK,
            ProviderErrorCategory.SERVER,
        )
        orchestrator, _, _, _ = _build_orchestrator(candidate=model_failure, copies=10)
    else:
        orchestrator, _, _, _ = _build_orchestrator(copies=10)

    outcomes = tuple(asyncio.run(orchestrator.plan(request)) for _ in range(10))
    first = outcomes[0]

    assert first.status is expected_status
    assert all(outcome.status is expected_status for outcome in outcomes)
    assert all(outcome.state_history == first.state_history for outcome in outcomes)
    assert all(outcome.candidate_result == first.candidate_result for outcome in outcomes)
    assert all(outcome.route_enrichments == first.route_enrichments for outcome in outcomes)
    assert all(outcome.final_validation == first.final_validation for outcome in outcomes)


def test_orchestrator_has_no_fake_transport_environment_sleep_or_framework_dependency() -> None:
    forbidden_modules = {
        "intelligent_travel_assistant.adapters",
        "fastapi",
        "httpx",
        "openai",
        "os",
        "requests",
        "socket",
        "time",
        "urllib",
    }
    observed_imports: list[str] = []
    observed_calls: list[str] = []
    for path in SERVICE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = (node.module,)
            else:
                modules = ()
            for module in modules:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in forbidden_modules
                ):
                    observed_imports.append(f"{path.name}:{module}")
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node.func).casefold()
                if "sleep" in rendered or "getenv" in rendered or "environ" in rendered:
                    observed_calls.append(rendered)

    assert observed_imports == []
    assert observed_calls == []


def test_governance_rejection_happens_before_the_fake_port_call() -> None:
    orchestrator, amap, qweather, deepseek = _build_orchestrator()
    governor = ToolCallGovernor(clock=lambda: 0.0)
    permit = governor.reserve(
        ToolCallCapability.RESOLVE_CITY,
        PlanningStatus.COLLECTING,
    )
    governor.complete(permit)
    governed = OfflinePlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        governor_factory=lambda: governor,
    )

    with pytest.raises(ToolCallGovernanceError) as raised:
        asyncio.run(governed.plan(_request()))

    assert raised.value.code is ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED
    assert amap.calls == ()
    assert qweather.calls == ()
    assert deepseek.calls == ()
