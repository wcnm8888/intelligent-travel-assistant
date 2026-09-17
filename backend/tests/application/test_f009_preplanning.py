from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.application.f009 import (
    F009CityFact,
    F009MapPinFact,
    F009PoiQuery,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
    F009ServiceError,
    F009ServiceErrorCode,
    PreplanningService,
)
from intelligent_travel_assistant.application.tooling import PacedAttemptLimiter
from intelligent_travel_assistant.contracts.f009 import (
    AccommodationChoice,
    AccommodationConfidence,
    AccommodationMode,
    Gcj02Point,
    PoiConfirmationStatus,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
    PoiSearchQuery,
    PreplanningSelection,
    PreplanningSelectionUpdate,
    PreplanningSessionCreateRequest,
    PreplanningState,
    PreplanningTripInput,
    PreplanningTripUpdate,
)
from intelligent_travel_assistant.contracts.trip_planning import (
    Money,
    MultiDayTimeWindow,
    Pace,
    TransportMode,
)
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderOperation,
    attempt_pacing_policy_for,
)

SESSION_ID = UUID("20000000-0000-4000-8000-000000000001")
LODGING_ID = UUID("20000000-0000-4000-8000-000000000002")
WEST_LAKE_ID = UUID("20000000-0000-4000-8000-000000000003")


@dataclass
class Clock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass
class MonotonicClock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.value += seconds


class FakeProvider:
    def __init__(self) -> None:
        self.search_calls = 0
        self.items = {
            PoiPurpose.ACCOMMODATION: (option(LODGING_ID, PoiPurpose.ACCOMMODATION, "龙翔桥"),),
            PoiPurpose.VISIT: (option(WEST_LAKE_ID, PoiPurpose.VISIT, "西湖风景名胜区"),),
        }

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        assert city == "杭州"
        return F009ProviderOutcome(F009CityFact("杭州市", "330100", "0571", None))

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        self.search_calls += 1
        return F009ProviderOutcome(self.items[query.purpose])

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        return F009ProviderOutcome(F009MapPinFact("湖滨地图锚点", "330100", "330102", coordinate))

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        raise AssertionError(f"route not expected: {query}")


def option(location_id: UUID, purpose: PoiPurpose, name: str) -> PoiOption:
    return PoiOption(
        location_id=location_id,
        provider_place_id=f"provider-{location_id}",
        name=name,
        address="杭州市",
        city_adcode="330100",
        district_adcode="330102",
        category_code="hotel" if purpose is PoiPurpose.ACCOMMODATION else "scenic_area",
        category_label="住宿" if purpose is PoiPurpose.ACCOMMODATION else "风景名胜",
        coordinate_gcj02=Gcj02Point(longitude=120.16, latitude=30.25),
        purpose=purpose,
        scope_kind=PoiScopeKind.POINT,
        confirmation_status=PoiConfirmationStatus.VERIFIED,
    )


def request() -> PreplanningSessionCreateRequest:
    return PreplanningSessionCreateRequest(
        trip=PreplanningTripInput(
            city="杭州",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            travelers=2,
            total_budget=Money(amount=Decimal("3000")),
            pace=Pace.BALANCED,
            transport_modes=(TransportMode.PUBLIC_TRANSIT, TransportMode.WALKING),
            day_windows=(
                MultiDayTimeWindow(day_offset=0, start_time=time(9), end_time=time(20)),
                MultiDayTimeWindow(day_offset=1, start_time=time(9), end_time=time(20)),
            ),
        )
    )


