"""Framework-free values and structural invariants for F-001.

This module contains shared values only. Date-window, schedule-overlap,
route-chain, and budget-aggregation rules live in focused sibling modules.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal
from uuid import UUID

_ADCODE: Final = re.compile(r"^\d{6}$")
MAX_ROUTE_DISTANCE_METERS: Final = 2_147_483_647
MAX_ROUTE_DURATION_MINUTES: Final = 1440


class DomainInvariantError(ValueError):
    """Stable failure raised when a pure domain invariant is violated."""

    def __init__(self, code: str, *, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f"{code}: {field}")


class Provider(StrEnum):
    DEEPSEEK = "deepseek"
    AMAP = "amap"
    QWEATHER = "qweather"
    USER = "user"
    SYSTEM = "system"


class CoordinateSystem(StrEnum):
    PROVIDER_NATIVE = "provider_native"
    WGS84 = "wgs84"
    UNKNOWN = "unknown"


class CostConfidence(StrEnum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class RouteMode(StrEnum):
    WALKING = "walking"
    PUBLIC_TRANSIT = "public_transit"


@dataclass(frozen=True, slots=True)
class Money:
    """Non-negative CNY amount with at most two decimal places."""

    amount: Decimal
    currency: Literal["CNY"] = "CNY"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal) or isinstance(self.amount, bool):
            raise DomainInvariantError("money_type_invalid", field="amount")
        if self.amount.is_nan() or self.amount.is_infinite():
            raise DomainInvariantError("money_not_finite", field="amount")
        if self.amount < 0:
            raise DomainInvariantError("money_negative", field="amount")
        exponent = self.amount.as_tuple().exponent
        if not isinstance(exponent, int):
            raise DomainInvariantError("money_not_finite", field="amount")
        if exponent < -2:
            raise DomainInvariantError("money_precision_invalid", field="amount")
        if self.currency != "CNY":
            raise DomainInvariantError("currency_unsupported", field="currency")


@dataclass(frozen=True, slots=True)
class CostEntry:
    """Minimal cost truth state; category and aggregation are later concerns."""

    confidence: CostConfidence
    amount: Money | None
    source_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        _require_unique_ids(self.source_ids, field="source_ids")
        if self.confidence is CostConfidence.UNKNOWN and self.amount is not None:
            raise DomainInvariantError("unknown_cost_has_amount", field="amount")
        if self.confidence is not CostConfidence.UNKNOWN and self.amount is None:
            raise DomainInvariantError("known_cost_missing_amount", field="amount")
        if self.confidence is CostConfidence.VERIFIED and not self.source_ids:
            raise DomainInvariantError("verified_cost_missing_source", field="source_ids")


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_id: UUID
    provider: Provider
    source_type: str
    fetched_at: datetime
    valid_until: datetime | None
    reference_url: str | None = None
    attributions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_type.strip():
            raise DomainInvariantError("source_type_empty", field="source_type")
        _require_aware_datetime(self.fetched_at, field="fetched_at")
        if self.valid_until is not None:
            _require_aware_datetime(self.valid_until, field="valid_until")
            if self.valid_until < self.fetched_at:
                raise DomainInvariantError("source_validity_precedes_fetch", field="valid_until")
        if self.reference_url is not None and not self.reference_url.startswith("https://"):
            raise DomainInvariantError("source_reference_url_invalid", field="reference_url")
        if (
            not isinstance(self.attributions, tuple)
            or len(self.attributions) > 10
            or any(
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 500
                or any(ord(character) < 32 or ord(character) == 127 for character in value)
                for value in self.attributions
            )
        ):
            raise DomainInvariantError("source_attributions_invalid", field="attributions")


@dataclass(frozen=True, slots=True)
class SourceCatalog:
    """Immutable source lookup used to reject missing provenance references."""

    records: tuple[SourceRecord, ...]
    _by_id: Mapping[UUID, SourceRecord] = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=lambda: MappingProxyType({}),
    )

    def __post_init__(self) -> None:
        by_id = {record.source_id: record for record in self.records}
        if len(by_id) != len(self.records):
            raise DomainInvariantError("duplicate_source_id", field="records")
        object.__setattr__(self, "_by_id", MappingProxyType(by_id))

    def require_all(self, source_ids: tuple[UUID, ...]) -> None:
        missing = set(source_ids) - self._by_id.keys()
        if missing:
            raise DomainInvariantError("source_reference_missing", field="source_ids")


@dataclass(frozen=True, slots=True)
class Coordinates:
    longitude: Decimal
    latitude: Decimal
    coordinate_system: CoordinateSystem

    def __post_init__(self) -> None:
        _require_decimal(self.longitude, field="longitude")
        _require_decimal(self.latitude, field="latitude")
        if not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise DomainInvariantError("longitude_out_of_range", field="longitude")
        if not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise DomainInvariantError("latitude_out_of_range", field="latitude")


@dataclass(frozen=True, slots=True)
class Location:
    location_id: UUID
    name: str
    category: str
    city_adcode: str
    coordinates: Coordinates | None
    source_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainInvariantError("location_name_empty", field="name")
        if not self.category.strip():
            raise DomainInvariantError("location_category_empty", field="category")
        _require_adcode(self.city_adcode, field="city_adcode")
        _require_non_empty_unique_ids(self.source_ids, field="source_ids")


@dataclass(frozen=True, slots=True)
class RouteLeg:
    origin_location_id: UUID
    destination_location_id: UUID
    mode: RouteMode
    distance_meters: int
    duration_minutes: int
    source_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if self.origin_location_id == self.destination_location_id:
            raise DomainInvariantError("route_endpoints_equal", field="destination_location_id")
        if (
            not isinstance(self.distance_meters, int)
            or isinstance(self.distance_meters, bool)
            or self.distance_meters < 0
            or self.distance_meters > MAX_ROUTE_DISTANCE_METERS
        ):
            raise DomainInvariantError("route_distance_invalid", field="distance_meters")
        if (
            not isinstance(self.duration_minutes, int)
            or isinstance(self.duration_minutes, bool)
            or self.duration_minutes <= 0
            or self.duration_minutes > MAX_ROUTE_DURATION_MINUTES
        ):
            raise DomainInvariantError("route_duration_invalid", field="duration_minutes")
        _require_non_empty_unique_ids(self.source_ids, field="source_ids")


@dataclass(frozen=True, slots=True)
class WeatherForecast:
    forecast_date: date
    location_id: UUID
    temperature_min_celsius: Decimal
    temperature_max_celsius: Decimal
    source_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        _require_decimal(self.temperature_min_celsius, field="temperature_min_celsius")
        _require_decimal(self.temperature_max_celsius, field="temperature_max_celsius")
        if self.temperature_min_celsius > self.temperature_max_celsius:
            raise DomainInvariantError(
                "weather_temperature_range_invalid", field="temperature_max_celsius"
            )
        _require_non_empty_unique_ids(self.source_ids, field="source_ids")


@dataclass(frozen=True, slots=True)
class PlanDayStructure:
    """References for one day; sequence and timing rules are intentionally deferred."""

    local_date: date
    accommodation_location_id: UUID
    activity_location_ids: tuple[UUID, ...] = ()
    route_legs: tuple[RouteLeg, ...] = ()
    weather: WeatherForecast | None = None


@dataclass(frozen=True, slots=True)
class PlanStructure:
    """Single-city reference integrity without schedule or route-chain algorithms."""

    city_adcode: str
    locations: tuple[Location, ...]
    days: tuple[PlanDayStructure, ...]

    def __post_init__(self) -> None:
        _require_adcode(self.city_adcode, field="city_adcode")
        if not self.locations:
            raise DomainInvariantError("plan_locations_empty", field="locations")
        locations_by_id = {location.location_id: location for location in self.locations}
        if len(locations_by_id) != len(self.locations):
            raise DomainInvariantError("duplicate_location_id", field="locations")
        if any(location.city_adcode != self.city_adcode for location in self.locations):
            raise DomainInvariantError("location_outside_plan_city", field="locations")

        for day in self.days:
            references = {
                day.accommodation_location_id,
                *day.activity_location_ids,
                *(route.origin_location_id for route in day.route_legs),
                *(route.destination_location_id for route in day.route_legs),
            }
            if day.weather is not None:
                references.add(day.weather.location_id)
            if references - locations_by_id.keys():
                raise DomainInvariantError("location_reference_missing", field="days")


def _require_decimal(value: object, *, field: str) -> None:
    if not isinstance(value, Decimal) or isinstance(value, bool):
        raise DomainInvariantError("decimal_type_invalid", field=field)
    if value.is_nan() or value.is_infinite():
        raise DomainInvariantError("decimal_not_finite", field=field)


def _require_aware_datetime(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError("timezone_required", field=field)


def _require_adcode(value: str, *, field: str) -> None:
    if _ADCODE.fullmatch(value) is None:
        raise DomainInvariantError("adcode_invalid", field=field)


def _require_unique_ids(values: tuple[UUID, ...], *, field: str) -> None:
    if len(set(values)) != len(values):
        raise DomainInvariantError("duplicate_reference_id", field=field)


def _require_non_empty_unique_ids(values: tuple[UUID, ...], *, field: str) -> None:
    if not values:
        raise DomainInvariantError("source_reference_required", field=field)
    _require_unique_ids(values, field=field)
