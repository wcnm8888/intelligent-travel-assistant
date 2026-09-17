from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from intelligent_travel_assistant.contracts.f009 import (
    AccommodationChoice,
    AccommodationConfidence,
    AccommodationMode,
    Gcj02Point,
    NarrativeRetryRequestV5,
    PoiConfirmationStatus,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PoiPurpose,
    PoiScopeKind,
    PoiSelectionSource,
    PreplanningSelection,
    PreplanningTripInput,
    TripPlanRequestV5,
)
from intelligent_travel_assistant.contracts.trip_planning import (
    Money,
    MultiDayTimeWindow,
    Pace,
    TransportMode,
)

SESSION_ID = UUID("10000000-0000-4000-8000-000000000001")
FEASIBILITY_ID = UUID("10000000-0000-4000-8000-000000000002")
LODGING_ID = UUID("10000000-0000-4000-8000-000000000003")
WEST_LAKE_ID = UUID("10000000-0000-4000-8000-000000000004")
LINGYIN_ID = UUID("10000000-0000-4000-8000-000000000005")
FEILAI_ID = UUID("10000000-0000-4000-8000-000000000006")


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


def accommodation() -> AccommodationChoice:
    return AccommodationChoice(
        mode=AccommodationMode.AREA,
        label="湖滨/龙翔桥一带",
        confidence=AccommodationConfidence.AREA_ESTIMATE,
        semantic_location_id=None,
        route_anchor_location_id=LODGING_ID,
    )


def poi(location_id: UUID, *, visit_group_id: str | None = None) -> PoiIntent:
    return PoiIntent(
        location_id=location_id,
        route_anchor_location_id=location_id,
        importance=PoiImportance.MUST_VISIT,
        visit_group_id=visit_group_id,
        preferred_day=None,
        expected_duration_minutes=120,
        omission_allowed=False,
        source=PoiSelectionSource.USER_SELECTED,
    )


def test_v5_accepts_confirmed_area_and_visit_group() -> None:
    selection = PreplanningSelection(
        accommodation=accommodation(),
        pois=(
            poi(WEST_LAKE_ID),
            poi(LINGYIN_ID, visit_group_id="lingyin-complex"),
            poi(FEILAI_ID, visit_group_id="lingyin-complex"),
        ),
        allow_system_recommendations=False,
    )
    request = TripPlanRequestV5(
        request_version="5",
        client_request_id=UUID("10000000-0000-4000-8000-000000000007"),
        session_id=SESSION_ID,
        selection_revision=2,
        feasibility_id=FEASIBILITY_ID,
        trip=trip(),
        selection=selection,
    )

    assert request.request_version == "5"
    assert len(request.selection.pois) == 3
    assert request.selection.allow_system_recommendations is False


def test_narrative_retry_request_is_strict_and_v5_only() -> None:
    request = NarrativeRetryRequestV5(
        request_version="5",
        client_request_id=UUID("10000000-0000-4000-8000-000000000008"),
    )
    assert request.request_version == "5"
    with pytest.raises(ValidationError):
        NarrativeRetryRequestV5.model_validate(
            {
                **request.model_dump(mode="json"),
                "unexpected": "not-allowed",
            }
        )


@pytest.mark.parametrize("field", ["mode", "confidence"])
def test_accommodation_mode_and_confidence_must_match(field: str) -> None:
    values = accommodation().model_dump()
    values[field] = "exact" if field == "confidence" else "exact_poi"
    with pytest.raises(ValidationError):
        AccommodationChoice.model_validate(values)


def test_visit_group_requires_at_least_two_members() -> None:
    with pytest.raises(ValidationError):
        PreplanningSelection(
            accommodation=accommodation(),
            pois=(poi(LINGYIN_ID, visit_group_id="single"),),
        )


def test_poi_cannot_belong_to_both_group_kinds() -> None:
    values = poi(LINGYIN_ID).model_dump()
    values.update(either_or_group_id="choice", visit_group_id="combined")
    with pytest.raises(ValidationError):
        PoiIntent.model_validate(values)


def test_optional_omission_is_explicit() -> None:
    item = poi(WEST_LAKE_ID).model_copy(
        update={"importance": PoiImportance.OPTIONAL, "omission_allowed": False}
    )
    assert item.omission_allowed is False


def test_poi_option_keeps_provider_identity_and_gcj02_coordinate() -> None:
    option = PoiOption(
        location_id=WEST_LAKE_ID,
        provider="amap",
        provider_place_id="B0FFFAKE001",
        name="西湖风景名胜区",
        address="浙江省杭州市西湖区",
        city_adcode="330100",
        district_adcode="330106",
        category_code="scenic_area",
        category_label="风景名胜",
        coordinate_gcj02=Gcj02Point(longitude=120.1302, latitude=30.2596),
        purpose=PoiPurpose.VISIT,
        scope_kind=PoiScopeKind.COMPLEX,
        confirmation_status=PoiConfirmationStatus.REPRESENTATIVE_REQUIRED,
    )
    assert option.provider_place_id == "B0FFFAKE001"
    assert option.coordinate_gcj02.longitude == 120.1302


def test_selection_rejects_duplicate_locations_and_more_than_eight() -> None:
    duplicate = poi(WEST_LAKE_ID)
    with pytest.raises(ValidationError):
        PreplanningSelection(
            accommodation=accommodation(),
            pois=(duplicate, duplicate),
        )


def test_trip_requires_two_to_seven_exact_day_windows() -> None:
    values = trip().model_dump()
    values["end_date"] = date(2026, 10, 8)
    with pytest.raises(ValidationError):
        PreplanningTripInput.model_validate(values)
