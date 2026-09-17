from __future__ import annotations

import asyncio
from datetime import date, time
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from tests.application.test_f009_preflight import (
    CLIENT_ID,
    NarrativeProvider,
    RouteProvider,
    selected_service,
)
from tests.application.test_f009_preflight import (
    SESSION_ID as V5_SESSION_ID,
)

from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.app import create_app
from intelligent_travel_assistant.application.f009 import (
    F009CityFact,
    F009MapPinFact,
    F009PoiQuery,
    F009ProviderOutcome,
    F009RouteFact,
    F009RouteQuery,
    PreplanningService,
)
from intelligent_travel_assistant.contracts.f009 import (
    Gcj02Point,
    PoiConfirmationStatus,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
    TripPlanRequestV5,
)

SESSION_ID = UUID("30000000-0000-4000-8000-000000000001")
LODGING_ID = UUID("30000000-0000-4000-8000-000000000002")
WEST_LAKE_ID = UUID("30000000-0000-4000-8000-000000000003")


class FakeProvider:
    def __init__(self) -> None:
        self.search_calls = 0

    async def resolve_city(self, city: str) -> F009ProviderOutcome[F009CityFact]:
        assert city == "杭州"
        return F009ProviderOutcome(F009CityFact("杭州市", "330100", "0571", None))

    async def search_pois(self, query: F009PoiQuery) -> F009ProviderOutcome[tuple[PoiOption, ...]]:
        self.search_calls += 1
        location_id = LODGING_ID if query.purpose is PoiPurpose.ACCOMMODATION else WEST_LAKE_ID
        return F009ProviderOutcome(
            (
                PoiOption(
                    location_id=location_id,
                    provider_place_id=f"provider-{location_id}",
                    name="龙翔桥" if query.purpose is PoiPurpose.ACCOMMODATION else "西湖",
                    address="杭州市上城区",
                    city_adcode="330100",
                    district_adcode="330102",
                    category_code=(
                        "hotel" if query.purpose is PoiPurpose.ACCOMMODATION else "scenic_area"
                    ),
                    category_label=(
                        "住宿" if query.purpose is PoiPurpose.ACCOMMODATION else "风景名胜"
                    ),
                    coordinate_gcj02=Gcj02Point(longitude=120.16, latitude=30.25),
                    purpose=query.purpose,
                    scope_kind=PoiScopeKind.POINT,
                    confirmation_status=PoiConfirmationStatus.VERIFIED,
                ),
            )
        )

    async def reverse_geocode(self, coordinate: Gcj02Point) -> F009ProviderOutcome[F009MapPinFact]:
        return F009ProviderOutcome(F009MapPinFact("湖滨锚点", "330100", "330102", coordinate))

    async def calculate_route(self, query: F009RouteQuery) -> F009ProviderOutcome[F009RouteFact]:
        raise AssertionError(f"route not expected: {query}")


def create_payload() -> dict[str, object]:
    return {
        "session_version": "1",
        "trip": {
            "city": "杭州",
            "start_date": date(2026, 10, 1).isoformat(),
            "end_date": date(2026, 10, 2).isoformat(),
            "travelers": 2,
            "total_budget": {"amount": str(Decimal("3000")), "currency": "CNY"},
            "preferences": {"interests": [], "free_text": "", "hard_constraints": []},
            "pace": "balanced",
            "transport_modes": ["public_transit", "walking"],
            "day_windows": [
                {
                    "day_offset": 0,
                    "start_time": time(9).isoformat(),
                    "end_time": time(20).isoformat(),
                },
                {
                    "day_offset": 1,
                    "start_time": time(9).isoformat(),
                    "end_time": time(20).isoformat(),
                },
            ],
        },
    }


def test_preplanning_api_create_search_cache_selection_and_delete() -> None:
    provider = FakeProvider()
    service = PreplanningService(provider, id_factory=lambda: SESSION_ID)
    application = create_app(
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=service,
    )

    with TestClient(application) as client:
        created = client.post("/api/preplanning-sessions", json=create_payload())
        first = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "accommodation", "keywords": "龙翔桥"},
        )
        repeated = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "accommodation", "keywords": "龙翔桥"},
        )
        visit = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "visit", "keywords": "西湖"},
        )
        updated = client.put(
            f"/api/preplanning-sessions/{SESSION_ID}/selection",
            json={
                "expected_revision": 0,
                "selection": {
                    "accommodation": {
                        "mode": "exact_poi",
                        "label": "龙翔桥",
                        "confidence": "exact",
                        "semantic_location_id": str(LODGING_ID),
                        "route_anchor_location_id": str(LODGING_ID),
                    },
                    "pois": [
                        {
                            "location_id": str(WEST_LAKE_ID),
                            "route_anchor_location_id": str(WEST_LAKE_ID),
                            "importance": "must_visit",
                            "expected_duration_minutes": 120,
                        }
                    ],
                    "allow_system_recommendations": False,
                },
            },
        )
        stale = client.put(
            f"/api/preplanning-sessions/{SESSION_ID}/selection",
            json={"expected_revision": 0, "selection": updated.json()["selection"]},
        )
        trip_payload = create_payload()["trip"]
        assert isinstance(trip_payload, dict)
        trip_payload["travelers"] = 3
        trip_updated = client.put(
            f"/api/preplanning-sessions/{SESSION_ID}/trip",
            json={"expected_revision": 1, "trip": trip_payload},
        )
        deleted = client.delete(f"/api/preplanning-sessions/{SESSION_ID}")
        missing = client.get(f"/api/preplanning-sessions/{SESSION_ID}")

    assert created.status_code == 201
    assert created.headers["location"].endswith(str(SESSION_ID))
    assert first.status_code == repeated.status_code == visit.status_code == 200
    assert provider.search_calls == 2
    assert repeated.json()["calls"]["poi_search"] == 1
    assert updated.status_code == 200
    assert updated.json()["revision"] == 1
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "selection_revision_conflict"
    assert trip_updated.status_code == 200
    assert trip_updated.json()["revision"] == 2
    assert trip_updated.json()["trip"]["travelers"] == 3
    assert deleted.status_code == 204
    assert missing.status_code == 404


