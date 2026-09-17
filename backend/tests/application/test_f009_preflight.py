from __future__ import annotations

import asyncio
import json
from datetime import date, time, timedelta
from decimal import Decimal
from itertools import pairwise
from uuid import UUID

from intelligent_travel_assistant.adapters.fakes.f009 import (
    SYNTHETIC_F009_POIS,
    SyntheticF009MapProvider,
    SyntheticF009NarrativeProvider,
)
from intelligent_travel_assistant.application.f009 import (
    F009CityFact,
    F009MapPinFact,
    F009Narrative,
    F009NarrativeDay,
    F009NarrativeRequest,
    F009PoiQuery,
    F009ProviderFailure,
    F009ProviderFailureKind,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
    PreplanningService,
)
from intelligent_travel_assistant.application.f009.service import _fit_map_plan_size
from intelligent_travel_assistant.application.f009.solver import haversine_meters
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
    PoiSelectionSource,
    PreplanningSelection,
    PreplanningSelectionUpdate,
    PreplanningSessionCreateRequest,
    PreplanningState,
    PreplanningTripInput,
    TripPlanRequestV5,
)
from intelligent_travel_assistant.contracts.f015 import TripPlanRequestV6
from intelligent_travel_assistant.contracts.trip_planning import (
    Money,
    MultiDayTimeWindow,
    Pace,
    PlanningStatus,
    TransportMode,
)

SESSION_ID = UUID("60000000-0000-4000-8000-000000000001")
FEASIBILITY_ID = UUID("60000000-0000-4000-8000-000000000002")
JOB_ID = UUID("60000000-0000-4000-8000-000000000010")
TRACE_ID = UUID("60000000-0000-4000-8000-000000000011")
PLAN_ID = UUID("60000000-0000-4000-8000-000000000012")
CLIENT_ID = UUID("60000000-0000-4000-8000-000000000013")
LODGING_ID = UUID("60000000-0000-4000-8000-000000000003")
POI_IDS = tuple(UUID(f"60000000-0000-4000-8000-00000000000{index}") for index in range(4, 7))


class RouteProvider:
    def __init__(self, failure: F009ProviderFailureKind | None = None) -> None:
        self.failure = failure
        self.route_calls = 0
        self.lodging = option(LODGING_ID, PoiPurpose.ACCOMMODATION, 120.16, 30.25)
        self.visits = tuple(
            option(location_id, PoiPurpose.VISIT, 120.16 + index * 0.01, 30.25)
            for index, location_id in enumerate(POI_IDS, start=1)
        )

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        return F009ProviderOutcome(F009CityFact("杭州市", "330100", "0571", None))

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        return F009ProviderOutcome(
            (self.lodging,) if query.purpose is PoiPurpose.ACCOMMODATION else self.visits
        )

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        raise AssertionError("reverse geocode not expected")

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        self.route_calls += 1
        if self.failure is not None:
            return F009ProviderOutcome(None, F009ProviderFailure(self.failure))
        distance = max(100, haversine_meters(query.origin, query.destination) + 100)
        return F009ProviderOutcome(
            F009RouteFact(
                distance_meters=distance,
                duration_minutes=20,
                points=(query.origin, query.destination),
            )
        )


class ReplacementRouteProvider(RouteProvider):
    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        self.route_calls += 1
        if POI_IDS[0] in {
            query.origin_location_id,
            query.destination_location_id,
        }:
            return F009ProviderOutcome(
                None,
                F009ProviderFailure(F009ProviderFailureKind.EMPTY_RESULT),
            )
        distance = max(100, haversine_meters(query.origin, query.destination) + 100)
        return F009ProviderOutcome(
            F009RouteFact(
                distance_meters=distance,
                duration_minutes=20,
                points=(query.origin, query.destination),
            )
        )


