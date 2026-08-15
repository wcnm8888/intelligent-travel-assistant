"""Pure domain invariants shared by later F-001 validators."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    Coordinates,
    CoordinateSystem,
    CostConfidence,
    CostEntry,
    DomainInvariantError,
    Location,
    Money,
    PlanDayStructure,
    PlanStructure,
    Provider,
    RouteLeg,
    RouteMode,
    SourceCatalog,
    SourceRecord,
    WeatherForecast,
)

SOURCE_ID = UUID("10000000-0000-4000-8000-000000000001")
HOTEL_ID = UUID("20000000-0000-4000-8000-000000000001")
POI_ID = UUID("20000000-0000-4000-8000-000000000002")
UNKNOWN_ID = UUID("20000000-0000-4000-8000-000000000099")


def source() -> SourceRecord:
    return SourceRecord(
        source_id=SOURCE_ID,
        provider=Provider.AMAP,
        source_type="synthetic_poi",
        fetched_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
        valid_until=None,
    )


def hotel() -> Location:
    return Location(
        location_id=HOTEL_ID,
        name="住宿锚点",
        category="accommodation_anchor",
        city_adcode="330100",
        coordinates=None,
        source_ids=(SOURCE_ID,),
    )


def poi() -> Location:
    return Location(
        location_id=POI_ID,
        name="synthetic POI",
        category="scenic_area",
        city_adcode="330100",
        coordinates=Coordinates(
            longitude=Decimal("120.15"),
            latitude=Decimal("30.25"),
            coordinate_system=CoordinateSystem.PROVIDER_NATIVE,
        ),
        source_ids=(SOURCE_ID,),
    )


@pytest.mark.parametrize("amount", [Decimal("-0.01"), Decimal("1.001")])
def test_money_rejects_negative_or_over_precise_amounts(amount: Decimal) -> None:
    with pytest.raises(DomainInvariantError):
        Money(amount=amount)


def test_money_rejects_binary_float_and_non_cny_currency() -> None:
    with pytest.raises(DomainInvariantError):
        Money(amount=100.0)  # type: ignore[arg-type]

    with pytest.raises(DomainInvariantError):
        Money(amount=Decimal("100.00"), currency="USD")  # type: ignore[arg-type]


def test_unknown_cost_has_no_amount_and_known_cost_has_an_amount() -> None:
    unknown = CostEntry(confidence=CostConfidence.UNKNOWN, amount=None)
    assert unknown.amount is None

    with pytest.raises(DomainInvariantError):
        CostEntry(
            confidence=CostConfidence.UNKNOWN,
            amount=Money(Decimal("0.00")),
        )

    with pytest.raises(DomainInvariantError):
        CostEntry(confidence=CostConfidence.ESTIMATED, amount=None)


def test_verified_cost_requires_at_least_one_source() -> None:
    with pytest.raises(DomainInvariantError):
        CostEntry(
            confidence=CostConfidence.VERIFIED,
            amount=Money(Decimal("80.00")),
            source_ids=(),
        )


def test_source_references_must_not_repeat() -> None:
    with pytest.raises(DomainInvariantError):
        CostEntry(
            confidence=CostConfidence.ESTIMATED,
            amount=Money(Decimal("10.00")),
            source_ids=(SOURCE_ID, SOURCE_ID),
        )


def test_source_requires_timezone_and_validity_cannot_precede_fetch() -> None:
    with pytest.raises(DomainInvariantError):
        SourceRecord(
            source_id=SOURCE_ID,
            provider=Provider.AMAP,
            source_type="poi",
            fetched_at=datetime(2026, 8, 13, 10, 0),
            valid_until=None,
        )

    with pytest.raises(DomainInvariantError):
        SourceRecord(
            source_id=SOURCE_ID,
            provider=Provider.AMAP,
            source_type="poi",
            fetched_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
            valid_until=datetime(2026, 8, 13, 9, 59, tzinfo=UTC),
        )


def test_source_catalog_rejects_duplicate_ids_and_missing_references() -> None:
    with pytest.raises(DomainInvariantError):
        SourceCatalog((source(), source()))

    catalog = SourceCatalog((source(),))
    catalog.require_all((SOURCE_ID,))
    with pytest.raises(DomainInvariantError):
        catalog.require_all((UUID("10000000-0000-4000-8000-000000000099"),))


@pytest.mark.parametrize(
    ("longitude", "latitude"),
    [
        (Decimal("180.01"), Decimal("30")),
        (Decimal("120"), Decimal("90.01")),
    ],
)
def test_coordinates_stay_inside_geographic_bounds(longitude: Decimal, latitude: Decimal) -> None:
    with pytest.raises(DomainInvariantError):
        Coordinates(
            longitude=longitude,
            latitude=latitude,
            coordinate_system=CoordinateSystem.UNKNOWN,
        )


def test_location_requires_valid_adcode_and_source() -> None:
    with pytest.raises(DomainInvariantError):
        Location(
            location_id=POI_ID,
            name="POI",
            category="scenic_area",
            city_adcode="3301",
            coordinates=None,
            source_ids=(SOURCE_ID,),
        )

    with pytest.raises(DomainInvariantError):
        Location(
            location_id=POI_ID,
            name="POI",
            category="scenic_area",
            city_adcode="330100",
            coordinates=None,
            source_ids=(),
        )


def test_route_requires_distinct_endpoints() -> None:
    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=HOTEL_ID,
            mode=RouteMode.WALKING,
            distance_meters=100,
            duration_minutes=5,
            source_ids=(SOURCE_ID,),
        )


def test_route_requires_non_negative_distance() -> None:
    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters=-1,
            duration_minutes=5,
            source_ids=(SOURCE_ID,),
        )

    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters="100",  # type: ignore[arg-type]
            duration_minutes=5,
            source_ids=(SOURCE_ID,),
        )


def test_route_requires_positive_duration() -> None:
    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters=100,
            duration_minutes=0,
            source_ids=(SOURCE_ID,),
        )

    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters=100,
            duration_minutes=True,
            source_ids=(SOURCE_ID,),
        )


@pytest.mark.parametrize(
    ("distance_meters", "duration_minutes", "expected_code"),
    [
        (2_147_483_648, 5, "route_distance_invalid"),
        (100, 1441, "route_duration_invalid"),
    ],
)
def test_route_rejects_values_above_the_frozen_public_safety_bounds(
    distance_meters: int,
    duration_minutes: int,
    expected_code: str,
) -> None:
    with pytest.raises(DomainInvariantError) as raised:
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters=distance_meters,
            duration_minutes=duration_minutes,
            source_ids=(SOURCE_ID,),
        )

    assert raised.value.code == expected_code


def test_route_requires_a_source() -> None:
    with pytest.raises(DomainInvariantError):
        RouteLeg(
            origin_location_id=HOTEL_ID,
            destination_location_id=POI_ID,
            mode=RouteMode.WALKING,
            distance_meters=100,
            duration_minutes=5,
            source_ids=(),
        )


def test_weather_requires_ordered_temperatures_and_source() -> None:
    with pytest.raises(DomainInvariantError):
        WeatherForecast(
            forecast_date=date(2026, 8, 15),
            location_id=POI_ID,
            temperature_min_celsius=Decimal("35"),
            temperature_max_celsius=Decimal("30"),
            source_ids=(SOURCE_ID,),
        )

    with pytest.raises(DomainInvariantError):
        WeatherForecast(
            forecast_date=date(2026, 8, 15),
            location_id=POI_ID,
            temperature_min_celsius=Decimal("25"),
            temperature_max_celsius=Decimal("30"),
            source_ids=(),
        )


def test_plan_structure_rejects_duplicate_locations_and_dangling_references() -> None:
    with pytest.raises(DomainInvariantError):
        PlanStructure(
            city_adcode="330100",
            locations=(hotel(), hotel()),
            days=(
                PlanDayStructure(
                    local_date=date(2026, 8, 15),
                    accommodation_location_id=HOTEL_ID,
                ),
            ),
        )

    with pytest.raises(DomainInvariantError):
        PlanStructure(
            city_adcode="330100",
            locations=(hotel(), poi()),
            days=(
                PlanDayStructure(
                    local_date=date(2026, 8, 15),
                    accommodation_location_id=UNKNOWN_ID,
                    activity_location_ids=(POI_ID,),
                ),
            ),
        )


def test_plan_structure_rejects_cross_city_locations_and_route_references() -> None:
    cross_city = Location(
        location_id=UNKNOWN_ID,
        name="其他城市 POI",
        category="scenic_area",
        city_adcode="310100",
        coordinates=None,
        source_ids=(SOURCE_ID,),
    )
    route = RouteLeg(
        origin_location_id=HOTEL_ID,
        destination_location_id=UNKNOWN_ID,
        mode=RouteMode.PUBLIC_TRANSIT,
        distance_meters=1000,
        duration_minutes=20,
        source_ids=(SOURCE_ID,),
    )

    with pytest.raises(DomainInvariantError):
        PlanStructure(
            city_adcode="330100",
            locations=(hotel(), cross_city),
            days=(
                PlanDayStructure(
                    local_date=date(2026, 8, 15),
                    accommodation_location_id=HOTEL_ID,
                    route_legs=(route,),
                ),
            ),
        )
