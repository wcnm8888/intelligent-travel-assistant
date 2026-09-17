from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import UUID

from intelligent_travel_assistant.application.f009.ports import F009RouteFact
from intelligent_travel_assistant.application.f009.solver import (
    enumerate_schedule_candidates,
    haversine_meters,
    validate_route_fact,
)
from intelligent_travel_assistant.contracts.f009 import (
    AccommodationChoice,
    AccommodationConfidence,
    AccommodationMode,
    FeasibilityConflictCode,
    Gcj02Point,
    PoiConfirmationStatus,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
    PreplanningSelection,
    PreplanningTripInput,
)
from intelligent_travel_assistant.contracts.trip_planning import (
    Money,
    MultiDayTimeWindow,
    Pace,
    TransportMode,
)

LODGING = UUID("50000000-0000-4000-8000-000000000001")
LINGYIN = UUID("50000000-0000-4000-8000-000000000002")
FEILAI = UUID("50000000-0000-4000-8000-000000000003")
HEFANG = UUID("50000000-0000-4000-8000-000000000004")
SOUTHERN_SONG = UUID("50000000-0000-4000-8000-000000000005")


def option(location_id: UUID, longitude: float, latitude: float) -> PoiOption:
    return PoiOption(
        location_id=location_id,
        provider_place_id=str(location_id),
        name=str(location_id)[-4:],
        address="杭州",
        city_adcode="330100",
        district_adcode="330106",
        category_code="hotel" if location_id == LODGING else "scenic_area",
        category_label="住宿" if location_id == LODGING else "景点",
        coordinate_gcj02=Gcj02Point(longitude=longitude, latitude=latitude),
        purpose=PoiPurpose.ACCOMMODATION if location_id == LODGING else PoiPurpose.VISIT,
        scope_kind=PoiScopeKind.POINT,
        confirmation_status=PoiConfirmationStatus.VERIFIED,
    )


def trip() -> PreplanningTripInput:
    return PreplanningTripInput(
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


def test_solver_is_deterministic_keeps_visit_group_and_selects_one_either_or() -> None:
    options = {
        LODGING: option(LODGING, 120.16, 30.25),
        LINGYIN: option(LINGYIN, 120.10, 30.24),
        FEILAI: option(FEILAI, 120.11, 30.24),
        HEFANG: option(HEFANG, 120.17, 30.24),
        SOUTHERN_SONG: option(SOUTHERN_SONG, 120.18, 30.24),
    }
    selection = PreplanningSelection(
        accommodation=AccommodationChoice(
            mode=AccommodationMode.EXACT_POI,
            label="湖滨住宿",
            confidence=AccommodationConfidence.EXACT,
            semantic_location_id=LODGING,
            route_anchor_location_id=LODGING,
        ),
        pois=(
            PoiIntent(
                location_id=LINGYIN,
                route_anchor_location_id=LINGYIN,
                importance=PoiImportance.MUST_VISIT,
                visit_group_id="temple",
            ),
            PoiIntent(
                location_id=FEILAI,
                route_anchor_location_id=FEILAI,
                importance=PoiImportance.MUST_VISIT,
                visit_group_id="temple",
            ),
            PoiIntent(
                location_id=HEFANG,
                route_anchor_location_id=HEFANG,
                importance=PoiImportance.MUST_VISIT,
                either_or_group_id="street",
            ),
            PoiIntent(
                location_id=SOUTHERN_SONG,
                route_anchor_location_id=SOUTHERN_SONG,
                importance=PoiImportance.MUST_VISIT,
                either_or_group_id="street",
            ),
        ),
    )

    first = enumerate_schedule_candidates(trip=trip(), selection=selection, options=options)
    second = enumerate_schedule_candidates(trip=trip(), selection=selection, options=options)

    assert first == second
    assert len(first) == 3
    for candidate in first:
        flattened = [intent for day in candidate.days for intent in day.intents]
        ids = {intent.location_id for intent in flattened}
        assert {LINGYIN, FEILAI} <= ids
        assert len(ids & {HEFANG, SOUTHERN_SONG}) == 1
        temple_day = next(
            day
            for day in candidate.days
            if any(item.location_id == LINGYIN for item in day.intents)
        )
        positions = [
            index
            for index, item in enumerate(temple_day.intents)
            if item.location_id in {LINGYIN, FEILAI}
        ]
        assert positions[1] == positions[0] + 1


def test_three_independent_required_locations_are_all_retained() -> None:
    options = {
        LODGING: option(LODGING, 120.16, 30.25),
        LINGYIN: option(LINGYIN, 120.10, 30.24),
        FEILAI: option(FEILAI, 120.11, 30.24),
        HEFANG: option(HEFANG, 120.17, 30.24),
    }
    selection = PreplanningSelection(
        accommodation=AccommodationChoice(
            mode=AccommodationMode.EXACT_POI,
            label="湖滨住宿",
            confidence=AccommodationConfidence.EXACT,
            semantic_location_id=LODGING,
            route_anchor_location_id=LODGING,
        ),
        pois=tuple(
            PoiIntent(
                location_id=location_id,
                route_anchor_location_id=location_id,
                importance=PoiImportance.MUST_VISIT,
            )
            for location_id in (LINGYIN, FEILAI, HEFANG)
        ),
    )

    candidates = enumerate_schedule_candidates(trip=trip(), selection=selection, options=options)

    assert candidates
    for candidate in candidates:
        assert {intent.location_id for day in candidate.days for intent in day.intents} == {
            LINGYIN,
            FEILAI,
            HEFANG,
        }
        assert candidate.omitted_location_ids == ()


def test_route_validation_rejects_endpoint_and_implausible_ratio() -> None:
    origin = Gcj02Point(longitude=120.16, latitude=30.25)
    destination = Gcj02Point(longitude=120.17, latitude=30.26)
    assert 1_000 < haversine_meters(origin, destination) < 2_000

    endpoint = validate_route_fact(
        origin=origin,
        destination=destination,
        mode=TransportMode.PUBLIC_TRANSIT,
        fact=F009RouteFact(
            distance_meters=2_000,
            duration_minutes=20,
            points=(
                Gcj02Point(longitude=121.0, latitude=31.0),
                destination,
            ),
        ),
    )
    ratio = validate_route_fact(
        origin=origin,
        destination=destination,
        mode=TransportMode.PUBLIC_TRANSIT,
        fact=F009RouteFact(
            distance_meters=30_000,
            duration_minutes=60,
            points=(origin, destination),
        ),
    )

    assert endpoint.code is FeasibilityConflictCode.ROUTE_ENDPOINT_MISMATCH
    assert ratio.code is FeasibilityConflictCode.IMPLAUSIBLE_ROUTE_RATIO