class NarrativeProvider:
    def __init__(self, *, valid: bool) -> None:
        self.valid = valid
        self.generate_calls = 0
        self.repair_calls = 0

    def _outcome(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        days = tuple(
            F009NarrativeDay(
                local_date=local_date,
                location_ids=(
                    tuple(location_id for location_id, _, _ in locations)
                    if self.valid
                    else (LODGING_ID,)
                ),
                pace_note="按已冻结顺序从容游览。",
                stop_narratives=tuple("留意现场指引。" for _ in locations),
                rationale="在已验证路线内保持当天节奏。",
            )
            for local_date, locations in request.days
        )
        return F009ProviderOutcome(F009Narrative(days, ("营业时间未核验。",)))

    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self.generate_calls += 1
        return self._outcome(request)

    async def repair(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self.repair_calls += 1
        return self._outcome(request)


class UnavailableNarrativeProvider(NarrativeProvider):
    def __init__(self) -> None:
        super().__init__(valid=True)

    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self.generate_calls += 1
        return F009ProviderOutcome(
            None,
            F009ProviderFailure(F009ProviderFailureKind.TIMEOUT, retryable=True),
        )


class SchemaFailureNarrativeProvider(NarrativeProvider):
    async def generate(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        self.generate_calls += 1
        return F009ProviderOutcome(
            None,
            F009ProviderFailure(F009ProviderFailureKind.SCHEMA),
        )


class WrongDateNarrativeProvider(NarrativeProvider):
    def _outcome(self, request: F009NarrativeRequest) -> F009ProviderOutcome[F009Narrative]:
        valid = super()._outcome(request).data
        assert valid is not None
        first, *rest = valid.days
        return F009ProviderOutcome(
            F009Narrative(
                days=(
                    F009NarrativeDay(
                        local_date=first.local_date + timedelta(days=1),
                        location_ids=tuple(reversed(first.location_ids)),
                        pace_note=first.pace_note,
                        stop_narratives=first.stop_narratives,
                        rationale=first.rationale,
                    ),
                    *rest,
                )
            )
        )


def option(
    location_id: UUID,
    purpose: PoiPurpose,
    longitude: float,
    latitude: float,
) -> PoiOption:
    return PoiOption(
        location_id=location_id,
        provider_place_id=f"provider-{location_id}",
        name=f"地点-{str(location_id)[-1]}",
        address="杭州",
        city_adcode="330100",
        district_adcode="330102",
        category_code="hotel" if purpose is PoiPurpose.ACCOMMODATION else "scenic_area",
        category_label="住宿" if purpose is PoiPurpose.ACCOMMODATION else "景点",
        coordinate_gcj02=Gcj02Point(longitude=longitude, latitude=latitude),
        purpose=purpose,
        scope_kind=PoiScopeKind.POINT,
        confirmation_status=PoiConfirmationStatus.VERIFIED,
    )


def create_request() -> PreplanningSessionCreateRequest:
    return PreplanningSessionCreateRequest(
        trip=PreplanningTripInput(
            city="杭州",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            travelers=2,
            total_budget=Money(amount=Decimal("3000")),
            pace=Pace.BALANCED,
            transport_modes=(TransportMode.WALKING, TransportMode.PUBLIC_TRANSIT),
            day_windows=(
                MultiDayTimeWindow(day_offset=0, start_time=time(9), end_time=time(20)),
                MultiDayTimeWindow(day_offset=1, start_time=time(9), end_time=time(20)),
            ),
        )
    )


async def selected_service(
    provider: RouteProvider,
    narrative: NarrativeProvider | None = None,
) -> PreplanningService:
    identifiers = iter((SESSION_ID, FEASIBILITY_ID, JOB_ID, TRACE_ID, PLAN_ID))
    service = PreplanningService(
        provider,
        narrative=narrative,
        id_factory=lambda: next(identifiers),
    )
    await service.create(create_request())
    await service.search(
        SESSION_ID,
        PoiSearchQuery(purpose=PoiPurpose.ACCOMMODATION, keywords="湖滨"),
    )
    await service.search(
        SESSION_ID,
        PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="杭州景点"),
    )
    await service.update_selection(
        SESSION_ID,
        PreplanningSelectionUpdate(
            expected_revision=0,
            selection=PreplanningSelection(
                accommodation=AccommodationChoice(
                    mode=AccommodationMode.EXACT_POI,
                    label="湖滨住宿",
                    confidence=AccommodationConfidence.EXACT,
                    semantic_location_id=LODGING_ID,
                    route_anchor_location_id=LODGING_ID,
                ),
                pois=tuple(
                    PoiIntent(
                        location_id=location_id,
                        route_anchor_location_id=location_id,
                        importance=PoiImportance.MUST_VISIT,
                        expected_duration_minutes=90,
                    )
                    for location_id in POI_IDS
                ),
            ),
        ),
    )
    return service


def test_preflight_builds_complete_lodging_chains_and_one_time_token() -> None:
    async def scenario() -> None:
        provider = RouteProvider()
        service = await selected_service(provider)
        result = await service.preflight(SESSION_ID, expected_revision=1)

        assert result.state is PreplanningState.FEASIBLE
        assert result.feasibility_id == FEASIBILITY_ID
        assert len(result.days) == 2
        assert result.calls.route <= 24
        for day in result.days:
            assert day.routes[0].origin_location_id == LODGING_ID
            assert day.routes[-1].destination_location_id == LODGING_ID
            assert all(
                left.destination_location_id == right.origin_location_id
                for left, right in pairwise(day.routes)
            )

    asyncio.run(scenario())


def test_provider_error_is_not_reported_as_route_unreachable() -> None:
    async def scenario() -> None:
        service = await selected_service(RouteProvider(F009ProviderFailureKind.TIMEOUT))
        result = await service.preflight(SESSION_ID, expected_revision=1)
        assert result.state is PreplanningState.PROVIDER_UNAVAILABLE
        assert {conflict.code.value for conflict in result.conflicts} == {"provider_unavailable"}

    asyncio.run(scenario())


def test_explicit_zero_route_stays_a_feasibility_conflict() -> None:
    async def scenario() -> None:
        service = await selected_service(RouteProvider(F009ProviderFailureKind.EMPTY_RESULT))
        result = await service.preflight(SESSION_ID, expected_revision=1)
        assert result.state is PreplanningState.CONFLICTED
        assert "route_unreachable" in {conflict.code.value for conflict in result.conflicts}

    asyncio.run(scenario())


def test_only_system_recommendation_can_use_verified_same_category_5km_replacement() -> None:
    async def scenario() -> None:
        provider = ReplacementRouteProvider()
        service = PreplanningService(provider, id_factory=lambda: SESSION_ID)
        await service.create(create_request())
        await service.search(
            SESSION_ID,
            PoiSearchQuery(purpose=PoiPurpose.ACCOMMODATION, keywords="湖滨"),
        )
        await service.search(
            SESSION_ID,
            PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="杭州景点"),
        )
        await service.update_selection(
            SESSION_ID,
            PreplanningSelectionUpdate(
                expected_revision=0,
                selection=PreplanningSelection(
                    accommodation=AccommodationChoice(
                        mode=AccommodationMode.EXACT_POI,
                        label="湖滨住宿",
                        confidence=AccommodationConfidence.EXACT,
                        semantic_location_id=LODGING_ID,
                        route_anchor_location_id=LODGING_ID,
                    ),
                    pois=(
                        PoiIntent(
                            location_id=POI_IDS[0],
                            route_anchor_location_id=POI_IDS[0],
                            importance=PoiImportance.MUST_VISIT,
                            expected_duration_minutes=90,
                            source=PoiSelectionSource.SYSTEM_RECOMMENDATION,
                        ),
                        PoiIntent(
                            location_id=POI_IDS[1],
                            route_anchor_location_id=POI_IDS[1],
                            importance=PoiImportance.MUST_VISIT,
                            expected_duration_minutes=90,
                        ),
                    ),
                    allow_system_recommendations=True,
                ),
            ),
        )

        result = await service.preflight(SESSION_ID, expected_revision=1)
        planned = {stop.location_id for day in result.days for stop in day.stops}

        assert result.state is PreplanningState.FEASIBLE
        assert planned == {POI_IDS[1], POI_IDS[2]}
        assert all(
            stop.source is PoiSelectionSource.SYSTEM_RECOMMENDATION
            for day in result.days
            for stop in day.stops
            if stop.location_id == POI_IDS[2]
        )
        assert result.calls.route <= 24

    asyncio.run(scenario())


def test_v5_job_preserves_frozen_ids_and_exposes_ephemeral_map() -> None:
    async def scenario() -> None:
        narrative = NarrativeProvider(valid=True)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None
        request = TripPlanRequestV5(
            request_version="5",
            client_request_id=CLIENT_ID,
            session_id=SESSION_ID,
            selection_revision=1,
            feasibility_id=preflight.feasibility_id,
            trip=session.trip,
            selection=session.selection,
        )

        created = await service.create_v5_job(request)
        repeated = await service.create_v5_job(request)
        map_plan = await service.get_map_plan(created.job_id)

        assert created == repeated
        assert created.status.value == "ready"
        assert created.plan is not None
        assert created.plan.plan_id == PLAN_ID
        assert created.job_id == JOB_ID
        assert narrative.generate_calls == 1
        assert narrative.repair_calls == 0
        assert map_plan.plan_id == PLAN_ID
        assert map_plan.coordinate_system == "gcj02"
        assert all(len(route.points) >= 2 for day in map_plan.days for route in day.routes)
        assert len(map_plan.days) == len(created.plan.days)
        for map_day, plan_day in zip(map_plan.days, created.plan.days, strict=True):
            assert map_day.local_date == plan_day.local_date
            assert tuple(marker.location_id for marker in map_day.markers) == tuple(
                stop.location_id for stop in plan_day.stops
            )
            assert tuple(route.route_id for route in map_day.routes) == tuple(
                route.route_id for route in plan_day.routes
            )
        planned_ids = {stop.location_id for day in created.plan.days for stop in day.stops}
        assert planned_ids == set(POI_IDS)

    asyncio.run(scenario())


def test_invalid_model_ids_are_repaired_once_then_downgrade_without_plan_mutation() -> None:
    async def scenario() -> None:
        narrative = NarrativeProvider(valid=False)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None
        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )

        assert created.status.value == "partial"
        assert created.plan is not None
        assert all(stop.narrative is None for day in created.plan.days for stop in day.stops)
        assert created.warnings == ("确定性计划已保留；模型说明不可用。",)
        assert len(created.errors) == 1
        assert created.errors[0].code.value == "model_output_invalid"
        assert created.errors[0].provider == "deepseek"
        assert created.errors[0].diagnostic_code == "narrative_repair_identity_invalid"
        assert created.errors[0].retryable is False
        assert narrative.generate_calls == 1
        assert narrative.repair_calls == 1
        serialized = json.dumps(created.model_dump(mode="json"), ensure_ascii=False)
        assert "prompt" not in serialized.lower()
        assert "provider_body" not in serialized.lower()
        assert "raw_output" not in serialized.lower()

    asyncio.run(scenario())