def test_preplanning_api_rejects_out_of_contract_paging_and_center() -> None:
    application = create_app(
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=PreplanningService(FakeProvider(), id_factory=lambda: SESSION_ID),
    )
    with TestClient(application) as client:
        client.post("/api/preplanning-sessions", json=create_payload())
        oversized = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "visit", "keywords": "西湖", "page_size": 21},
        )
        bad_center = client.get(
            f"/api/preplanning-sessions/{SESSION_ID}/pois",
            params={"purpose": "visit", "keywords": "西湖", "center": "120.1"},
        )

    assert oversized.status_code == 422
    assert bad_center.status_code == 422
    assert oversized.json()["error"]["code"] == "input_invalid"
    assert bad_center.json()["error"]["code"] == "input_invalid"


def test_v5_same_uri_job_map_and_retry_contract_remain_memory_only() -> None:
    async def prepare() -> tuple[PreplanningService, TripPlanRequestV5]:
        service = await selected_service(RouteProvider(), NarrativeProvider(valid=True))
        preflight = await service.preflight(V5_SESSION_ID, expected_revision=1)
        session = await service.get(V5_SESSION_ID)
        assert preflight.feasibility_id is not None
        assert session.selection is not None
        return service, TripPlanRequestV5(
            request_version="5",
            client_request_id=CLIENT_ID,
            session_id=V5_SESSION_ID,
            selection_revision=1,
            feasibility_id=preflight.feasibility_id,
            trip=session.trip,
            selection=session.selection,
        )

    service, request = asyncio.run(prepare())
    application = create_app(
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=service,
    )
    with TestClient(application) as client:
        created = client.post(
            "/api/trip-plans",
            json=request.model_dump(mode="json"),
        )
        job_id = created.json()["job_id"]
        fetched = client.get(f"/api/trip-plans/{job_id}")
        mapped = client.get(f"/api/trip-plans/{job_id}/map")
        plan = created.json()["plan"]
        replan = client.post(
            f"/api/trip-plans/{job_id}/replans",
            json={
                "replan_request_id": "60000000-0000-4000-8000-000000000020",
                "baseline_plan_id": plan["plan_id"],
                "command": {
                    "operation": "adjust_activity_time",
                    "target_activity_id": plan["days"][0]["stops"][0]["location_id"],
                    "start_time": "10:30:00",
                    "end_time": "12:00:00",
                    "reason_code": "user_schedule_preference",
                },
            },
        )
        retry = client.post(f"/api/trip-plans/{job_id}/retry")

    assert created.status_code == 202
    assert created.json()["response_version"] == "5"
    assert created.json() == fetched.json()
    assert mapped.status_code == 200
    assert mapped.json()["coordinate_system"] == "gcj02"
    assert replan.status_code == 422
    assert replan.json()["error"]["code"] == "replan_scope_not_supported"
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "retry_not_allowed"


def test_v5_narrative_retry_action_updates_only_narrative_and_is_idempotent() -> None:
    async def prepare() -> tuple[PreplanningService, TripPlanRequestV5, NarrativeProvider]:
        narrative = NarrativeProvider(valid=False)
        service = await selected_service(RouteProvider(), narrative)
        preflight = await service.preflight(V5_SESSION_ID, expected_revision=1)
        session = await service.get(V5_SESSION_ID)
        assert preflight.feasibility_id is not None
        assert session.selection is not None
        return (
            service,
            TripPlanRequestV5(
                request_version="5",
                client_request_id=CLIENT_ID,
                session_id=V5_SESSION_ID,
                selection_revision=1,
                feasibility_id=preflight.feasibility_id,
                trip=session.trip,
                selection=session.selection,
            ),
            narrative,
        )

    service, request, narrative = asyncio.run(prepare())
    application = create_app(
        planning_job_repository=InMemoryPlanningJobRepository(),
        preplanning_service=service,
    )
    retry_id = "60000000-0000-4000-8000-000000000031"
    with TestClient(application) as client:
        created = client.post("/api/trip-plans", json=request.model_dump(mode="json"))
        assert created.json()["status"] == "partial"
        original_plan = created.json()["plan"]
        job_id = created.json()["job_id"]
        original_map = client.get(f"/api/trip-plans/{job_id}/map").json()
        narrative.valid = True
        payload = {"request_version": "5", "client_request_id": retry_id}
        retried = client.post(
            f"/api/trip-plans/{job_id}/narrative-retries",
            json=payload,
        )
        repeated = client.post(
            f"/api/trip-plans/{job_id}/narrative-retries",
            json=payload,
        )
        current_map = client.get(f"/api/trip-plans/{job_id}/map").json()

    assert retried.status_code == 200
    assert retried.json() == repeated.json()
    assert retried.json()["status"] == "ready"
    assert retried.json()["plan"]["plan_id"] == original_plan["plan_id"]
    assert retried.json()["plan"]["days"][0]["routes"] == original_plan["days"][0]["routes"]
    assert current_map == original_map
    assert narrative.generate_calls == 2
    assert narrative.repair_calls == 1
