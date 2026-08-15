"""Minimal offline planning flow before final deterministic validation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from intelligent_travel_assistant.application.planning import (
    AccommodationAnchor,
    CandidateResolutionErrorCode,
    CandidateValidationStage,
    DeepSeekCandidateResolver,
    FinalValidationResult,
    RouteEnrichmentResult,
    evaluate_final_plan,
    route_activities,
)
from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CandidateTimeFailureCode,
    CandidateValidationCode,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    PlanCandidate,
    PlanningContext,
    PlanningDayWindow,
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
from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
    ToolCallSnapshot,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    BudgetCostItem,
    CostCategory,
    CostConfidence,
    DailyAvailability,
    DailyRoutePlan,
    DomainInvariantError,
    Money,
    ProviderErrorCategory,
    ProviderResult,
    ProviderResultStatus,
    RouteLeg,
    RouteMode,
    TripRequestInput,
)


@dataclass(frozen=True, slots=True)
class OfflinePlanningRequest:
    trip: TripRequestInput
    budget: Money
    hard_constraints: tuple[str, ...]
    weather_location_id: UUID | None
    poi_keywords: tuple[str, ...]
    poi_categories: tuple[str, ...]
    poi_limit: int
    route_mode: RouteMode
    accommodation: AccommodationAnchor | None
    day_windows: tuple[DailyAvailability, ...]
    cost_items: tuple[BudgetCostItem, ...]
    evaluated_at: datetime
    accommodation_query: str | None = None
    derive_local_transport_cost: bool = False

    def __post_init__(self) -> None:
        if self.accommodation is None and (
            not isinstance(self.accommodation_query, str) or not self.accommodation_query.strip()
        ):
            raise DomainInvariantError(
                "accommodation_query_required",
                field="accommodation_query",
            )


@dataclass(frozen=True, slots=True)
class OfflinePlanningOutcome:
    status: PlanningStatus
    state_history: tuple[PlanningStatus, ...]
    tool_calls: ToolCallSnapshot
    candidate_resolution_error: CandidateResolutionErrorCode | None = None
    candidate_repaired: bool = False
    candidate_validation_stage: CandidateValidationStage | None = None
    candidate_validation_code: CandidateValidationCode | None = None
    candidate_time_failure: CandidateTimeFailureCode | None = None
    city_result: ProviderResult[CityResolution] | None = None
    accommodation_result: ProviderResult[PoiSearchResult] | None = None
    accommodation: AccommodationAnchor | None = None
    poi_result: ProviderResult[PoiSearchResult] | None = None
    weather_result: ProviderResult[WeatherForecastResult] | None = None
    alert_result: ProviderResult[WeatherAlertsResult] | None = None
    candidate_result: ProviderResult[PlanCandidate] | None = None
    route_enrichments: tuple[RouteEnrichmentResult, ...] = ()
    final_validation: FinalValidationResult | None = None

    @property
    def route_result(self) -> ProviderResult[RouteLeg] | None:
        """Compatibility view; callers should use the complete enrichment tuple."""

        return next(
            (item.result for item in self.route_enrichments if item.result is not None),
            None,
        )


class OfflinePlanningOrchestrator:
    """Compose, enrich, and deterministically arbitrate one offline candidate."""

    __slots__ = ("_amap", "_deepseek", "_governor_factory", "_qweather")

    def __init__(
        self,
        amap: AmapPort,
        qweather: QWeatherPort,
        deepseek: DeepSeekPort,
        governor_factory: Callable[[], ToolCallGovernor],
    ) -> None:
        self._amap = amap
        self._qweather = qweather
        self._deepseek = deepseek
        self._governor_factory = governor_factory

    async def plan(
        self,
        request: OfflinePlanningRequest,
        *,
        state_observer: Callable[[PlanningStatus], Awaitable[None]] | None = None,
    ) -> OfflinePlanningOutcome:
        governor = self._governor_factory()
        history = [PlanningStatus.DRAFT]
        await _advance(history, PlanningStatus.NORMALIZING, state_observer)
        await _advance(history, PlanningStatus.COLLECTING, state_observer)

        city_result = await _governed_call(
            governor,
            ToolCallCapability.RESOLVE_CITY,
            history[-1],
            lambda: self._amap.resolve_city(CityResolutionRequest(request.trip.city)),
        )
        if city_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(history, governor, city_result=city_result)
        city = _require_data(city_result)

        accommodation = request.accommodation
        accommodation_result: ProviderResult[PoiSearchResult] | None = None
        if accommodation is None:
            accommodation_query = request.accommodation_query
            assert isinstance(accommodation_query, str)
            accommodation_result = await _governed_call(
                governor,
                ToolCallCapability.SEARCH_POIS,
                history[-1],
                lambda: self._amap.search_pois(
                    PoiSearchRequest(
                        city_adcode=city.adcode,
                        keywords=(accommodation_query.strip(),),
                        categories=(),
                        limit=3,
                    )
                ),
            )
            if accommodation_result.status is ProviderResultStatus.UNAVAILABLE:
                await _advance(history, PlanningStatus.FAILED, state_observer)
                return _outcome(
                    history,
                    governor,
                    city_result=city_result,
                    accommodation_result=accommodation_result,
                )
            accommodation_candidate = next(
                (
                    item
                    for item in _require_data(accommodation_result).candidates
                    if item.city_adcode == city.adcode and item.coordinates is not None
                ),
                None,
            )
            if accommodation_candidate is None:
                await _advance(history, PlanningStatus.FAILED, state_observer)
                return _outcome(
                    history,
                    governor,
                    city_result=city_result,
                    accommodation_result=accommodation_result,
                )
            accommodation = AccommodationAnchor(
                accommodation_candidate.location_id,
                accommodation_candidate.city_adcode,
                accommodation_candidate.coordinates,
            )

        poi_request = PoiSearchRequest(
            city_adcode=city.adcode,
            keywords=request.poi_keywords,
            categories=request.poi_categories,
            limit=request.poi_limit,
        )
        poi_result = await _governed_call(
            governor,
            ToolCallCapability.SEARCH_POIS,
            history[-1],
            lambda: self._amap.search_pois(poi_request),
        )
        if poi_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(
                history,
                governor,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
            )
        pois = _require_data(poi_result)

        weather_result: ProviderResult[WeatherForecastResult] | None = None
        alert_result: ProviderResult[WeatherAlertsResult] | None = None
        weather_coordinates = (
            accommodation.coordinates if request.weather_location_id is None else city.center
        )
        if weather_coordinates is not None:
            weather_location_id = request.weather_location_id or accommodation.location_id
            forecast_request = WeatherForecastRequest(
                location_id=weather_location_id,
                coordinates=weather_coordinates,
                start_date=request.trip.start_date,
                end_date=request.trip.end_date,
            )
            weather_result = await _governed_call(
                governor,
                ToolCallCapability.GET_WEATHER_FORECAST,
                history[-1],
                lambda: self._qweather.get_weather_forecast(forecast_request),
            )
            alerts_request = CurrentWeatherAlertsRequest(
                location_id=weather_location_id,
                coordinates=weather_coordinates,
            )
            alert_result = await _governed_call(
                governor,
                ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
                history[-1],
                lambda: self._qweather.get_current_weather_alerts(alerts_request),
            )

        await _advance(history, PlanningStatus.PLANNING, state_observer)
        planning_context = _planning_context(
            request,
            city,
            accommodation,
            pois,
            city_result,
            poi_result,
            weather_result,
            alert_result,
        )
        candidate_resolution = await DeepSeekCandidateResolver(self._deepseek).resolve(
            planning_context,
            governor,
        )
        candidate_result = candidate_resolution.result
        if candidate_result.status is ProviderResultStatus.UNAVAILABLE:
            await _advance(history, PlanningStatus.FAILED, state_observer)
            return _outcome(
                history,
                governor,
                candidate_resolution_error=candidate_resolution.error_code,
                candidate_repaired=candidate_resolution.repaired,
                candidate_validation_stage=candidate_resolution.validation_stage,
                candidate_validation_code=candidate_resolution.validation_code,
                candidate_time_failure=candidate_resolution.validation_time_failure,
                city_result=city_result,
                accommodation_result=accommodation_result,
                accommodation=accommodation,
                poi_result=poi_result,
                weather_result=weather_result,
                alert_result=alert_result,
                candidate_result=candidate_result,
            )

        candidate = _require_data(candidate_result)
        await _advance(history, PlanningStatus.ENRICHING_ROUTES, state_observer)
        route_enrichments = await _enrich_routes(
            candidate,
            request,
            accommodation,
            pois.candidates,
            city.citycode,
            self._amap,
            governor,
            history[-1],
        )
        await _advance(history, PlanningStatus.VALIDATING, state_observer)
        provider_results = _provider_results(
            city_result,
            accommodation_result,
            poi_result,
            candidate_result,
            weather_result,
            alert_result,
            route_enrichments,
        )
        final_validation = evaluate_final_plan(
            candidate=candidate,
            city_adcode=city.adcode,
            pois=pois,
            poi_source_ids=_source_ids(poi_result),
            accommodation=accommodation,
            day_windows=request.day_windows,
            budget=request.budget,
            cost_items=_cost_items_with_local_transport(
                request,
                route_enrichments,
            ),
            route_enrichments=route_enrichments,
            weather_result=weather_result,
            expected_weather_location_id=(request.weather_location_id or accommodation.location_id),
            provider_results=provider_results,
            evaluated_at=request.evaluated_at,
            hard_constraints=request.hard_constraints,
        )
        await _advance(history, final_validation.status, state_observer)
        return _outcome(
            history,
            governor,
            candidate_resolution_error=candidate_resolution.error_code,
            candidate_repaired=candidate_resolution.repaired,
            candidate_validation_stage=candidate_resolution.validation_stage,
            candidate_validation_code=candidate_resolution.validation_code,
            candidate_time_failure=candidate_resolution.validation_time_failure,
            city_result=city_result,
            accommodation_result=accommodation_result,
            accommodation=accommodation,
            poi_result=poi_result,
            weather_result=weather_result,
            alert_result=alert_result,
            candidate_result=candidate_result,
            route_enrichments=route_enrichments,
            final_validation=final_validation,
        )


async def _advance(
    history: list[PlanningStatus],
    target: PlanningStatus,
    state_observer: Callable[[PlanningStatus], Awaitable[None]] | None,
) -> None:
    result = PlanningStateMachine.transition(
        PlanningTransitionCommand(current_status=history[-1], target_status=target)
    )
    history.append(result.current_status)
    if state_observer is not None:
        await state_observer(result.current_status)


def _outcome(
    history: list[PlanningStatus],
    governor: ToolCallGovernor,
    *,
    candidate_resolution_error: CandidateResolutionErrorCode | None = None,
    candidate_repaired: bool = False,
    candidate_validation_stage: CandidateValidationStage | None = None,
    candidate_validation_code: CandidateValidationCode | None = None,
    candidate_time_failure: CandidateTimeFailureCode | None = None,
    city_result: ProviderResult[CityResolution] | None = None,
    accommodation_result: ProviderResult[PoiSearchResult] | None = None,
    accommodation: AccommodationAnchor | None = None,
    poi_result: ProviderResult[PoiSearchResult] | None = None,
    weather_result: ProviderResult[WeatherForecastResult] | None = None,
    alert_result: ProviderResult[WeatherAlertsResult] | None = None,
    candidate_result: ProviderResult[PlanCandidate] | None = None,
    route_enrichments: tuple[RouteEnrichmentResult, ...] = (),
    final_validation: FinalValidationResult | None = None,
) -> OfflinePlanningOutcome:
    return OfflinePlanningOutcome(
        status=history[-1],
        state_history=tuple(history),
        tool_calls=governor.snapshot(),
        candidate_resolution_error=candidate_resolution_error,
        candidate_repaired=candidate_repaired,
        candidate_validation_stage=candidate_validation_stage,
        candidate_validation_code=candidate_validation_code,
        candidate_time_failure=candidate_time_failure,
        city_result=city_result,
        accommodation_result=accommodation_result,
        accommodation=accommodation,
        poi_result=poi_result,
        weather_result=weather_result,
        alert_result=alert_result,
        candidate_result=candidate_result,
        route_enrichments=route_enrichments,
        final_validation=final_validation,
    )


async def _governed_call[T](
    governor: ToolCallGovernor,
    capability: ToolCallCapability,
    status: PlanningStatus,
    operation: Callable[[], Awaitable[ProviderResult[T]]],
) -> ProviderResult[T]:
    permit = governor.reserve(capability, status)
    result: ProviderResult[T] | None = None
    try:
        result = await operation()
    finally:
        try:
            governor.complete(permit)
        except ToolCallGovernanceError as error:
            provider_timeout = (
                result is not None
                and result.error is not None
                and result.error.category is ProviderErrorCategory.TIMEOUT
            )
            if error.code is not ToolCallGovernanceErrorCode.CALL_TIMEOUT or not provider_timeout:
                raise
    assert result is not None
    return result


def _planning_context(
    request: OfflinePlanningRequest,
    city: CityResolution,
    accommodation: AccommodationAnchor,
    pois: PoiSearchResult,
    city_result: ProviderResult[CityResolution],
    poi_result: ProviderResult[PoiSearchResult],
    weather_result: ProviderResult[WeatherForecastResult] | None,
    alert_result: ProviderResult[WeatherAlertsResult] | None,
) -> PlanningContext:
    observations = [
        PlanningObservation("city", "city resolved", _source_ids(city_result)),
        PlanningObservation("pois", "POI candidates collected", _source_ids(poi_result)),
    ]
    if weather_result is not None:
        observations.append(
            PlanningObservation(
                "weather",
                _weather_summary(weather_result),
                _source_ids(weather_result),
            )
        )
    if alert_result is not None:
        observations.append(
            PlanningObservation(
                "weather_alerts",
                _alert_summary(alert_result),
                _source_ids(alert_result),
            )
        )
    return PlanningContext(
        city_name=city.city_name,
        city_adcode=city.adcode,
        start_date=request.trip.start_date,
        end_date=request.trip.end_date,
        travelers=request.trip.travelers,
        budget=request.budget,
        interests=request.trip.interests,
        hard_constraints=request.hard_constraints,
        allowed_tools=tuple(PlanningToolName),
        locations=tuple(
            PlanningLocation(item.location_id, item.name, item.category, item.city_adcode)
            for item in pois.candidates
        ),
        observations=tuple(observations),
        free_text=request.trip.free_text,
        route_mode=request.route_mode,
        day_windows=tuple(
            PlanningDayWindow(item.day_offset, item.start_time, item.end_time)
            for item in request.day_windows
        ),
        accommodation=PlanningLocation(
            accommodation.location_id,
            "accommodation anchor",
            "accommodation_anchor",
            accommodation.city_adcode,
        ),
        activity_source_ids=_source_ids(poi_result),
    )


async def _enrich_routes(
    candidate: PlanCandidate,
    request: OfflinePlanningRequest,
    accommodation: AccommodationAnchor,
    pois: tuple[PoiCandidate, ...],
    citycode: str,
    amap: AmapPort,
    governor: ToolCallGovernor,
    status: PlanningStatus,
) -> tuple[RouteEnrichmentResult, ...]:
    coordinates = {item.location_id: item.coordinates for item in pois}
    coordinates[accommodation.location_id] = accommodation.coordinates
    windows = {item.day_offset: item for item in request.day_windows}
    enrichments: list[RouteEnrichmentResult] = []
    for day_offset in (0, 1):
        try:
            expected = DailyRoutePlan(
                accommodation.location_id,
                windows[day_offset],
                route_activities(candidate, day_offset),
                (),
            ).expected_legs()
        except (DomainInvariantError, KeyError):
            continue
        for leg in expected:
            origin = coordinates.get(leg.origin_location_id)
            destination = coordinates.get(leg.destination_location_id)
            if origin is None or destination is None:
                enrichments.append(RouteEnrichmentResult(day_offset, leg, None, None))
                continue
            route_request = RouteCalculationRequest(
                leg.origin_location_id,
                leg.destination_location_id,
                origin,
                destination,
                citycode,
                citycode,
                request.route_mode,
            )
            route_result = await _governed_call(
                governor,
                ToolCallCapability.CALCULATE_ROUTES,
                status,
                _route_operation(amap, route_request),
            )
            enrichments.append(RouteEnrichmentResult(day_offset, leg, route_request, route_result))
    return tuple(enrichments)


def _route_operation(
    amap: AmapPort,
    request: RouteCalculationRequest,
) -> Callable[[], Awaitable[ProviderResult[RouteLeg]]]:
    async def calculate() -> ProviderResult[RouteLeg]:
        return await amap.calculate_routes(request)

    return calculate


def _cost_items_with_local_transport(
    request: OfflinePlanningRequest,
    routes: tuple[RouteEnrichmentResult, ...],
) -> tuple[BudgetCostItem, ...]:
    if not request.derive_local_transport_cost:
        return request.cost_items
    if any(item.category is CostCategory.LOCAL_TRANSPORT for item in request.cost_items):
        return request.cost_items
    amount = Decimal("0.00")
    if request.route_mode is RouteMode.PUBLIC_TRANSIT:
        amount = Decimal(10 * request.trip.travelers * len(routes)).quantize(Decimal("0.01"))
    local_transport = BudgetCostItem(
        uuid5(
            NAMESPACE_URL,
            (
                f"f-001:local-transport:{request.trip.city}:"
                f"{request.trip.start_date.isoformat()}:{request.trip.travelers}:"
                f"{request.route_mode.value}:{len(routes)}"
            ),
        ),
        CostCategory.LOCAL_TRANSPORT,
        CostConfidence.ESTIMATED,
        Money(amount),
    )
    return (*request.cost_items, local_transport)


def _source_ids[T](result: ProviderResult[T]) -> tuple[UUID, ...]:
    return tuple(record.source_id for record in result.source_records)


def _weather_summary(result: ProviderResult[WeatherForecastResult]) -> str:
    if result.data is None:
        return f"weather {result.status.value}"
    return "; ".join(
        (
            f"{item.forecast_date.isoformat()} day={item.condition_day} "
            f"night={item.condition_night} min_c={item.temperature_min_celsius} "
            f"max_c={item.temperature_max_celsius}"
        )
        for item in result.data.days
    )


def _alert_summary(result: ProviderResult[WeatherAlertsResult]) -> str:
    if result.data is None:
        return f"weather alerts {result.status.value}"
    if not result.data.alerts:
        return "no current weather alerts"
    return "; ".join(
        f"title={item.title} severity={item.severity or 'unknown'}" for item in result.data.alerts
    )


def _require_data[T](result: ProviderResult[T]) -> T:
    if result.data is None:
        raise AssertionError("available ProviderResult must contain data")
    return result.data


def _provider_results(
    city: ProviderResult[CityResolution],
    accommodation: ProviderResult[PoiSearchResult] | None,
    pois: ProviderResult[PoiSearchResult],
    candidate: ProviderResult[PlanCandidate],
    weather: ProviderResult[WeatherForecastResult] | None,
    alerts: ProviderResult[WeatherAlertsResult] | None,
    routes: tuple[RouteEnrichmentResult, ...],
) -> tuple[ProviderResult[object], ...]:
    values: list[ProviderResult[object]] = [
        cast(ProviderResult[object], city),
        cast(ProviderResult[object], pois),
        cast(ProviderResult[object], candidate),
    ]
    if accommodation is not None:
        values.append(cast(ProviderResult[object], accommodation))
    if weather is not None:
        values.append(cast(ProviderResult[object], weather))
    if alerts is not None:
        values.append(cast(ProviderResult[object], alerts))
    values.extend(
        cast(ProviderResult[object], item.result) for item in routes if item.result is not None
    )
    return tuple(values)
