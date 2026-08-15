"""Offline proof for the live-capable planning-job executor bridge."""

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx2
from fastapi.testclient import TestClient

from intelligent_travel_assistant.adapters.fakes import (
    FakeAmapAdapter,
    FakeDeepSeekAdapter,
    FakeQWeatherAdapter,
)
from intelligent_travel_assistant.adapters.providers import (
    DEEPSEEK_MODEL,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.ports import (
    CityResolution,
    DailyWeather,
    DeepSeekPort,
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


def _request(*, day_zero_end: time = time(18)) -> TripPlanRequest:
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
            DailyTimeWindow(day_offset=0, start_time=time(8), end_time=day_zero_end),
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
                    "selections": [
                        {
                            "location_id": str(POI_ONE_ID),
                            "local_date": "2026-08-15",
                            "title": "西湖步行",
                            "priority_rank": 1,
                            "selection_kind": "required",
                            "duration_class": "standard",
                            "source_ids": [str(poi_source_id)],
                        }
                    ],
                },
                {
                    "local_date": "2026-08-16",
                    "selections": [
                        {
                            "location_id": str(POI_TWO_ID),
                            "local_date": "2026-08-16",
                            "title": "博物馆参观",
                            "priority_rank": 1,
                            "selection_kind": "required",
                            "duration_class": "standard",
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
    deepseek_override: DeepSeekPort | None = None,
    poi_one_category: str = "scenic_area",
    route_results_override: tuple[ProviderResult[RouteLeg], ...] | None = None,
    day_zero_end: time = time(18),
) -> tuple[PlanningJob, FakeAmapAdapter, InMemoryPlanningJobRepository]:
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
                PoiCandidate(POI_ONE_ID, "西湖", poi_one_category, "330100", None, POI_ONE_COORDS),
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
    routes = route_results_override or tuple(
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
    deepseek: DeepSeekPort
    if deepseek_override is not None:
        deepseek = deepseek_override
    elif provider_schema_invalid:
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
    reserved = await repository.get_or_create(_request(day_zero_end=day_zero_end))
    orchestrator = OfflinePlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        lambda: ToolCallGovernor(clock=lambda: 0.0),
    )
    executor = ProviderPlanningJobExecutor(repository, orchestrator, clock=lambda: NOW)
    await executor.execute(reserved.job.job_id)
    return await repository.get(reserved.job.job_id), amap, repository


def test_executor_publishes_real_orchestration_shape_using_only_offline_ports() -> None:
    job, amap, repository = asyncio.run(_execute())

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
    assert {
        "activity_duration_estimated_model",
        "travel_buffer_estimated",
    } <= {item.code for item in job.result.uncertainties}
    assert [call.operation.value for call in amap.calls[:3]] == [
        "resolve_city",
        "search_pois",
        "search_pois",
    ]
    with TestClient(create_app(planning_job_repository=repository)) as client:
        body = client.get(f"/api/trip-plans/{job.job_id}").json()
    assert body["status"] == "partial"
    assert body["plan"]["budget_summary"]["unknown_count"] == 1
    assert body["retryable"] is False


def test_unknown_unmapped_duration_publishes_needs_input_without_route_calls() -> None:
    poi_source_id = _source(Provider.AMAP, "pois").source_id
    proposal = json.loads(_candidate_json(poi_source_id))
    proposal["days"][0]["selections"][0]["duration_class"] = "unknown"
    deepseek = FakeDeepSeekAdapter(
        generation_results=(
            _result(
                Provider.DEEPSEEK,
                ModelTextOutput(json.dumps(proposal)),
                "proposal",
            ),
        )
    )

    job, amap, repository = asyncio.run(
        _execute(deepseek_override=deepseek, poi_one_category="park")
    )

    assert job.status is PlanningStatus.NEEDS_INPUT
    assert job.result is not None
    assert job.result.plan is None
    assert job.result.errors[0].code.value == "input_invalid"
    assert job.result.errors[0].diagnostic_code == "activity_duration_unknown"
    assert job.result.errors[0].retryable is False
    assert not any(call.operation.value == "calculate_routes" for call in amap.calls)
    assert any(source.provider.value == "deepseek" for source in job.result.sources)
    with TestClient(create_app(planning_job_repository=repository)) as client:
        body = client.get(f"/api/trip-plans/{job.job_id}").json()
    assert body["status"] == "needs_input"
    assert body["plan"] is None
    assert body["errors"][0]["diagnostic_code"] == "activity_duration_unknown"


def test_required_capacity_conflict_flows_through_repository_and_get_api() -> None:
    job, _, repository = asyncio.run(_execute(day_zero_end=time(11)))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        body = client.get(f"/api/trip-plans/{job.job_id}").json()

    assert body["status"] == "conflict"
    assert body["plan"] is None
    assert body["errors"] == []
    assert body["retryable"] is False
    assert [item["code"] for item in body["violations"]] == ["schedule_capacity_exceeded"]


def test_partial_route_and_optional_warning_flow_through_get_api() -> None:
    poi_source_id = _source(Provider.AMAP, "pois").source_id
    proposal = json.loads(_candidate_json(poi_source_id))
    proposal["days"][0]["selections"].append(
        {
            "location_id": str(POI_TWO_ID),
            "local_date": "2026-08-15",
            "title": "可选 synthetic 活动",
            "priority_rank": 2,
            "selection_kind": "optional",
            "duration_class": "long",
            "source_ids": [str(poi_source_id)],
        }
    )
    deepseek = FakeDeepSeekAdapter(
        generation_results=(
            _result(
                Provider.DEEPSEEK,
                ModelTextOutput(json.dumps(proposal)),
                "proposal",
            ),
        )
    )
    route_pairs = (
        (HOTEL_ID, POI_ONE_ID),
        (POI_ONE_ID, POI_TWO_ID),
        (POI_TWO_ID, HOTEL_ID),
        (HOTEL_ID, POI_TWO_ID),
        (POI_TWO_ID, HOTEL_ID),
        (POI_ONE_ID, HOTEL_ID),
    )
    route_results: list[ProviderResult[RouteLeg]] = []
    for index, (origin, destination) in enumerate(route_pairs):
        source = _source(Provider.AMAP, f"route_{index}")
        route_results.append(
            ProviderResult(
                ProviderResultStatus.PARTIAL if index == 0 else ProviderResultStatus.OK,
                Provider.AMAP,
                RouteLeg(
                    origin,
                    destination,
                    RouteMode.PUBLIC_TRANSIT,
                    3000,
                    20,
                    (source.source_id,),
                ),
                FETCHED_AT,
                None,
                ("synthetic route",),
                ProviderError(ProviderErrorCategory.TIMEOUT) if index == 0 else None,
                (source,),
            )
        )
    job, amap, repository = asyncio.run(
        _execute(
            deepseek_override=deepseek,
            route_results_override=tuple(route_results),
            day_zero_end=time(14),
        )
    )

    with TestClient(create_app(planning_job_repository=repository)) as client:
        body = client.get(f"/api/trip-plans/{job.job_id}").json()

    assert body["status"] == "partial"
    assert body["plan"] is not None
    assert body["retryable"] is True
    assert "一天内有一项低优先级可选活动因时间容量不足被移除。" in body["warnings"]
    assert any(item["code"] == "provider_timeout" for item in body["errors"])
    assert any(
        item["source_id"] == str(_source(Provider.AMAP, "route_0").source_id)
        for item in body["sources"]
    )
    assert {item["code"] for item in body["uncertainties"]} >= {
        "activity_duration_estimated_model",
        "travel_buffer_estimated",
    }
    assert [call.operation.value for call in amap.calls].count("calculate_routes") == 6


def test_route_unavailable_preserves_retryable_failure_through_get_api() -> None:
    unavailable = ProviderResult[RouteLeg](
        ProviderResultStatus.UNAVAILABLE,
        Provider.AMAP,
        None,
        None,
        None,
        ("synthetic route timeout",),
        ProviderError(ProviderErrorCategory.TIMEOUT),
        (),
    )
    route_source = _source(Provider.AMAP, "route")
    remaining = tuple(
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
        for origin, destination, minutes in (
            (POI_ONE_ID, HOTEL_ID, 22),
            (HOTEL_ID, POI_TWO_ID, 30),
            (POI_TWO_ID, HOTEL_ID, 32),
        )
    )
    job, _, repository = asyncio.run(_execute(route_results_override=(unavailable, *remaining)))

    with TestClient(create_app(planning_job_repository=repository)) as client:
        body = client.get(f"/api/trip-plans/{job.job_id}").json()

    assert body["status"] == "failed"
    assert body["plan"] is None
    assert body["retryable"] is True
    assert [(item["code"], item["provider"], item["retryable"]) for item in body["errors"]] == [
        ("provider_timeout", "amap", True)
    ]


def test_local_candidate_failure_is_not_mislabeled_as_provider_schema() -> None:
    job, _, _ = asyncio.run(_execute(model_output_invalid=True))

    assert job.status is PlanningStatus.FAILED
    assert job.result is not None
    assert [(error.code.value, error.retryable) for error in job.result.errors] == [
        ("model_output_invalid", False)
    ]
    assert job.result.errors[0].diagnostic_code == "candidate_repair_json_invalid"
    assert any(source.provider.value == "amap" for source in job.result.sources)
    assert any(source.provider.value == "qweather" for source in job.result.sources)
    assert all(source.provider.value != "deepseek" for source in job.result.sources)


def test_adapter_schema_failure_keeps_stable_provider_error_distinct() -> None:
    job, _, _ = asyncio.run(_execute(provider_schema_invalid=True))

    assert job.status is PlanningStatus.FAILED
    assert job.result is not None
    assert [(error.code.value, error.retryable) for error in job.result.errors] == [
        ("provider_schema_invalid", False)
    ]
    assert job.result.errors[0].diagnostic_code == "response_envelope_invalid"


def test_mock_transport_candidate_failure_flows_through_executor_and_api_safely() -> None:
    generation_raw = "{synthetic-generation-secret"
    poi_source_id = _source(Provider.AMAP, "pois").source_id
    repaired_document = json.loads(_candidate_json(poi_source_id))
    repaired_document["days"][0]["selections"][0]["source_ids"] = [
        str(UUID("70000000-0000-4000-8000-000000000099"))
    ]
    contents = iter((generation_raw, json.dumps(repaired_document)))
    observed_payloads: list[dict[str, object]] = []

    def completion(content: str) -> dict[str, object]:
        return {
            "id": "chatcmpl-synthetic-vertical",
            "object": "chat.completion",
            "created": 1786687200,
            "model": DEEPSEEK_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": None,
                    },
                    "finish_reason": "stop",
                    "logprobs": None,
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "system_fingerprint": "fp_synthetic_vertical",
        }

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed_payloads.append(json.loads(request.content))
        return httpx2.Response(200, json=completion(next(contents)))

    source_ids = iter(
        (
            UUID("70000000-0000-4000-8000-000000000001"),
            UUID("70000000-0000-4000-8000-000000000002"),
        )
    )
    adapter = DeepSeekAdapter(
        DeepSeekAdapterConfig(api_key="test-only-deepseek-key"),
        transport=httpx2.MockTransport(handler),
        clock=lambda: FETCHED_AT,
        source_id_factory=source_ids.__next__,
    )

    job, _, repository = asyncio.run(_execute(deepseek_override=adapter))

    assert len(observed_payloads) == 2
    repair_user_message = observed_payloads[1]["messages"][1]["content"]  # type: ignore[index]
    repair_payload = json.loads(repair_user_message)
    assert repair_payload["validation_code"] == "candidate_json_invalid"
    assert len(repair_payload["proposal_rules"]) == 13
    assert any("never output start_time" in rule for rule in repair_payload["proposal_rules"])

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.get(f"/api/trip-plans/{job.job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["plan"] is None
    assert body["retryable"] is False
    assert [
        (error["code"], error["diagnostic_code"], error["retryable"]) for error in body["errors"]
    ] == [("model_output_invalid", "candidate_repair_source_reference_invalid", False)]
    assert all(source["provider"] != "deepseek" for source in body["sources"])
    assert generation_raw not in response.text
    assert "synthetic-generation-secret" not in repr(job)


def test_mock_transport_rejects_exact_times_through_api() -> None:
    poi_source_id = _source(Provider.AMAP, "pois").source_id
    generation_document = json.loads(_candidate_json(poi_source_id))
    generation_document["days"][0]["selections"][0]["start_time"] = "08:00:00"
    repair_document = json.loads(_candidate_json(poi_source_id))
    repair_document["days"][1]["selections"][0]["end_time"] = "18:00:00"
    contents = iter((json.dumps(generation_document), json.dumps(repair_document)))
    observed_payloads: list[dict[str, object]] = []

    def completion(content: str) -> dict[str, object]:
        return {
            "id": "chatcmpl-synthetic-time-vertical",
            "object": "chat.completion",
            "created": 1786687200,
            "model": DEEPSEEK_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": None,
                    },
                    "finish_reason": "stop",
                    "logprobs": None,
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "system_fingerprint": "fp_synthetic_time_vertical",
        }

    def handler(request: httpx2.Request) -> httpx2.Response:
        observed_payloads.append(json.loads(request.content))
        return httpx2.Response(200, json=completion(next(contents)))

    source_ids = iter(
        (
            UUID("70000000-0000-4000-8000-000000000011"),
            UUID("70000000-0000-4000-8000-000000000012"),
        )
    )
    adapter = DeepSeekAdapter(
        DeepSeekAdapterConfig(api_key="test-only-deepseek-key"),
        transport=httpx2.MockTransport(handler),
        clock=lambda: FETCHED_AT,
        source_id_factory=source_ids.__next__,
    )

    job, amap, repository = asyncio.run(_execute(deepseek_override=adapter))

    assert len(observed_payloads) == 2
    repair_payload = json.loads(observed_payloads[1]["messages"][1]["content"])  # type: ignore[index]
    assert repair_payload["validation_code"] == "candidate_schema_invalid"
    assert "validation_time_failure" not in repair_payload
    assert "validation_hint" not in repair_payload
    assert not any(call.operation.value == "calculate_routes" for call in amap.calls)

    with TestClient(create_app(planning_job_repository=repository)) as client:
        response = client.get(f"/api/trip-plans/{job.job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["plan"] is None
    assert body["retryable"] is False
    assert [
        (error["code"], error["diagnostic_code"], error["retryable"]) for error in body["errors"]
    ] == [
        (
            "model_output_invalid",
            "candidate_repair_schema_invalid",
            False,
        )
    ]
    assert "08:00:00" not in response.text
    assert "18:00:00" not in response.text