def test_narrative_only_retry_is_idempotent_and_preserves_plan_and_map_facts() -> None:
    async def scenario() -> None:
        narrative = NarrativeProvider(valid=False)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None
        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )
        assert created.status is PlanningStatus.PARTIAL
        assert created.retryable is True
        assert created.plan is not None
        original_plan = created.plan
        original_map = await service.get_map_plan(created.job_id)
        original_calls = (await service.get(SESSION_ID)).calls

        narrative.valid = True
        retry_id = UUID("60000000-0000-4000-8000-000000000030")
        retried = await service.retry_v5_narrative(
            created.job_id,
            client_request_id=retry_id,
        )
        repeated = await service.retry_v5_narrative(
            created.job_id,
            client_request_id=retry_id,
        )

        assert retried == repeated
        assert retried.status is PlanningStatus.READY
        assert retried.plan is not None
        assert retried.plan.plan_id == original_plan.plan_id
        assert tuple(day.routes for day in retried.plan.days) == tuple(
            day.routes for day in original_plan.days
        )
        assert tuple(
            (stop.location_id, stop.visit_order, stop.start_time, stop.end_time)
            for day in retried.plan.days
            for stop in day.stops
        ) == tuple(
            (stop.location_id, stop.visit_order, stop.start_time, stop.end_time)
            for day in original_plan.days
            for stop in day.stops
        )
        assert all(stop.narrative for day in retried.plan.days for stop in day.stops)
        assert await service.get_map_plan(created.job_id) == original_map
        assert (await service.get(SESSION_ID)).calls == original_calls
        assert narrative.generate_calls == 2
        assert narrative.repair_calls == 1

    asyncio.run(scenario())


