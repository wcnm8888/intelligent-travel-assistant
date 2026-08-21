"""Real offline application-entry execution for the fixed F-005 eval suite."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx2

from evals.f005.models import EvalCase, EvalScenario, EvalSlice, EvalTerminal
from intelligent_travel_assistant.adapters.fakes import FakeAmapAdapter, FakeQWeatherAdapter
from intelligent_travel_assistant.adapters.providers import (
    DEEPSEEK_MODEL,
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
)
from intelligent_travel_assistant.adapters.repositories import (
    InMemoryPlanningJobRepository,
    InMemoryReplanRepository,
)
from intelligent_travel_assistant.application.planning import DeepSeekProposalResolver
from intelligent_travel_assistant.application.ports import (
    CityResolution,
    DailyWeather,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningToolName,
    PoiCandidate,
    PoiSearchResult,
    WeatherAlertsResult,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.replanning import (
    ReplanApplicationRequest,
    ReplanApplicationService,
    ReplanExecutionResult,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobRepository,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
    request_fingerprint,
)
from intelligent_travel_assistant.application.services import (
    MultiCityPlanningOrchestrator,
    OfflinePlanningOrchestrator,
    OfflinePlanningRequest,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.tooling import (
    DEFAULT_TOOL_CALL_POLICIES,
    ProviderAttemptRuntime,
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
    ToolCallPolicy,
    multicity_task_timeout_seconds,
    multicity_tool_call_policies,
    multiday_task_timeout_seconds,
    multiday_tool_call_policies,
)
from intelligent_travel_assistant.contracts import (
    PlanningRequest,
    PlanningStatus,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanRequestV3,
    TripPlanResponse,
)
from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    Money,
    PlanChangeSet,
    Provider,
    ProviderResult,
    ProviderResultStatus,
    ReplanStatus,
    RouteLeg,
    RouteMode,
    SourceRecord,
)

_FIXED_NOW = datetime(2026, 8, 21, 8, tzinfo=UTC)
_SHANGHAI = timezone(timedelta(hours=8))
_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
_ACTIVITY_ID = UUID("91000000-0000-4000-8000-000000000001")


class ApplicationEntrypoint(StrEnum):
    PROVIDER_PLANNING_JOB = "provider_planning_job_executor"
    REPLAN_APPLICATION_SERVICE = "replan_application_service"


class _ObservedSource(Protocol):
    @property
    def source_type(self) -> str: ...

    @property
    def freshness(self) -> object: ...


@dataclass(frozen=True, slots=True)
class ApplicationObservation:
    entrypoint: ApplicationEntrypoint
    terminal: EvalTerminal
    published_source_ids: tuple[UUID, ...]
    unknown_amounts: tuple[Decimal | None, ...]
    source_freshness: tuple[str, ...]
    validity_probe_freshness: tuple[str, ...]
    model_rejected: bool
    injection_isolated: bool
    logical_calls: int
    http_attempts: int
    extra_calls_rejected: bool
    call_budgets_respected: bool


@dataclass(slots=True)
class _AgentEvidence:
    requests: list[httpx2.Request]
    governors: list[ToolCallGovernor]
    runtimes: list[ProviderAttemptRuntime]

    def observation_fields(self, case: EvalCase) -> tuple[bool, int, int, bool, bool]:
        governor = self.governors[-1]
        logical_calls = sum(len(value.snapshot().records) for value in self.governors)
        attempts = sum(len(runtime.snapshot().records) for runtime in self.runtimes)
        extra_rejected = case.requested_extra_calls == 0
        if case.requested_extra_calls:
            rejected = 0
            for _ in range(case.requested_extra_calls):
                try:
                    permit = governor.reserve(
                        ToolCallCapability.GENERATE_PLAN_CANDIDATE,
                        PlanningStatus.PLANNING,
                    )
                except ToolCallGovernanceError as error:
                    rejected += error.code is ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED
                else:
                    governor.complete(permit)
            extra_rejected = rejected == case.requested_extra_calls
        isolated = case.scenario is not EvalScenario.INJECTION or all(
            _request_keeps_injection_in_allowlisted_data(request, case.model_text)
            for request in self.requests
        )
        return (
            isolated,
            logical_calls,
            attempts,
            extra_rejected,
            _call_budgets_respected(case, self.governors, self.runtimes),
        )


async def execute_application_case(case: EvalCase) -> ApplicationObservation:
    """Execute one case through its version-specific real application boundary."""

    if case.slice is EvalSlice.F003:
        return await _execute_replan_case(case)
    return await _execute_planning_case(case)


async def _execute_planning_case(case: EvalCase) -> ApplicationObservation:
    request = _planning_request(case)
    evidence = _AgentEvidence([], [], [])
    deepseek = _deepseek(case, request=request, requests=evidence.requests)
    legacy, amap, qweather = _single_city_orchestrator(case, request, deepseek, evidence)
    multicity = (
        _multicity_orchestrator(case, cast(TripPlanRequestV3, request), deepseek, evidence)
        if case.slice is EvalSlice.V3
        else None
    )
    repository = InMemoryPlanningJobRepository(
        clock=lambda: _FIXED_NOW,
        id_factory=iter(
            (_stable_uuid(f"{case.case_id}:job"), _stable_uuid(f"{case.case_id}:trace"))
        ).__next__,
    )
    reservation = await repository.get_or_create(request)
    executor = ProviderPlanningJobExecutor(
        repository,
        legacy,
        clock=lambda: _FIXED_NOW,
        multicity_orchestrator=multicity,
        attempt_runtime_factory=_runtime_factory(evidence),
    )
    await executor.execute(reservation.job.job_id)
    job = await repository.get(reservation.job.job_id)
    isolated, logical_calls, attempts, extra_rejected, budgets_respected = (
        evidence.observation_fields(case)
    )
    result = job.result
    if result is None:
        raise ValueError("eval_application_result_missing")
    return ApplicationObservation(
        ApplicationEntrypoint.PROVIDER_PLANNING_JOB,
        _planning_terminal(job.status),
        tuple(source.source_id for source in result.sources),
        _unknown_amounts(result.plan),
        tuple(_freshness_value(source.freshness) for source in result.sources),
        _validity_probe_freshness(result.sources),
        job.status is PlanningStatus.FAILED,
        isolated,
        logical_calls,
        attempts,
        extra_rejected,
        budgets_respected,
    )


def _single_city_orchestrator(
    case: EvalCase,
    request: PlanningRequest,
    deepseek: DeepSeekAdapter,
    evidence: _AgentEvidence,
) -> tuple[OfflinePlanningOrchestrator, FakeAmapAdapter, FakeQWeatherAdapter]:
    start = request.start_date
    day_count = 2 if not isinstance(request, TripPlanRequestV2) else request.day_count
    hotel_id = _stable_uuid(f"{case.case_id}:hotel")
    coordinates = Coordinates(Decimal("120.15"), Decimal("30.27"), CoordinateSystem.PROVIDER_NATIVE)
    hotel = PoiCandidate(hotel_id, "synthetic hotel", "lodging", "330100", None, coordinates)
    pois = tuple(
        PoiCandidate(
            _stable_uuid(f"{case.case_id}:poi:{offset}"),
            f"synthetic poi {offset}",
            "scenic_area",
            "330100",
            None,
            coordinates,
        )
        for offset in range(day_count)
    )
    selected_source = _case_catalog_uuid(case, case.allowed_source_ids[0])
    city = _result(
        Provider.AMAP,
        CityResolution("杭州市", "330100", "0571", coordinates),
        f"{case.case_id}:city",
    )
    accommodation = _result(
        Provider.AMAP,
        PoiSearchResult((hotel,)),
        f"{case.case_id}:hotel",
    )
    poi_result = _result(
        Provider.AMAP,
        PoiSearchResult(pois),
        f"{case.case_id}:pois",
        source_id=selected_source,
    )
    route_results = tuple(
        _route_result(case, index, origin, destination)
        for index, (origin, destination) in enumerate(
            pair
            for poi in pois
            for pair in ((hotel.location_id, poi.location_id), (poi.location_id, hotel.location_id))
        )
    )
    amap = FakeAmapAdapter(
        resolve_city_results=(city,),
        search_pois_results=(accommodation, poi_result),
        calculate_routes_results=route_results,
    )
    weather_valid_until = _weather_valid_until(case)
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=(
            _result(
                Provider.QWEATHER,
                WeatherForecastResult(
                    hotel_id,
                    tuple(
                        DailyWeather(
                            start + timedelta(days=offset),
                            "晴",
                            "晴",
                            Decimal("20"),
                            Decimal("30"),
                        )
                        for offset in range(day_count)
                    ),
                ),
                f"{case.case_id}:weather",
                fetched_at=(
                    _FIXED_NOW - timedelta(hours=2)
                    if case.scenario is EvalScenario.STALE
                    else _FIXED_NOW
                ),
                valid_until=weather_valid_until,
            ),
        ),
        weather_alert_results=(
            _result(
                Provider.QWEATHER,
                WeatherAlertsResult(hotel_id, ()),
                f"{case.case_id}:alerts",
                fetched_at=(
                    _FIXED_NOW - timedelta(hours=2)
                    if case.scenario is EvalScenario.STALE
                    else _FIXED_NOW
                ),
                valid_until=weather_valid_until,
            ),
        ),
    )

    def governor_factory() -> ToolCallGovernor:
        value = ToolCallGovernor(clock=lambda: 0.0)
        evidence.governors.append(value)
        return value

    def request_governor_factory(value: OfflinePlanningRequest) -> ToolCallGovernor:
        count = value.day_count
        governor = ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multiday_tool_call_policies(count),
            task_timeout_seconds=multiday_task_timeout_seconds(count),
        )
        evidence.governors.append(governor)
        return governor

    return (
        OfflinePlanningOrchestrator(
            amap,
            qweather,
            deepseek,
            governor_factory,
            request_governor_factory=(
                request_governor_factory if isinstance(request, TripPlanRequestV2) else None
            ),
        ),
        amap,
        qweather,
    )


def _multicity_orchestrator(
    case: EvalCase,
    request: TripPlanRequestV3,
    deepseek: DeepSeekAdapter,
    evidence: _AgentEvidence,
) -> MultiCityPlanningOrchestrator:
    coordinates = (
        Coordinates(Decimal("120.15"), Decimal("30.27"), CoordinateSystem.PROVIDER_NATIVE),
        Coordinates(Decimal("121.47"), Decimal("31.23"), CoordinateSystem.PROVIDER_NATIVE),
    )
    adcodes = ("330100", "310000")
    hotels = tuple(
        PoiCandidate(
            _stable_uuid(f"{case.case_id}:v3:hotel:{index}"),
            f"hotel {index}",
            "lodging",
            adcodes[index],
            None,
            coordinates[index],
        )
        for index in range(2)
    )
    pois = tuple(
        PoiCandidate(
            _stable_uuid(f"{case.case_id}:v3:poi:{index}"),
            f"poi {index}",
            "scenic_area",
            adcodes[index],
            None,
            coordinates[index],
        )
        for index in range(2)
    )
    stations = tuple(
        PoiCandidate(
            _stable_uuid(f"{case.case_id}:v3:station:{index}"),
            request.intercity_segments[0].departure_station
            if index == 0
            else request.intercity_segments[0].arrival_station,
            "rail_station",
            adcodes[index],
            None,
            coordinates[index],
        )
        for index in range(2)
    )
    allowed_source = _case_catalog_uuid(case, case.allowed_source_ids[0])
    searches = tuple(
        value
        for index in range(2)
        for value in (
            _result(
                Provider.AMAP, PoiSearchResult((hotels[index],)), f"{case.case_id}:v3:hotel:{index}"
            ),
            _result(
                Provider.AMAP,
                PoiSearchResult((pois[index],)),
                f"{case.case_id}:v3:poi:{index}",
                source_id=allowed_source,
            ),
            _result(
                Provider.AMAP,
                PoiSearchResult((stations[index],)),
                f"{case.case_id}:v3:station:{index}",
            ),
        )
    )
    routes = tuple(
        _route_result(case, index, origin, destination)
        for index, (origin, destination) in enumerate(
            (
                (hotels[0].location_id, pois[0].location_id),
                (pois[0].location_id, hotels[0].location_id),
                (hotels[1].location_id, pois[1].location_id),
                (pois[1].location_id, hotels[1].location_id),
            )
        )
    )
    amap = FakeAmapAdapter(
        resolve_city_results=tuple(
            _result(
                Provider.AMAP,
                CityResolution(name, adcode, area, coordinate),
                f"{case.case_id}:v3:city:{index}",
            )
            for index, (name, adcode, area, coordinate) in enumerate(
                zip(("杭州市", "上海市"), adcodes, ("0571", "021"), coordinates, strict=True)
            )
        ),
        search_pois_results=searches,
        calculate_routes_results=routes,
    )
    weather_valid_until = _weather_valid_until(case)
    qweather = FakeQWeatherAdapter(
        weather_forecast_results=tuple(
            _result(
                Provider.QWEATHER,
                WeatherForecastResult(
                    hotels[index].location_id,
                    tuple(
                        DailyWeather(
                            request.start_date + timedelta(days=offset),
                            "晴",
                            "晴",
                            Decimal("20"),
                            Decimal("30"),
                        )
                        for offset in range(request.day_count)
                    ),
                ),
                f"{case.case_id}:v3:weather:{index}",
                fetched_at=(
                    _FIXED_NOW - timedelta(hours=2)
                    if case.scenario is EvalScenario.STALE
                    else _FIXED_NOW
                ),
                valid_until=weather_valid_until,
            )
            for index in range(2)
        ),
        weather_alert_results=tuple(
            _result(
                Provider.QWEATHER,
                WeatherAlertsResult(hotels[index].location_id, ()),
                f"{case.case_id}:v3:alerts:{index}",
                fetched_at=(
                    _FIXED_NOW - timedelta(hours=2)
                    if case.scenario is EvalScenario.STALE
                    else _FIXED_NOW
                ),
                valid_until=weather_valid_until,
            )
            for index in range(2)
        ),
    )

    def governor_factory(city_count: int, day_count: int) -> ToolCallGovernor:
        governor = ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multicity_tool_call_policies(city_count=city_count, day_count=day_count),
            task_timeout_seconds=multicity_task_timeout_seconds(
                city_count=city_count,
                day_count=day_count,
            ),
        )
        evidence.governors.append(governor)
        return governor

    return MultiCityPlanningOrchestrator(amap, qweather, deepseek, governor_factory)


async def _execute_replan_case(case: EvalCase) -> ApplicationObservation:
    baseline = _f003_baseline(case)
    evidence = _AgentEvidence([], [], [])
    executor = _EvalReplanExecutor(case, baseline, evidence)
    identifiers = iter(
        (
            _stable_uuid(f"{case.case_id}:replan"),
            _stable_uuid(f"{case.case_id}:replan-trace"),
            _stable_uuid(f"{case.case_id}:decision"),
        )
    )
    service = ReplanApplicationService(
        cast(PlanningJobRepository, _SinglePlanningJobRepository(baseline)),
        InMemoryReplanRepository(id_factory=identifiers.__next__),
        executor,
    )
    assert baseline.result is not None and baseline.result.plan is not None
    result = await service.create(
        ReplanApplicationRequest(
            baseline.job_id,
            _stable_uuid(f"{case.case_id}:request"),
            baseline.result.plan.plan_id,
            DeleteActivity(_ACTIVITY_ID, reason_code="user_requested"),
        )
    )
    isolated, logical_calls, attempts, extra_rejected, budgets_respected = (
        evidence.observation_fields(case)
    )
    published = (
        executor.committed_result.sources
        if executor.committed_result is not None
        else baseline.result.sources
    )
    plan = (
        executor.committed_result.plan
        if executor.committed_result is not None
        else baseline.result.plan
    )
    terminal = (
        _planning_terminal(executor.committed_result.status)
        if executor.committed_result is not None
        else _replan_terminal(result.replan.status)
    )
    return ApplicationObservation(
        ApplicationEntrypoint.REPLAN_APPLICATION_SERVICE,
        terminal,
        tuple(source.source_id for source in published),
        _unknown_amounts(plan),
        tuple(_freshness_value(source.freshness) for source in published),
        _validity_probe_freshness(published),
        executor.model_rejected,
        isolated,
        logical_calls,
        attempts,
        extra_rejected,
        budgets_respected,
    )


@dataclass(slots=True)
class _SinglePlanningJobRepository:
    job: PlanningJob

    async def get(self, job_id: UUID) -> PlanningJob:
        if job_id != self.job.job_id:
            raise ValueError("eval_job_not_found")
        return self.job


class _EvalReplanExecutor:
    def __init__(self, case: EvalCase, baseline: PlanningJob, evidence: _AgentEvidence) -> None:
        self._case = case
        self._baseline = baseline
        self._evidence = evidence
        self.model_rejected = False
        self.committed_result: PlanningJobResult | None = None

    async def analyze(self, _job: PlanningJob, _command: object) -> ImpactAnalysis:
        return ImpactAnalysis(
            (ImpactCategory.SAME_DAY_LOW,),
            ImpactDisposition.AUTO,
            (_ACTIVITY_ID,),
            (),
            (),
            (),
            (),
            ("schedule",),
            False,
        )

    async def execute(self, _job: PlanningJob, _replan: ReplanRecord) -> ReplanExecutionResult:
        context = _standalone_context(self._case)
        deepseek = _deepseek(
            self._case,
            request=None,
            requests=self._evidence.requests,
            standalone_context=context,
        )
        runtime = _new_runtime(90.0)
        governor = ToolCallGovernor(clock=lambda: 0.0)
        self._evidence.runtimes.append(runtime)
        self._evidence.governors.append(governor)
        resolution = await DeepSeekProposalResolver(deepseek).resolve(context, governor, runtime)
        await runtime.close()
        self.model_rejected = resolution.result.data is None
        if self._case.scenario is EvalScenario.CONFLICT:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.CONFLICT, "synthetic_eval_conflict")
            )
        if self.model_rejected or self._case.scenario in {
            EvalScenario.PROVIDER_TIMEOUT,
            EvalScenario.PROVIDER_AUTH,
            EvalScenario.PROVIDER_SCHEMA,
        }:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "synthetic_eval_failed")
            )
        baseline_result = cast(PlanningJobResult, self._baseline.result)
        baseline_plan = baseline_result.plan
        if baseline_plan is None:
            raise ValueError("eval_replan_baseline_missing")
        result_plan = baseline_plan.model_copy(
            update={"plan_id": _stable_uuid(f"{self._case.case_id}:result-plan")}
        )
        committed_result = PlanningJobResult(
            baseline_result.status,
            baseline_result.resolved_destination,
            result_plan,
            baseline_result.violations,
            baseline_result.warnings,
            baseline_result.uncertainties,
            baseline_result.sources,
            baseline_result.errors,
            baseline_result.retryable,
        )
        self.committed_result = committed_result
        return ReplanExecutionResult(
            commit=ReplanCommit(
                committed_result,
                PlanChangeSet(
                    baseline_plan.plan_id,
                    result_plan.plan_id,
                    (),
                    (),
                    (),
                    (),
                    (),
                ),
            )
        )


def _f003_baseline(case: EvalCase) -> PlanningJob:
    request_document = json.loads(
        (_FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    request = TripPlanRequest.model_validate(request_document["request"])
    response_document = json.loads(
        (_FIXTURE_ROOT / "synthetic_hangzhou_partial.json").read_text(encoding="utf-8")
    )
    if case.scenario is EvalScenario.UNKNOWN_COST:
        budget_summary = response_document["response"]["plan"]["budget_summary"]
        known_item = budget_summary["cost_items"][0]
        known_item.update({"confidence": "unknown", "amount": None, "source_ids": []})
        budget_summary["known_total"] = {"amount": "1400.00", "currency": "CNY"}
        budget_summary["unknown_count"] = 2
    if case.scenario is EvalScenario.UNKNOWN_VALIDITY:
        weather_source = response_document["response"]["sources"][4]
        weather_source.update({"valid_until": None, "freshness": "unknown_validity"})
    response = TripPlanResponse.model_validate(response_document["response"])
    sources = response.sources
    if case.scenario is EvalScenario.STALE:
        stale_source = sources[3].model_copy(
            update={
                "valid_until": sources[3].fetched_at,
                "freshness": "stale",
            }
        )
        sources = (*sources[:3], stale_source, *sources[4:])
    result = PlanningJobResult(
        response.status,
        response.resolved_destination,
        response.plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        sources,
        response.errors,
        response.retryable,
    )
    return PlanningJob(
        _stable_uuid(f"{case.case_id}:baseline-job"),
        _stable_uuid(f"{case.case_id}:baseline-trace"),
        request.client_request_id,
        request_fingerprint(request),
        request,
        PlanningStatus.PARTIAL,
        1,
        5,
        result.retryable,
        response.created_at,
        response.updated_at,
        result,
    )


def _planning_request(case: EvalCase) -> PlanningRequest:
    if case.slice is EvalSlice.V3:
        payload: dict[str, object] = {
            "request_version": "3",
            "client_request_id": str(_stable_uuid(f"{case.case_id}:client")),
            "start_date": "2026-08-21",
            "end_date": "2026-08-23",
            "travelers": 2,
            "total_budget": {"amount": "5000.00", "currency": "CNY"},
            "preferences": {
                "interests": ["自然"],
                "free_text": case.model_text,
                "hard_constraints": [],
            },
            "pace": "balanced",
            "transport_modes": ["walking", "public_transit"],
            "city_stays": [
                {
                    "city": "杭州",
                    "nights": 1,
                    "accommodation": {
                        "area_or_poi": "杭州住宿",
                        "one_night_cost": {"amount": "500.00", "currency": "CNY"},
                    },
                },
                {
                    "city": "上海",
                    "nights": 1,
                    "accommodation": {
                        "area_or_poi": "上海住宿",
                        "one_night_cost": {"amount": "500.00", "currency": "CNY"},
                    },
                },
            ],
            "intercity_segments": [
                {
                    "from_city_index": 0,
                    "to_city_index": 1,
                    "mode": "rail",
                    "departure_station": "杭州站",
                    "arrival_station": "上海站",
                    "departure_at": datetime(2026, 8, 22, 10, tzinfo=_SHANGHAI).isoformat(),
                    "arrival_at": datetime(2026, 8, 22, 12, tzinfo=_SHANGHAI).isoformat(),
                    "fare": (
                        None
                        if case.scenario is EvalScenario.UNKNOWN_COST
                        else {"amount": "120.00", "currency": "CNY"}
                    ),
                }
            ],
            "day_windows": _day_windows(3, conflict=case.scenario is EvalScenario.CONFLICT),
            "meal_budget_per_person_per_day": {"amount": "100.00", "currency": "CNY"},
        }
        return TripPlanRequestV3.model_validate(payload)
    document = json.loads(
        (_FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    payload = cast(dict[str, object], document["request"])
    payload["client_request_id"] = str(_stable_uuid(f"{case.case_id}:client"))
    payload["city"] = "杭州"
    preferences = cast(dict[str, object], payload["preferences"])
    preferences["free_text"] = case.model_text
    payload["start_date"] = "2026-08-22"
    payload["day_windows"] = _day_windows(2, conflict=case.scenario is EvalScenario.CONFLICT)
    if case.scenario is EvalScenario.UNKNOWN_COST:
        payload["intercity_transport_cost"] = None
    if case.slice is EvalSlice.V2:
        payload["request_version"] = "2"
        payload["end_date"] = "2026-08-23"
        return TripPlanRequestV2.model_validate(payload)
    return TripPlanRequest.model_validate(payload)


def _day_windows(day_count: int, *, conflict: bool) -> list[dict[str, object]]:
    return [
        {
            "day_offset": offset,
            "start_time": "08:00:00",
            "end_time": "09:00:00" if conflict else "18:00:00",
        }
        for offset in range(day_count)
    ]


def _deepseek(
    case: EvalCase,
    *,
    request: PlanningRequest | None,
    requests: list[httpx2.Request],
    standalone_context: PlanningContext | None = None,
) -> DeepSeekAdapter:
    if request is None and standalone_context is None:
        raise ValueError("eval_context_missing")
    output = _proposal_document(case, request=request, context=standalone_context)

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        requests.append(http_request)
        if case.scenario is EvalScenario.PROVIDER_TIMEOUT:
            raise httpx2.ReadTimeout("synthetic timeout", request=http_request)
        if case.scenario is EvalScenario.PROVIDER_AUTH:
            return httpx2.Response(401, json={"error": "synthetic"})
        if case.scenario is EvalScenario.PROVIDER_SCHEMA:
            return httpx2.Response(200, json={"object": "synthetic-invalid"})
        return httpx2.Response(200, json=_completion(output))

    return DeepSeekAdapter(
        DeepSeekAdapterConfig(api_key="synthetic"),
        transport=httpx2.MockTransport(handler),
        clock=lambda: _FIXED_NOW,
        source_id_factory=lambda: _stable_uuid(f"{case.case_id}:deepseek"),
    )


def _proposal_document(
    case: EvalCase,
    *,
    request: PlanningRequest | None,
    context: PlanningContext | None,
) -> str:
    if request is not None:
        start = request.start_date
        day_count = (
            request.day_count if isinstance(request, (TripPlanRequestV2, TripPlanRequestV3)) else 2
        )
        is_v3 = isinstance(request, TripPlanRequestV3)
    elif context is not None:
        start = context.start_date
        day_count = len(context.day_windows)
        is_v3 = context.request_version == "3"
    else:
        raise ValueError("eval_context_missing")
    source_values = case.selected_source_ids or case.allowed_source_ids[:1]
    source_ids = [str(_case_catalog_uuid(case, value)) for value in source_values]
    days: list[dict[str, object]] = []
    for offset in range(day_count):
        local_date = start + timedelta(days=offset)
        selections: list[dict[str, object]] = []
        if not is_v3 or offset != 1:
            selections.append(
                {
                    "location_id": str(
                        _stable_uuid(
                            f"{case.case_id}:v3:poi:{0 if offset == 0 else 1}"
                            if is_v3
                            else (
                                f"{case.case_id}:poi:0"
                                if request is None
                                else f"{case.case_id}:poi:{offset}"
                            )
                        )
                    ),
                    "local_date": local_date.isoformat(),
                    "title": "synthetic activity",
                    "priority_rank": 1,
                    "selection_kind": "required",
                    "duration_class": "short" if is_v3 else "standard",
                    "source_ids": source_ids,
                }
            )
        item: dict[str, object] = {
            "local_date": local_date.isoformat(),
            "selections": selections,
        }
        if is_v3:
            indices = ((0, 0, 0), (0, 1, 1), (1, 1, 1))[offset]
            item.update(
                departure_city_index=indices[0],
                arrival_city_index=indices[1],
                overnight_city_index=indices[2],
            )
        days.append(item)
    root: dict[str, object] = {
        "intent_summary": "synthetic offline eval",
        "days": days,
        "explanation": "synthetic offline eval",
        "warnings": [],
    }
    for field in case.model_fields:
        if field not in root:
            root[field] = "synthetic-forbidden"
    return json.dumps(root, separators=(",", ":"))


def _standalone_context(case: EvalCase) -> PlanningContext:
    location_id = _stable_uuid(f"{case.case_id}:poi:0")
    source_ids = tuple(_case_catalog_uuid(case, value) for value in case.allowed_source_ids)
    return PlanningContext(
        city_name=case.model_text,
        city_adcode="330100",
        start_date=date(2026, 8, 15),
        end_date=date(2026, 8, 16),
        travelers=1,
        budget=Money(Decimal("1000.00")),
        interests=(),
        hard_constraints=(),
        allowed_tools=tuple(PlanningToolName),
        locations=(PlanningLocation(location_id, "synthetic", "poi", "330100"),),
        observations=(),
        day_windows=(
            PlanningDayWindow(0, time(8), time(18)),
            PlanningDayWindow(1, time(8), time(18)),
        ),
        activity_source_ids=source_ids,
    )


def _runtime_factory(evidence: _AgentEvidence) -> Callable[[float], ProviderAttemptRuntime]:
    def factory(task_timeout_seconds: float) -> ProviderAttemptRuntime:
        runtime = _new_runtime(task_timeout_seconds)
        evidence.runtimes.append(runtime)
        return runtime

    return factory


def _new_runtime(task_timeout_seconds: float) -> ProviderAttemptRuntime:
    async def no_delay(_seconds: float) -> None:
        return None

    return ProviderAttemptRuntime(
        clock=lambda: 0.0,
        sleeper=no_delay,
        jitter=lambda: 0.0,
        task_timeout_seconds=task_timeout_seconds,
    )


def _call_budgets_respected(
    case: EvalCase,
    governors: list[ToolCallGovernor],
    runtimes: list[ProviderAttemptRuntime],
) -> bool:
    policies: dict[ToolCallCapability, ToolCallPolicy]
    if case.slice is EvalSlice.V2:
        policies = dict(multiday_tool_call_policies(2))
    elif case.slice is EvalSlice.V3:
        policies = dict(multicity_tool_call_policies(city_count=2, day_count=3))
    else:
        policies = dict(DEFAULT_TOOL_CALL_POLICIES)
    logical_ok = all(
        all(
            snapshot.count_for(capability) <= policy.max_calls
            for capability, policy in policies.items()
        )
        for snapshot in (governor.snapshot() for governor in governors)
    )
    attempt_ok = True
    for runtime in runtimes:
        snapshot = runtime.snapshot()
        attempt_ok = attempt_ok and (
            snapshot.amap_extra_attempts <= 3
            and snapshot.qweather_extra_attempts <= 1
            and snapshot.task_extra_attempts <= 4
            and all(
                record.attempt_number <= (1 if record.provider is Provider.DEEPSEEK else 2)
                for record in snapshot.records
            )
        )
    return logical_ok and attempt_ok


def _result[T](
    provider: Provider,
    data: T,
    key: str,
    *,
    source_id: UUID | None = None,
    fetched_at: datetime = _FIXED_NOW,
    valid_until: datetime | None = None,
) -> ProviderResult[T]:
    source = SourceRecord(
        source_id or _stable_uuid(f"source:{key}"),
        provider,
        f"synthetic_eval_{key}",
        fetched_at,
        valid_until,
    )
    return ProviderResult(
        ProviderResultStatus.OK,
        provider,
        data,
        fetched_at,
        valid_until,
        ("synthetic provider result",),
        None,
        (source,),
    )


def _route_result(
    case: EvalCase,
    index: int,
    origin: UUID,
    destination: UUID,
) -> ProviderResult[RouteLeg]:
    source_id = _stable_uuid(f"source:{case.case_id}:route:{index}")
    return _result(
        Provider.AMAP,
        RouteLeg(origin, destination, RouteMode.PUBLIC_TRANSIT, 1000, 15, (source_id,)),
        f"{case.case_id}:route:{index}",
        source_id=source_id,
    )


def _weather_valid_until(case: EvalCase) -> datetime | None:
    if case.scenario is EvalScenario.STALE:
        return _FIXED_NOW - timedelta(hours=1)
    if case.scenario is EvalScenario.BOUNDARY:
        return _FIXED_NOW
    if case.scenario is EvalScenario.NORMAL:
        return _FIXED_NOW + timedelta(hours=1)
    return None


def _unknown_amounts(plan: object) -> tuple[Decimal | None, ...]:
    if plan is None or not hasattr(plan, "budget_summary"):
        return ()
    items = plan.budget_summary.cost_items
    return tuple(item.amount for item in items if item.confidence.value == "unknown")


def _freshness_value(value: object) -> str:
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raise ValueError("eval_source_freshness_invalid")
    return raw


def _validity_probe_freshness(sources: tuple[_ObservedSource, ...]) -> tuple[str, ...]:
    return tuple(
        _freshness_value(source.freshness)
        for source in sources
        if any(token in source.source_type for token in ("weather", "forecast", "alert"))
    )


def _planning_terminal(status: PlanningStatus) -> EvalTerminal:
    if status is PlanningStatus.READY:
        return EvalTerminal.READY
    if status is PlanningStatus.PARTIAL:
        return EvalTerminal.PARTIAL
    if status is PlanningStatus.CONFLICT:
        return EvalTerminal.CONFLICT
    return EvalTerminal.FAILED


def _replan_terminal(status: ReplanStatus) -> EvalTerminal:
    if status is ReplanStatus.CONFLICT:
        return EvalTerminal.CONFLICT
    return EvalTerminal.FAILED


def _completion(content: str) -> dict[str, object]:
    return {
        "id": "chatcmpl-synthetic-eval",
        "object": "chat.completion",
        "created": 1787299200,
        "model": DEEPSEEK_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        "system_fingerprint": "fp_synthetic_eval",
    }


def _request_keeps_injection_in_allowlisted_data(
    request: httpx2.Request,
    untrusted_text: str,
) -> bool:
    try:
        payload = json.loads(request.content)
        messages = payload["messages"]
        system_text = messages[0]["content"]
        user_value = json.loads(messages[1]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(system_text, str) or untrusted_text in system_text:
        return False
    occurrences = _text_occurrences(user_value, untrusted_text)
    return not occurrences or occurrences == (("free_text", untrusted_text),)


def _text_occurrences(value: object, target: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []

    def visit(item: object, field: str = "") -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                visit(child, key if isinstance(key, str) else "")
        elif isinstance(item, list):
            for child in item:
                visit(child, field)
        elif isinstance(item, str) and target in item:
            found.append((field, item))

    visit(value)
    return tuple(found)


def _stable_uuid(value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"f005-eval:{value}")


def _catalog_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        return _stable_uuid(value)


def _case_catalog_uuid(case: EvalCase, value: str) -> UUID:
    if case.slice is EvalSlice.F003 and value == "s1":
        return UUID("40000000-0000-4000-8000-000000000002")
    return _catalog_uuid(value)
