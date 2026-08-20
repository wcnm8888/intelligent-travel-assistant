"""Offline V3 multi-city planning over existing provider-neutral ports."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AnyHttpUrl

from intelligent_travel_assistant.application.planning import DeepSeekProposalResolver
from intelligent_travel_assistant.application.ports import (
    AmapPort,
    CityResolution,
    CityResolutionRequest,
    CurrentWeatherAlertsRequest,
    DeepSeekPort,
    PlanningContext,
    PlanningDayWindow,
    PlanningLocation,
    PlanningObservation,
    PlanningToolName,
    PlanProposal,
    PoiCandidate,
    PoiSearchRequest,
    PoiSearchResult,
    QWeatherPort,
    RouteCalculationRequest,
    WeatherAlertsResult,
    WeatherForecastRequest,
    WeatherForecastResult,
)
from intelligent_travel_assistant.application.repositories import PlanningJobResultV3
from intelligent_travel_assistant.application.services.offline_planning import _governed_call
from intelligent_travel_assistant.application.tooling import (
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernor,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    BudgetAssessment,
    BudgetSummary,
    ConstraintViolation,
    Coordinates,
    CoordinateSystem,
    CostCategory,
    CostConfidence,
    CostItem,
    DataFreshness,
    IntercityMode,
    ItineraryItem,
    LocationRef,
    Money,
    PlanDayV3,
    PlanIntercitySegmentV3,
    PlanningStatus,
    ProviderName,
    ResolvedDestination,
    RouteLeg,
    RouteMode,
    SourceRecord,
    TransportMode,
    TripPlanRequestV3,
    TripPlanV3,
    Uncertainty,
    ViolationSeverity,
    WeatherAlert,
    WeatherSnapshot,
)
from intelligent_travel_assistant.domain import (
    Money as DomainMoney,
)
from intelligent_travel_assistant.domain import (
    ProviderErrorCode,
    ProviderResult,
    ProviderResultStatus,
    evaluate_freshness,
)
from intelligent_travel_assistant.domain import (
    RouteLeg as DomainRouteLeg,
)
from intelligent_travel_assistant.domain import (
    RouteMode as DomainRouteMode,
)

_USER_WARNING = "未核验班次、票价、余票或库存"
_USER_DISCLOSURE = "城际段由用户提供，未核验班次、票价、余票或库存。"
_ROUTE_BUFFER_MINUTES = {
    DomainRouteMode.WALKING: 10,
    DomainRouteMode.PUBLIC_TRANSIT: 15,
}
_DURATION_MINUTES = {"short": 60, "standard": 120, "long": 180, "unknown": 120}


@dataclass(frozen=True, slots=True)
class _CityFacts:
    index: int
    city_result: ProviderResult[CityResolution]
    accommodation_result: ProviderResult[PoiSearchResult]
    poi_result: ProviderResult[PoiSearchResult]
    station_result: ProviderResult[PoiSearchResult] | None
    weather_result: ProviderResult[WeatherForecastResult] | None
    alert_result: ProviderResult[WeatherAlertsResult] | None

    @property
    def city(self) -> CityResolution:
        assert self.city_result.data is not None
        return self.city_result.data

    @property
    def accommodation(self) -> PoiCandidate:
        assert self.accommodation_result.data is not None
        return self.accommodation_result.data.candidates[0]


@dataclass(frozen=True, slots=True)
class _RouteNeed:
    day_offset: int
    origin: PoiCandidate
    destination: PoiCandidate


@dataclass(frozen=True, slots=True)
class _RouteFact:
    need: _RouteNeed
    result: ProviderResult[DomainRouteLeg]


class MultiCityPlanningOrchestrator:
    """Own one V3 job governor while reusing existing city-scoped ports."""

    __slots__ = ("_amap", "_deepseek", "_governor_factory", "_qweather")

    def __init__(
        self,
        amap: AmapPort,
        qweather: QWeatherPort,
        deepseek: DeepSeekPort,
        governor_factory: Callable[[int, int], ToolCallGovernor],
    ) -> None:
        self._amap = amap
        self._qweather = qweather
        self._deepseek = deepseek
        self._governor_factory = governor_factory

    async def plan(
        self,
        request: TripPlanRequestV3,
        *,
        job_id: UUID,
        evaluated_at: datetime,
        state_observer: Callable[[PlanningStatus], Awaitable[None]] | None = None,
    ) -> PlanningJobResultV3:
        """Collect city facts, ask the model once, and deterministically build V3."""

        governor = self._governor_factory(len(request.city_stays), request.day_count)
        try:
            await _observe(PlanningStatus.COLLECTING, state_observer)
            facts = await self._collect_cities(request, governor)
            if any(item is None for item in facts):
                return _failed_result("provider_unavailable", retryable=True)
            cities = tuple(item for item in facts if item is not None)
            if len({item.city.adcode for item in cities}) != len(cities):
                return _needs_input_result("city_stays")

            await _observe(PlanningStatus.PLANNING, state_observer)
            context = _planning_context(request, cities)
            resolution = await DeepSeekProposalResolver(self._deepseek).resolve(context, governor)
            if resolution.result.data is None:
                return _failed_result("model_output_invalid", retryable=False)
            proposal = resolution.result.data

            await _observe(PlanningStatus.ENRICHING_ROUTES, state_observer)
            route_needs = _route_needs(request, cities, proposal)
            route_facts = await self._collect_routes(route_needs, cities, request, governor)
            if any(not _route_fact_valid(item) for item in route_facts):
                return _failed_result("route_data_unavailable", retryable=True)

            await _observe(PlanningStatus.VALIDATING, state_observer)
            return _build_result(
                request,
                cities,
                proposal,
                route_facts,
                resolution.result,
                job_id=job_id,
                evaluated_at=evaluated_at,
            )
        except ToolCallGovernanceError as error:
            return _failed_result(error.code.value, retryable=False)

    async def _collect_cities(
        self,
        request: TripPlanRequestV3,
        governor: ToolCallGovernor,
    ) -> tuple[_CityFacts | None, ...]:
        semaphore = asyncio.Semaphore(2)

        async def collect(index: int) -> _CityFacts | None:
            async with semaphore:
                stay = request.city_stays[index]
                city_result = await _governed_call(
                    governor,
                    ToolCallCapability.RESOLVE_CITY,
                    PlanningStatus.COLLECTING,
                    lambda: self._amap.resolve_city(CityResolutionRequest(stay.city)),
                )
                if city_result.data is None or not _mainland_adcode(city_result.data.adcode):
                    return None
                city = city_result.data
                accommodation_result = await _governed_call(
                    governor,
                    ToolCallCapability.SEARCH_POIS,
                    PlanningStatus.COLLECTING,
                    lambda: self._amap.search_pois(
                        PoiSearchRequest(
                            city.adcode,
                            (stay.accommodation.area_or_poi,),
                            ("lodging",),
                            3,
                        )
                    ),
                )
                poi_result = await _governed_call(
                    governor,
                    ToolCallCapability.SEARCH_POIS,
                    PlanningStatus.COLLECTING,
                    lambda: self._amap.search_pois(
                        PoiSearchRequest(
                            city.adcode,
                            request.preferences.interests or ("景点",),
                            ("scenic_area", "museum"),
                            min(20, max(6, 2 * request.day_count + 2)),
                        )
                    ),
                )
                station_names = _station_names(request, index)
                station_result = None
                if station_names:
                    station_result = await _governed_call(
                        governor,
                        ToolCallCapability.SEARCH_POIS,
                        PlanningStatus.COLLECTING,
                        lambda: self._amap.search_pois(
                            PoiSearchRequest(city.adcode, station_names, (), len(station_names)),
                        ),
                    )
                if (
                    accommodation_result.data is None
                    or not accommodation_result.data.candidates
                    or poi_result.data is None
                    or not poi_result.data.candidates
                    or (station_names and (station_result is None or station_result.data is None))
                ):
                    return None
                accommodation = accommodation_result.data.candidates[0]
                if accommodation.city_adcode != city.adcode or accommodation.coordinates is None:
                    return None
                accommodation_coordinates = accommodation.coordinates
                weather_result = await _governed_call(
                    governor,
                    ToolCallCapability.GET_WEATHER_FORECAST,
                    PlanningStatus.COLLECTING,
                    lambda: self._qweather.get_weather_forecast(
                        WeatherForecastRequest(
                            accommodation.location_id,
                            accommodation_coordinates,
                            request.start_date,
                            request.end_date,
                        )
                    ),
                )
                alert_result = await _governed_call(
                    governor,
                    ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
                    PlanningStatus.COLLECTING,
                    lambda: self._qweather.get_current_weather_alerts(
                        CurrentWeatherAlertsRequest(
                            accommodation.location_id,
                            accommodation_coordinates,
                        )
                    ),
                )
                return _CityFacts(
                    index,
                    city_result,
                    accommodation_result,
                    poi_result,
                    station_result,
                    weather_result,
                    alert_result,
                )

        return tuple(
            await asyncio.gather(*(collect(index) for index in range(len(request.city_stays))))
        )

    async def _collect_routes(
        self,
        needs: tuple[_RouteNeed, ...],
        cities: tuple[_CityFacts, ...],
        request: TripPlanRequestV3,
        governor: ToolCallGovernor,
    ) -> tuple[_RouteFact, ...]:
        semaphore = asyncio.Semaphore(2)
        citycodes = {item.city.adcode: item.city.citycode for item in cities}
        mode = (
            DomainRouteMode.PUBLIC_TRANSIT
            if TransportMode.PUBLIC_TRANSIT in request.transport_modes
            else DomainRouteMode.WALKING
        )

        async def collect(need: _RouteNeed) -> _RouteFact:
            async with semaphore:
                if need.origin.coordinates is None or need.destination.coordinates is None:
                    raise ValueError("route_coordinates_missing")
                origin_coordinates = need.origin.coordinates
                destination_coordinates = need.destination.coordinates
                result = await _governed_call(
                    governor,
                    ToolCallCapability.CALCULATE_ROUTES,
                    PlanningStatus.ENRICHING_ROUTES,
                    lambda: self._amap.calculate_routes(
                        RouteCalculationRequest(
                            need.origin.location_id,
                            need.destination.location_id,
                            origin_coordinates,
                            destination_coordinates,
                            citycodes[need.origin.city_adcode],
                            citycodes[need.destination.city_adcode],
                            mode,
                        )
                    ),
                )
                return _RouteFact(need, result)

        return tuple(await asyncio.gather(*(collect(need) for need in needs)))


async def _observe(
    status: PlanningStatus,
    observer: Callable[[PlanningStatus], Awaitable[None]] | None,
) -> None:
    if observer is not None:
        await observer(status)


def _mainland_adcode(value: str) -> bool:
    return (
        len(value) == 6
        and value.isascii()
        and value.isdigit()
        and value[:2]
        not in {
            "71",
            "81",
            "82",
        }
    )


def _station_names(request: TripPlanRequestV3, city_index: int) -> tuple[str, ...]:
    names: list[str] = []
    for segment in request.intercity_segments:
        if segment.from_city_index == city_index:
            names.append(segment.departure_station)
        if segment.to_city_index == city_index:
            names.append(segment.arrival_station)
    return tuple(dict.fromkeys(names))


def _day_city_indices(request: TripPlanRequestV3) -> tuple[tuple[int, int, int], ...]:
    transfers = {item.departure_at.date(): item for item in request.intercity_segments}
    current = 0
    values: list[tuple[int, int, int]] = []
    for offset in range(request.day_count):
        local_date = request.start_date + timedelta(days=offset)
        segment = transfers.get(local_date)
        if segment is None:
            values.append((current, current, current))
        else:
            values.append((segment.from_city_index, segment.to_city_index, segment.to_city_index))
            current = segment.to_city_index
    return tuple(values)


def _planning_context(
    request: TripPlanRequestV3,
    cities: tuple[_CityFacts, ...],
) -> PlanningContext:
    locations = tuple(
        PlanningLocation(item.location_id, item.name, item.category, item.city_adcode)
        for city in cities
        for item in _poi_candidates(city.poi_result)
    )
    accommodations = tuple(
        PlanningLocation(
            city.accommodation.location_id,
            city.accommodation.name,
            city.accommodation.category,
            city.accommodation.city_adcode,
        )
        for city in cities
    )
    observations: list[PlanningObservation] = []
    for city in cities:
        observations.extend(
            (
                PlanningObservation("city", "city resolved", _source_ids(city.city_result)),
                PlanningObservation(
                    "pois", "POI candidates collected", _source_ids(city.poi_result)
                ),
            )
        )
        if city.weather_result is not None and city.weather_result.data is not None:
            observations.append(
                PlanningObservation(
                    "weather",
                    "weather forecast collected",
                    _source_ids(city.weather_result),
                )
            )
        if city.alert_result is not None and city.alert_result.data is not None:
            observations.append(
                PlanningObservation(
                    "weather_alerts",
                    "weather alerts collected",
                    _source_ids(city.alert_result),
                )
            )
    route_mode = (
        DomainRouteMode.PUBLIC_TRANSIT
        if TransportMode.PUBLIC_TRANSIT in request.transport_modes
        else DomainRouteMode.WALKING
    )
    return PlanningContext(
        city_name="多城市行程",
        city_adcode=cities[0].city.adcode,
        start_date=request.start_date,
        end_date=request.end_date,
        travelers=request.travelers,
        budget=DomainMoney(request.total_budget.amount),
        interests=request.preferences.interests,
        hard_constraints=request.preferences.hard_constraints,
        allowed_tools=tuple(PlanningToolName),
        locations=locations,
        observations=tuple(observations),
        free_text=request.preferences.free_text,
        route_mode=route_mode,
        day_windows=tuple(
            PlanningDayWindow(item.day_offset, item.start_time, item.end_time)
            for item in request.day_windows
        ),
        activity_source_ids=tuple(
            dict.fromkeys(
                source_id for city in cities for source_id in _source_ids(city.poi_result)
            )
        ),
        request_version="3",
        expected_dates=tuple(
            request.start_date + timedelta(days=offset) for offset in range(request.day_count)
        ),
        city_adcodes=tuple(item.city.adcode for item in cities),
        day_city_indices=_day_city_indices(request),
        accommodations=accommodations,
    )


def _route_needs(
    request: TripPlanRequestV3,
    cities: tuple[_CityFacts, ...],
    proposal: PlanProposal,
) -> tuple[_RouteNeed, ...]:
    locations = {
        item.location_id: item for city in cities for item in _poi_candidates(city.poi_result)
    }
    values: list[_RouteNeed] = []
    segments = {item.departure_at.date(): item for item in request.intercity_segments}
    for day_offset, day in enumerate(proposal.days):
        segment = segments.get(day.local_date)
        selections = tuple(locations[item.location_id] for item in day.selections)
        if segment is None:
            city_index = day.overnight_city_index
            assert city_index is not None
            chain = (
                cities[city_index].accommodation,
                *selections,
                cities[city_index].accommodation,
            )
        elif not selections:
            chain = ()
        else:
            selection = selections[0]
            if selection.city_adcode == cities[segment.from_city_index].city.adcode:
                chain = (
                    cities[segment.from_city_index].accommodation,
                    selection,
                    _station(cities[segment.from_city_index], segment.departure_station),
                )
            else:
                chain = (
                    _station(cities[segment.to_city_index], segment.arrival_station),
                    selection,
                    cities[segment.to_city_index].accommodation,
                )
        values.extend(
            _RouteNeed(day_offset, origin, destination)
            for origin, destination in zip(chain, chain[1:], strict=False)
            if origin.location_id != destination.location_id
        )
    return tuple(values)


def _station(city: _CityFacts, name: str) -> PoiCandidate:
    if city.station_result is None or city.station_result.data is None:
        raise ValueError("station_location_missing")
    candidates = city.station_result.data.candidates
    match = next((item for item in candidates if item.name == name), None)
    if match is None or match.city_adcode != city.city.adcode:
        raise ValueError("station_location_missing")
    return match


def _build_result(
    request: TripPlanRequestV3,
    cities: tuple[_CityFacts, ...],
    proposal: PlanProposal,
    route_facts: tuple[_RouteFact, ...],
    model_result: ProviderResult[PlanProposal],
    *,
    job_id: UUID,
    evaluated_at: datetime,
) -> PlanningJobResultV3:
    user_source_ids = tuple(
        _id(job_id, f"source:user:segment:{index}")
        for index in range(len(request.intercity_segments))
    )
    request_source_id = _id(job_id, "source:user:request")
    system_source_id = _id(job_id, "source:system")
    provider_results = tuple(_provider_results(cities, route_facts, model_result))
    sources = (
        SourceRecord(
            source_id=request_source_id,
            provider=ProviderName.USER,
            source_type="user_input",
            fetched_at=evaluated_at,
            freshness=DataFreshness.UNKNOWN_VALIDITY,
            attributions=("用户提供",),
            warnings=("用户输入仅用于本地离线规划。",),
        ),
        SourceRecord(
            source_id=system_source_id,
            provider=ProviderName.SYSTEM,
            source_type="estimation_rule",
            fetched_at=evaluated_at,
            freshness=DataFreshness.UNKNOWN_VALIDITY,
            warnings=("使用项目固定估算规则。",),
        ),
        *tuple(
            SourceRecord(
                source_id=source_id,
                provider=ProviderName.USER,
                source_type="user_provided_intercity_segment",
                fetched_at=evaluated_at,
                freshness=DataFreshness.UNKNOWN_VALIDITY,
                attributions=("用户提供",),
                warnings=(_USER_WARNING,),
            )
            for source_id in user_source_ids
        ),
        *_contract_sources(provider_results, evaluated_at=evaluated_at),
    )
    locations = _locations(cities)
    cost_items = _cost_items(
        request,
        route_facts,
        request_source_id=request_source_id,
        system_source_id=system_source_id,
        segment_source_ids=user_source_ids,
        job_id=job_id,
    )
    budget_summary = _budget_summary(request.total_budget, cost_items)
    segments = tuple(
        PlanIntercitySegmentV3(
            segment_id=_id(job_id, f"segment:{index}"),
            from_city_index=segment.from_city_index,
            to_city_index=segment.to_city_index,
            mode=segment.mode,
            departure_station_location_id=_station(
                cities[segment.from_city_index], segment.departure_station
            ).location_id,
            arrival_station_location_id=_station(
                cities[segment.to_city_index], segment.arrival_station
            ).location_id,
            departure_at=segment.departure_at,
            arrival_at=segment.arrival_at,
            fare=next(
                item
                for item in cost_items
                if item.cost_id == _id(job_id, f"cost:intercity:{index}")
            ),
            source_ids=(user_source_ids[index],),
        )
        for index, segment in enumerate(request.intercity_segments)
    )
    days, schedule_error = _schedule_days(
        request,
        cities,
        proposal,
        route_facts,
        segments,
        job_id=job_id,
    )
    destinations = tuple(
        ResolvedDestination(
            city_name=item.city.city_name,
            adcode=item.city.adcode,
            center=_coordinates(item.city.center),
            source_ids=_source_ids(item.city_result),
        )
        for item in cities
    )
    if schedule_error is not None:
        return PlanningJobResultV3(
            status=PlanningStatus.CONFLICT,
            resolved_destinations=destinations,
            plan=None,
            violations=(
                ConstraintViolation(
                    code="intercity_buffer_conflict",
                    severity=ViolationSeverity.ERROR,
                    message="城际缓冲与当天活动窗口无法同时满足。",
                ),
            ),
            warnings=(_USER_DISCLOSURE,),
            uncertainties=(),
            sources=sources,
            errors=(),
            retryable=False,
        )
    plan = TripPlanV3(
        plan_id=_id(job_id, "plan"),
        plan_format_version="3",
        city_adcodes=tuple(item.city.adcode for item in cities),
        start_date=request.start_date,
        end_date=request.end_date,
        locations=locations,
        intercity_segments=segments,
        days=days,
        budget_summary=budget_summary,
    )
    weather_missing = any(day.weather is None for day in days)
    provider_partial = any(item.status is not ProviderResultStatus.OK for item in provider_results)
    errors = _provider_errors(provider_results)
    unknowns = tuple(item for item in cost_items if item.confidence is CostConfidence.UNKNOWN)
    status = (
        PlanningStatus.PARTIAL
        if provider_partial or weather_missing or unknowns or errors
        else PlanningStatus.READY
    )
    if budget_summary.assessment is BudgetAssessment.OVER_BUDGET:
        status = PlanningStatus.CONFLICT
    violations = (
        (
            ConstraintViolation(
                code="budget_exceeded",
                severity=ViolationSeverity.ERROR,
                message="已知费用超过用户总预算。",
            ),
        )
        if status is PlanningStatus.CONFLICT
        else ()
    )
    uncertainties = tuple(
        Uncertainty(
            code="intercity_fare_unknown",
            message="城际费用未知。",
            affected_refs=(_id(job_id, f"segment:{index}"),),
            source_ids=(user_source_ids[index],),
        )
        for index, segment in enumerate(request.intercity_segments)
        if segment.fare is None
    )
    if weather_missing:
        uncertainties = (
            *uncertainties,
            Uncertainty(
                code="weather_incomplete",
                message="部分日期天气数据不完整。",
            ),
        )
    return PlanningJobResultV3(
        status=status,
        resolved_destinations=destinations,
        plan=plan,
        violations=violations,
        warnings=(_USER_DISCLOSURE, *proposal.warnings),
        uncertainties=uncertainties,
        sources=sources,
        errors=errors,
        retryable=status is PlanningStatus.PARTIAL and any(item.retryable for item in errors),
    )


def _schedule_days(
    request: TripPlanRequestV3,
    cities: tuple[_CityFacts, ...],
    proposal: PlanProposal,
    route_facts: tuple[_RouteFact, ...],
    segments: tuple[PlanIntercitySegmentV3, ...],
    *,
    job_id: UUID,
) -> tuple[tuple[PlanDayV3, ...], str | None]:
    route_map = {
        (
            item.need.day_offset,
            item.need.origin.location_id,
            item.need.destination.location_id,
        ): item
        for item in route_facts
    }
    poi_locations = {
        item.location_id: item for city in cities for item in _poi_candidates(city.poi_result)
    }
    transfer_by_date = {
        value.departure_at.date(): (source, value)
        for source, value in zip(request.intercity_segments, segments, strict=True)
    }
    windows = {item.day_offset: item for item in request.day_windows}
    days: list[PlanDayV3] = []
    for day_offset, proposal_day in enumerate(proposal.days):
        departure = proposal_day.departure_city_index
        arrival = proposal_day.arrival_city_index
        overnight = proposal_day.overnight_city_index
        assert departure is not None and arrival is not None and overnight is not None
        transfer = transfer_by_date.get(proposal_day.local_date)
        selection_pois = tuple(poi_locations[item.location_id] for item in proposal_day.selections)
        start = datetime.combine(proposal_day.local_date, windows[day_offset].start_time)
        end_bound = datetime.combine(proposal_day.local_date, windows[day_offset].end_time)
        if transfer is None:
            chain = (
                cities[overnight].accommodation,
                *selection_pois,
                cities[overnight].accommodation,
            )
            segment_id = None
        elif not selection_pois:
            chain = ()
            segment_id = transfer[1].segment_id
        elif selection_pois[0].city_adcode == cities[departure].city.adcode:
            before = _intercity_buffer_minutes(transfer[0].mode)[0]
            end_bound = min(end_bound, transfer[0].departure_at - timedelta(minutes=before))
            chain = (
                cities[departure].accommodation,
                selection_pois[0],
                _station(cities[departure], transfer[0].departure_station),
            )
            segment_id = transfer[1].segment_id
        else:
            after = _intercity_buffer_minutes(transfer[0].mode)[1]
            start = max(start, transfer[0].arrival_at + timedelta(minutes=after))
            chain = (
                _station(cities[arrival], transfer[0].arrival_station),
                selection_pois[0],
                cities[arrival].accommodation,
            )
            segment_id = transfer[1].segment_id

        cursor = start
        activities: list[ItineraryItem] = []
        routes: list[RouteLeg] = []
        for index, selection in enumerate(proposal_day.selections):
            if chain:
                route_fact = route_map.get(
                    (day_offset, chain[index].location_id, selection.location_id)
                )
                if route_fact is not None:
                    cursor = _after_route(cursor, route_fact, routes, job_id=job_id)
            duration = _DURATION_MINUTES[selection.duration_class.value]
            activity_end = cursor + timedelta(minutes=duration)
            activities.append(
                ItineraryItem(
                    item_id=_id(job_id, f"activity:{day_offset}:{index}"),
                    location_id=selection.location_id,
                    title=selection.title,
                    start_time=cursor.time(),
                    end_time=activity_end.time(),
                    source_ids=selection.source_ids,
                )
            )
            cursor = activity_end
        if chain and selection_pois:
            final_fact = route_map.get(
                (day_offset, selection_pois[-1].location_id, chain[-1].location_id)
            )
            if final_fact is not None:
                cursor = _after_route(cursor, final_fact, routes, job_id=job_id)
        if cursor > end_bound:
            return (), "intercity_buffer_conflict"
        days.append(
            PlanDayV3(
                local_date=proposal_day.local_date,
                departure_city_index=departure,
                arrival_city_index=arrival,
                overnight_city_index=overnight,
                intercity_segment_id=segment_id,
                accommodation_location_id=cities[overnight].accommodation.location_id,
                activities=tuple(activities),
                routes=tuple(routes),
                weather=_weather_for_day(cities[overnight], proposal_day.local_date),
            )
        )
    return tuple(days), None


def _after_route(
    cursor: datetime,
    fact: _RouteFact,
    routes: list[RouteLeg],
    *,
    job_id: UUID,
) -> datetime:
    route = fact.result.data
    assert route is not None
    source_ids = _source_ids(fact.result)
    routes.append(
        RouteLeg(
            route_id=_id(
                job_id,
                f"route:{fact.need.day_offset}:{fact.need.origin.location_id}:"
                f"{fact.need.destination.location_id}",
            ),
            origin_location_id=route.origin_location_id,
            destination_location_id=route.destination_location_id,
            mode=RouteMode(route.mode.value),
            distance_meters=route.distance_meters,
            duration_minutes=route.duration_minutes,
            source_ids=source_ids,
        )
    )
    return cursor + timedelta(minutes=route.duration_minutes + _ROUTE_BUFFER_MINUTES[route.mode])


def _weather_for_day(city: _CityFacts, local_date: object) -> WeatherSnapshot | None:
    if city.weather_result is None or city.weather_result.data is None:
        return None
    day = next(
        (item for item in city.weather_result.data.days if item.forecast_date == local_date),
        None,
    )
    if day is None:
        return None
    alerts: tuple[WeatherAlert, ...] = ()
    alert_sources: tuple[UUID, ...] = ()
    if city.alert_result is not None and city.alert_result.data is not None:
        alert_sources = _source_ids(city.alert_result)
        alerts = tuple(
            WeatherAlert(
                alert_id=item.alert_id,
                title=item.title,
                severity=item.severity,
                issued_at=item.issued_at,
                description=item.description,
                source_ids=alert_sources,
            )
            for item in city.alert_result.data.alerts
        )
    return WeatherSnapshot(
        forecast_date=day.forecast_date,
        location_id=city.accommodation.location_id,
        condition_day=day.condition_day,
        condition_night=day.condition_night,
        temperature_min_celsius=day.temperature_min_celsius,
        temperature_max_celsius=day.temperature_max_celsius,
        alerts=alerts,
        source_ids=_source_ids(city.weather_result),
    )


def _locations(cities: tuple[_CityFacts, ...]) -> tuple[LocationRef, ...]:
    values: list[LocationRef] = []
    seen: set[UUID] = set()
    for city in cities:
        groups = (
            (city.accommodation_result, (city.accommodation,)),
            (city.poi_result, _poi_candidates(city.poi_result)),
            (
                city.station_result,
                _poi_candidates(city.station_result) if city.station_result is not None else (),
            ),
        )
        for result, candidates in groups:
            if result is None:
                continue
            source_ids = _source_ids(result)
            for item in candidates:
                if item.location_id in seen:
                    continue
                seen.add(item.location_id)
                values.append(
                    LocationRef(
                        location_id=item.location_id,
                        provider=ProviderName.AMAP,
                        name=item.name,
                        category=item.category,
                        address=item.address,
                        city_adcode=item.city_adcode,
                        coordinates=_coordinates(item.coordinates),
                        source_ids=source_ids,
                    )
                )
    return tuple(values)


def _cost_items(
    request: TripPlanRequestV3,
    route_facts: tuple[_RouteFact, ...],
    *,
    request_source_id: UUID,
    system_source_id: UUID,
    segment_source_ids: tuple[UUID, ...],
    job_id: UUID,
) -> tuple[CostItem, ...]:
    values: list[CostItem] = []
    for index, stay in enumerate(request.city_stays):
        amount = (
            None
            if stay.accommodation.one_night_cost is None
            else Money(
                amount=(stay.accommodation.one_night_cost.amount * stay.nights).quantize(
                    Decimal("0.01")
                )
            )
        )
        values.append(
            CostItem(
                cost_id=_id(job_id, f"cost:accommodation:{index}"),
                category=CostCategory.ACCOMMODATION,
                confidence=(
                    CostConfidence.UNKNOWN if amount is None else CostConfidence.USER_PROVIDED
                ),
                amount=amount,
                description=f"第{index + 1}个城市住宿费用",
                source_ids=() if amount is None else (request_source_id,),
            )
        )
    for index, segment in enumerate(request.intercity_segments):
        values.append(
            CostItem(
                cost_id=_id(job_id, f"cost:intercity:{index}"),
                category=CostCategory.INTERCITY_TRANSPORT,
                confidence=(
                    CostConfidence.UNKNOWN if segment.fare is None else CostConfidence.USER_PROVIDED
                ),
                amount=segment.fare,
                description="用户提供城际费用",
                source_ids=(segment_source_ids[index],),
            )
        )
    values.append(
        CostItem(
            cost_id=_id(job_id, "cost:meal"),
            category=CostCategory.MEAL,
            confidence=CostConfidence.ESTIMATED,
            amount=Money(
                amount=(
                    request.meal_budget_per_person_per_day.amount
                    * request.travelers
                    * request.day_count
                ).quantize(Decimal("0.01"))
            ),
            description="按旅行天数和人数估算餐饮费用",
            source_ids=(system_source_id,),
        )
    )
    transit_count = sum(
        1
        for item in route_facts
        if item.result.data is not None and item.result.data.mode is DomainRouteMode.PUBLIC_TRANSIT
    )
    values.append(
        CostItem(
            cost_id=_id(job_id, "cost:local-transport"),
            category=CostCategory.LOCAL_TRANSPORT,
            confidence=CostConfidence.ESTIMATED,
            amount=Money(amount=Decimal(10 * transit_count * request.travelers)),
            description="按每人每段10元估算市内公交费用",
            source_ids=(system_source_id,),
        )
    )
    return tuple(values)


def _budget_summary(budget: Money, items: tuple[CostItem, ...]) -> BudgetSummary:
    known_total = sum(
        (item.amount.amount for item in items if item.amount is not None),
        Decimal("0.00"),
    )
    unknown_count = sum(item.confidence is CostConfidence.UNKNOWN for item in items)
    assessment = (
        BudgetAssessment.OVER_BUDGET
        if known_total > budget.amount
        else BudgetAssessment.INDETERMINATE
        if unknown_count
        else BudgetAssessment.WITHIN_BUDGET
    )
    return BudgetSummary(
        budget=budget,
        known_total=Money(amount=known_total.quantize(Decimal("0.01"))),
        unknown_count=unknown_count,
        assessment=assessment,
        cost_items=items,
    )


def _provider_results(
    cities: tuple[_CityFacts, ...],
    route_facts: tuple[_RouteFact, ...],
    model_result: ProviderResult[PlanProposal],
) -> Iterable[ProviderResult[object]]:
    for city in cities:
        for result in (
            city.city_result,
            city.accommodation_result,
            city.poi_result,
            city.station_result,
            city.weather_result,
            city.alert_result,
        ):
            if result is not None:
                yield result
    yield model_result
    for item in route_facts:
        yield item.result


def _contract_sources(
    results: tuple[ProviderResult[object], ...],
    *,
    evaluated_at: datetime,
) -> tuple[SourceRecord, ...]:
    values: list[SourceRecord] = []
    seen: set[UUID] = set()
    for result in results:
        for item in result.source_records:
            if item.source_id in seen:
                continue
            seen.add(item.source_id)
            values.append(
                SourceRecord(
                    source_id=item.source_id,
                    provider=ProviderName(item.provider.value),
                    source_type=item.source_type,
                    provider_record_id=None,
                    fetched_at=item.fetched_at,
                    valid_until=item.valid_until,
                    freshness=DataFreshness(
                        evaluate_freshness(
                            item.fetched_at,
                            item.valid_until,
                            max(evaluated_at, item.fetched_at),
                        ).value
                    ),
                    reference_url=cast(AnyHttpUrl | None, item.reference_url),
                    attributions=item.attributions,
                    warnings=result.warnings[:10],
                )
            )
    return tuple(values)


def _provider_errors(results: tuple[ProviderResult[object], ...]) -> tuple[ApiError, ...]:
    values: list[ApiError] = []
    seen: set[tuple[str, str]] = set()
    messages = {
        ProviderErrorCode.TIMEOUT: "外部服务响应超时。",
        ProviderErrorCode.RATE_LIMITED: "外部服务当前达到调用限制。",
        ProviderErrorCode.UNAVAILABLE: "外部服务当前不可用。",
        ProviderErrorCode.UNAUTHORIZED: "外部服务凭证未通过验证。",
        ProviderErrorCode.SCHEMA_INVALID: "外部服务返回了无法安全解析的数据。",
        ProviderErrorCode.DATA_MISSING: "外部服务没有返回可用数据。",
    }
    for result in results:
        if result.error is None:
            continue
        key = (result.provider.value, result.error.code.value)
        if key in seen:
            continue
        seen.add(key)
        values.append(
            ApiError(
                code=ApiErrorCode(result.error.code.value),
                message=messages[result.error.code],
                provider=result.provider.value,
                diagnostic_code=(
                    result.error.reason.value if result.error.reason is not None else None
                ),
                retryable=result.error.retryable,
            )
        )
    return tuple(values)


def _route_fact_valid(item: _RouteFact) -> bool:
    route = item.result.data
    if route is None:
        return False
    return (
        route.origin_location_id == item.need.origin.location_id
        and route.destination_location_id == item.need.destination.location_id
        and route.mode in _ROUTE_BUFFER_MINUTES
        and set(route.source_ids) <= set(_source_ids(item.result))
    )


def _failed_result(code: str, *, retryable: bool) -> PlanningJobResultV3:
    error_code = (
        ApiErrorCode.PROVIDER_UNAVAILABLE
        if code in {"provider_unavailable", "route_data_unavailable"}
        else ApiErrorCode.MODEL_OUTPUT_INVALID
        if code == "model_output_invalid"
        else ApiErrorCode.INTERNAL_ERROR
    )
    return PlanningJobResultV3(
        status=PlanningStatus.FAILED,
        resolved_destinations=(),
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(
            ApiError(
                code=error_code,
                message="多城市规划任务未能安全完成。",
                diagnostic_code=code,
                retryable=retryable,
            ),
        ),
        retryable=retryable,
    )


def _needs_input_result(field: str) -> PlanningJobResultV3:
    return PlanningJobResultV3(
        status=PlanningStatus.NEEDS_INPUT,
        resolved_destinations=(),
        plan=None,
        violations=(),
        warnings=(),
        uncertainties=(),
        sources=(),
        errors=(
            ApiError(
                code=ApiErrorCode.INPUT_INVALID,
                message="城市解析结果不唯一，需要补充或修正城市信息。",
                field=field,
                retryable=False,
            ),
        ),
        retryable=False,
    )


def _poi_candidates(
    result: ProviderResult[PoiSearchResult] | None,
) -> tuple[PoiCandidate, ...]:
    return () if result is None or result.data is None else result.data.candidates


def _source_ids[T](result: ProviderResult[T] | None) -> tuple[UUID, ...]:
    return () if result is None else tuple(item.source_id for item in result.source_records)


def _coordinates(value: object) -> Coordinates | None:
    from intelligent_travel_assistant.domain import Coordinates as DomainCoordinates

    if not isinstance(value, DomainCoordinates):
        return None
    return Coordinates(
        longitude=value.longitude,
        latitude=value.latitude,
        coordinate_system=CoordinateSystem(value.coordinate_system.value),
    )


def _intercity_buffer_minutes(mode: IntercityMode) -> tuple[int, int]:
    return {
        IntercityMode.RAIL: (60, 30),
        IntercityMode.AIR: (120, 60),
        IntercityMode.COACH: (45, 30),
    }[mode]


def _id(job_id: UUID, suffix: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"f-004b1:{job_id}:{suffix}")