def test_model_date_or_order_mutation_is_repaired_once_then_keeps_plan() -> None:
    async def scenario() -> None:
        narrative = WrongDateNarrativeProvider(valid=True)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None

        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )

        assert created.status.value == "partial"
        assert created.plan is not None
        assert tuple(day.local_date for day in created.plan.days) == tuple(
            day.local_date for day in preflight.days
        )
        assert tuple(stop.location_id for day in created.plan.days for stop in day.stops) == tuple(
            stop.location_id for day in preflight.days for stop in day.stops
        )
        assert created.errors[0].diagnostic_code == "narrative_repair_identity_invalid"
        assert narrative.generate_calls == 1
        assert narrative.repair_calls == 1

    asyncio.run(scenario())


def test_model_transport_failure_downgrades_without_spending_schema_repair() -> None:
    async def scenario() -> None:
        narrative = UnavailableNarrativeProvider()
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None

        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )

        assert created.status.value == "partial"
        assert created.plan is not None
        assert created.errors[0].diagnostic_code == "narrative_generation_provider_unavailable"
        assert created.errors[0].retryable is True
        assert narrative.generate_calls == 1
        assert narrative.repair_calls == 0

    asyncio.run(scenario())


def test_explicit_model_schema_failure_spends_the_single_repair_budget() -> None:
    async def scenario() -> None:
        narrative = SchemaFailureNarrativeProvider(valid=True)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None

        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )

        assert created.status.value == "ready"
        assert narrative.generate_calls == 1
        assert narrative.repair_calls == 1

    asyncio.run(scenario())