def test_session_search_cache_and_selection_revision() -> None:
    async def scenario() -> None:
        provider = FakeProvider()
        clock = Clock(datetime(2026, 9, 13, 6, tzinfo=UTC))
        service = PreplanningService(provider, clock=clock, id_factory=lambda: SESSION_ID)
        created = await service.create(request())
        assert created.state is PreplanningState.DRAFT
        assert created.city_adcode == "330100"

        accommodation_query = PoiSearchQuery(
            purpose=PoiPurpose.ACCOMMODATION,
            keywords="龙翔桥",
        )
        first = await service.search(SESSION_ID, accommodation_query)
        second = await service.search(SESSION_ID, accommodation_query)
        assert first.items == second.items
        assert provider.search_calls == 1
        assert second.calls.poi_search == 1

        await service.search(
            SESSION_ID,
            PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="西湖"),
        )
        selected = await service.update_selection(
            SESSION_ID,
            PreplanningSelectionUpdate(
                expected_revision=0,
                selection=PreplanningSelection(
                    accommodation=AccommodationChoice(
                        mode=AccommodationMode.EXACT_POI,
                        label="龙翔桥",
                        confidence=AccommodationConfidence.EXACT,
                        semantic_location_id=LODGING_ID,
                        route_anchor_location_id=LODGING_ID,
                    ),
                    pois=(
                        PoiIntent(
                            location_id=WEST_LAKE_ID,
                            route_anchor_location_id=WEST_LAKE_ID,
                            importance=PoiImportance.MUST_VISIT,
                            expected_duration_minutes=120,
                        ),
                    ),
                ),
            ),
        )
        assert selected.revision == 1

        revised_trip = request().trip.model_copy(update={"travelers": 3})
        trip_updated = await service.update_trip(
            SESSION_ID,
            PreplanningTripUpdate(expected_revision=1, trip=revised_trip),
        )
        assert trip_updated.revision == 2
        assert trip_updated.trip.travelers == 3
        assert trip_updated.selection == selected.selection

        with pytest.raises(F009ServiceError) as stale_trip:
            await service.update_trip(
                SESSION_ID,
                PreplanningTripUpdate(expected_revision=1, trip=revised_trip),
            )
        assert stale_trip.value.code is F009ServiceErrorCode.REVISION_CONFLICT
        assert selected.state is PreplanningState.NEEDS_CONFIRMATION

        assert selected.selection is not None
        with pytest.raises(F009ServiceError) as caught:
            await service.update_selection(
                SESSION_ID,
                PreplanningSelectionUpdate(
                    expected_revision=0,
                    selection=selected.selection,
                ),
            )
        assert caught.value.code is F009ServiceErrorCode.REVISION_CONFLICT

    asyncio.run(scenario())


def test_concurrent_identical_searches_are_single_flight() -> None:
    async def scenario() -> None:
        provider = FakeProvider()
        service = PreplanningService(provider, id_factory=lambda: SESSION_ID)
        await service.create(request())
        query = PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="西湖")

        first, second = await asyncio.gather(
            service.search(SESSION_ID, query),
            service.search(SESSION_ID, query),
        )

        assert first.items == second.items
        assert provider.search_calls == 1
        assert second.calls.poi_search == 1

    asyncio.run(scenario())


def test_session_sliding_expiry_is_distinct_from_not_found() -> None:
    async def scenario() -> None:
        clock = Clock(datetime(2026, 9, 13, 6, tzinfo=UTC))
        service = PreplanningService(FakeProvider(), clock=clock, id_factory=lambda: SESSION_ID)
        await service.create(request())
        clock.value += timedelta(minutes=31)

        with pytest.raises(F009ServiceError) as caught:
            await service.get(SESSION_ID)
        assert caught.value.code is F009ServiceErrorCode.SESSION_EXPIRED

    asyncio.run(scenario())


def test_map_pin_requires_same_city_reverse_geocode() -> None:
    async def scenario() -> None:
        service = PreplanningService(FakeProvider(), id_factory=lambda: SESSION_ID)
        await service.create(request())
        result = await service.create_map_pin(
            SESSION_ID,
            expected_revision=0,
            coordinate=Gcj02Point(longitude=120.17, latitude=30.26),
        )
        assert result.city_adcode == "330100"
        assert result.calls.reverse_geocode == 1

    asyncio.run(scenario())


def test_all_f009_amap_operations_share_the_two_qps_no_burst_timeline() -> None:
    async def scenario() -> None:
        clock = MonotonicClock()
        policy = attempt_pacing_policy_for(
            Provider.AMAP,
            ProviderOperation.CALCULATE_ROUTES,
        )
        assert policy is not None
        limiter = PacedAttemptLimiter(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            policy=policy,
            clock=clock,
            sleeper=clock.sleep,
        )
        service = PreplanningService(
            FakeProvider(),
            route_limiter=limiter,
            monotonic_clock=clock,
            id_factory=lambda: SESSION_ID,
        )

        await service.create(request())
        await service.search(
            SESSION_ID,
            PoiSearchQuery(purpose=PoiPurpose.ACCOMMODATION, keywords="龙翔桥"),
        )
        await service.search(
            SESSION_ID,
            PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="西湖"),
        )
        await service.create_map_pin(
            SESSION_ID,
            expected_revision=0,
            coordinate=Gcj02Point(longitude=120.17, latitude=30.26),
        )

        assert clock.value == 1.5

    asyncio.run(scenario())