def test_map_plan_size_guard_degrades_geometry_before_dropping_routes() -> None:
    async def scenario() -> None:
        service = await selected_service(RouteProvider(), NarrativeProvider(valid=True))
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        session = await service.get(SESSION_ID)
        assert session.selection is not None
        assert preflight.feasibility_id is not None
        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            )
        )
        map_plan = await service.get_map_plan(created.job_id)
        large_plan = map_plan.model_copy(
            update={
                "days": tuple(
                    day.model_copy(
                        update={
                            "routes": tuple(
                                route.model_copy(update={"points": route.points * 250})
                                for route in day.routes
                            )
                        }
                    )
                    for day in map_plan.days
                )
            }
        )

        endpoint_only = _fit_map_plan_size(large_plan, max_bytes=10_000)
        dropped = _fit_map_plan_size(large_plan, max_bytes=1)

        assert all(len(route.points) == 2 for day in endpoint_only.days for route in day.routes)
        assert all(not day.routes for day in dropped.days)
        assert "完整路线摘要仍保留在列表中" in endpoint_only.warnings[-1]

    asyncio.run(scenario())


def test_complex_poi_routes_project_anchor_ids_back_to_selected_location_ids() -> None:
    async def scenario() -> None:
        lodging, semantic, anchor, lingyin = SYNTHETIC_F009_POIS[:4]
        identifiers = iter((SESSION_ID, FEASIBILITY_ID, JOB_ID, TRACE_ID, PLAN_ID))
        service = PreplanningService(
            SyntheticF009MapProvider(),
            narrative=SyntheticF009NarrativeProvider(),
            id_factory=lambda: next(identifiers),
        )
        await service.create(create_request())
        for purpose, keywords in (
            (PoiPurpose.ACCOMMODATION, "湖滨"),
            (PoiPurpose.VISIT, "西湖"),
            (PoiPurpose.VISIT, "入口"),
            (PoiPurpose.VISIT, "灵隐寺"),
        ):
            await service.search(
                SESSION_ID,
                PoiSearchQuery(purpose=purpose, keywords=keywords),
            )
        selection = PreplanningSelection(
            accommodation=AccommodationChoice(
                mode=AccommodationMode.EXACT_POI,
                label=lodging.name,
                confidence=AccommodationConfidence.EXACT,
                semantic_location_id=lodging.location_id,
                route_anchor_location_id=lodging.location_id,
            ),
            pois=(
                PoiIntent(
                    location_id=semantic.location_id,
                    route_anchor_location_id=anchor.location_id,
                    importance=PoiImportance.MUST_VISIT,
                    expected_duration_minutes=90,
                ),
                PoiIntent(
                    location_id=lingyin.location_id,
                    route_anchor_location_id=lingyin.location_id,
                    importance=PoiImportance.MUST_VISIT,
                    expected_duration_minutes=90,
                ),
            ),
        )
        await service.update_selection(
            SESSION_ID,
            PreplanningSelectionUpdate(expected_revision=0, selection=selection),
        )
        preflight = await service.preflight(SESSION_ID, expected_revision=1)
        assert preflight.feasibility_id is not None
        created = await service.create_v5_job(
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=create_request().trip,
                selection=selection,
            )
        )
        map_plan = await service.get_map_plan(JOB_ID)
        assert created.plan is not None
        visible_ids = {lodging.location_id, semantic.location_id, lingyin.location_id}
        route_endpoint_ids = {
            endpoint
            for day in created.plan.days
            for route in day.routes
            for endpoint in (route.origin_location_id, route.destination_location_id)
        }
        map_endpoint_ids = {
            endpoint
            for day in map_plan.days
            for route in day.routes
            for endpoint in (route.origin_location_id, route.destination_location_id)
        }
        assert route_endpoint_ids <= visible_ids
        assert map_endpoint_ids == route_endpoint_ids
        assert semantic.location_id in route_endpoint_ids
        assert anchor.location_id not in route_endpoint_ids

    asyncio.run(scenario())


def test_v6_offers_distinct_feasible_options_and_preserves_selected_facts() -> None:
    async def scenario() -> None:
        provider = RouteProvider()
        narrative = NarrativeProvider(valid=True)
        service = PreplanningService(provider, narrative=narrative)
        created_session = await service.create(create_request())
        await service.search(
            created_session.session_id,
            PoiSearchQuery(purpose=PoiPurpose.ACCOMMODATION, keywords="湖滨"),
        )
        await service.search(
            created_session.session_id,
            PoiSearchQuery(purpose=PoiPurpose.VISIT, keywords="杭州景点"),
        )
        selection = PreplanningSelection(
            accommodation=AccommodationChoice(
                mode=AccommodationMode.EXACT_POI,
                label="湖滨住宿",
                confidence=AccommodationConfidence.EXACT,
                semantic_location_id=LODGING_ID,
                route_anchor_location_id=LODGING_ID,
            ),
            pois=tuple(
                PoiIntent(
                    location_id=location_id,
                    route_anchor_location_id=location_id,
                    importance=PoiImportance.MUST_VISIT,
                    expected_duration_minutes=90,
                    preferred_day=index % 2,
                )
                for index, location_id in enumerate(POI_IDS)
            ),
        )
        session = await service.update_selection(
            created_session.session_id,
            PreplanningSelectionUpdate(expected_revision=0, selection=selection),
        )

        preflight = await service.preflight_v6(
            session.session_id, expected_revision=session.revision
        )

        assert preflight.state is PreplanningState.FEASIBLE
        assert preflight.feasibility_set_id is not None
        assert 1 <= len(preflight.options) <= 3
        assert len({option.kind for option in preflight.options}) == len(preflight.options)
        schedules = {
            tuple(stop.location_id for day in option.days for stop in day.stops)
            for option in preflight.options
        }
        assert len(schedules) == len(preflight.options)
        assert all(
            {stop.location_id for day in option.days for stop in day.stops} == set(POI_IDS)
            for option in preflight.options
        )
        assert all(option.weather_message == "天气尚不可核验" for option in preflight.options)

        chosen = preflight.options[-1]
        result = await service.create_v6_job(
            TripPlanRequestV6(
                request_version="6",
                client_request_id=CLIENT_ID,
                session_id=session.session_id,
                selection_revision=session.revision,
                feasibility_set_id=preflight.feasibility_set_id,
                option_id=chosen.option_id,
                trip=session.trip,
                selection=selection,
            )
        )
        map_plan = await service.get_map_plan(result.job_id)

        assert result.status is PlanningStatus.READY
        assert result.plan is not None
        assert result.plan.plan_format_version == "6"
        assert result.plan.selected_option_id == chosen.option_id
        assert result.plan.option_kind == chosen.kind
        assert tuple(
            (stop.location_id, stop.start_time, stop.end_time)
            for day in result.plan.days
            for stop in day.stops
        ) == tuple(
            (stop.location_id, stop.start_time, stop.end_time)
            for day in chosen.days
            for stop in day.stops
        )
        assert map_plan.plan_id == result.plan.plan_id
        assert provider.route_calls <= 24
        assert narrative.generate_calls == 1

    asyncio.run(scenario())
