"""Pure F-004B1 multi-city continuity, transfer, and terminal rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.domain.budget import BudgetCostItem, CostCategory
from intelligent_travel_assistant.domain.foundation import (
    CostConfidence,
    DomainInvariantError,
    Money,
)

_SHANGHAI_OFFSET: Final = timedelta(hours=8)
_SERVICE_NUMBER_PATTERN: Final = re.compile(r"^[A-Z0-9]{1,12}$")


class IntercityMode(StrEnum):
    RAIL = "rail"
    AIR = "air"
    COACH = "coach"


_BUFFERS: Final[dict[IntercityMode, tuple[int, int]]] = {
    IntercityMode.RAIL: (60, 30),
    IntercityMode.AIR: (120, 60),
    IntercityMode.COACH: (45, 30),
}


class MultiCityTerminalStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    NEEDS_INPUT = "needs_input"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CityStay:
    city: str
    nights: int
    accommodation_location_id: UUID

    def __post_init__(self) -> None:
        city = _require_text(self.city, field="city", min_length=2, max_length=30)
        if not _strict_int_between(self.nights, 1, 6):
            raise DomainInvariantError("multicity_nights_invalid", field="nights")
        if not isinstance(self.accommodation_location_id, UUID):
            raise DomainInvariantError(
                "multicity_accommodation_invalid", field="accommodation_location_id"
            )
        object.__setattr__(self, "city", city)


@dataclass(frozen=True, slots=True)
class UserProvidedIntercitySegment:
    from_city_index: int
    to_city_index: int
    mode: IntercityMode
    departure_station: str
    arrival_station: str
    departure_at: datetime
    arrival_at: datetime
    fare: Money | None = None

    def __post_init__(self) -> None:
        _require_city_index(self.from_city_index, field="from_city_index")
        _require_city_index(self.to_city_index, field="to_city_index")
        if self.to_city_index != self.from_city_index + 1:
            raise DomainInvariantError("intercity_segment_order_invalid", field="to_city_index")
        if not isinstance(self.mode, IntercityMode):
            raise DomainInvariantError("intercity_mode_invalid", field="mode")
        departure_station = _require_text(
            self.departure_station,
            field="departure_station",
            min_length=1,
            max_length=120,
        )
        arrival_station = _require_text(
            self.arrival_station,
            field="arrival_station",
            min_length=1,
            max_length=120,
        )
        _require_shanghai_datetime(self.departure_at, field="departure_at")
        _require_shanghai_datetime(self.arrival_at, field="arrival_at")
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise DomainInvariantError("intercity_time_invalid", field="arrival_at")
        if self.fare is not None and not isinstance(self.fare, Money):
            raise DomainInvariantError("intercity_fare_invalid", field="fare")
        object.__setattr__(self, "departure_station", departure_station)
        object.__setattr__(self, "arrival_station", arrival_station)


def normalize_service_number(value: object) -> str:
    """Normalize a strict user-provided service number without claiming verification."""

    if not isinstance(value, str):
        raise DomainInvariantError("intercity_service_number_invalid", field="service_number")
    normalized = value.strip().upper()
    if _SERVICE_NUMBER_PATTERN.fullmatch(normalized) is None:
        raise DomainInvariantError("intercity_service_number_invalid", field="service_number")
    return normalized


@dataclass(frozen=True, slots=True)
class BookedRailIntercitySegment:
    """A user-provided, unverified, same-day direct rail segment."""

    from_city_index: int
    to_city_index: int
    service_number: str
    departure_station: str
    arrival_station: str
    departure_at: datetime
    arrival_at: datetime
    fare: Money | None = None

    def __post_init__(self) -> None:
        _require_city_index(self.from_city_index, field="from_city_index")
        _require_city_index(self.to_city_index, field="to_city_index")
        if self.to_city_index != self.from_city_index + 1:
            raise DomainInvariantError("intercity_segment_order_invalid", field="to_city_index")
        service_number = normalize_service_number(self.service_number)
        departure_station = _require_text(
            self.departure_station,
            field="departure_station",
            min_length=1,
            max_length=120,
        )
        arrival_station = _require_text(
            self.arrival_station,
            field="arrival_station",
            min_length=1,
            max_length=120,
        )
        _require_shanghai_datetime(self.departure_at, field="departure_at")
        _require_shanghai_datetime(self.arrival_at, field="arrival_at")
        if (
            self.departure_at.date() != self.arrival_at.date()
            or self.arrival_at <= self.departure_at
        ):
            raise DomainInvariantError("intercity_time_invalid", field="arrival_at")
        if self.fare is not None and (not isinstance(self.fare, Money) or self.fare.amount <= 0):
            raise DomainInvariantError("intercity_fare_invalid", field="fare")
        object.__setattr__(self, "service_number", service_number)
        object.__setattr__(self, "departure_station", departure_station)
        object.__setattr__(self, "arrival_station", arrival_station)

    @property
    def mode(self) -> IntercityMode:
        return IntercityMode.RAIL

    @property
    def duration(self) -> timedelta:
        return self.arrival_at - self.departure_at


@dataclass(frozen=True, slots=True)
class MultiCityTrip:
    start_date: date
    end_date: date
    city_stays: tuple[CityStay, ...]
    intercity_segments: tuple[UserProvidedIntercitySegment, ...]

    def __post_init__(self) -> None:
        _require_date(self.start_date, field="start_date")
        _require_date(self.end_date, field="end_date")
        if self.end_date <= self.start_date or not 3 <= self.day_count <= 7:
            raise DomainInvariantError("trip_day_count_invalid", field="end_date")
        if (
            not isinstance(self.city_stays, tuple)
            or not 2 <= len(self.city_stays) <= 3
            or not all(isinstance(item, CityStay) for item in self.city_stays)
        ):
            raise DomainInvariantError("multicity_city_count_invalid", field="city_stays")
        normalized_cities = tuple(item.city.casefold() for item in self.city_stays)
        if len(set(normalized_cities)) != len(normalized_cities):
            raise DomainInvariantError("multicity_city_order_invalid", field="city_stays")
        accommodation_ids = tuple(item.accommodation_location_id for item in self.city_stays)
        if len(set(accommodation_ids)) != len(accommodation_ids):
            raise DomainInvariantError("multicity_accommodation_invalid", field="city_stays")
        if sum(item.nights for item in self.city_stays) != self.day_count - 1:
            raise DomainInvariantError("multicity_nights_invalid", field="city_stays")
        if (
            not isinstance(self.intercity_segments, tuple)
            or len(self.intercity_segments) != len(self.city_stays) - 1
            or not all(
                isinstance(item, UserProvidedIntercitySegment) for item in self.intercity_segments
            )
        ):
            raise DomainInvariantError(
                "intercity_segment_order_invalid", field="intercity_segments"
            )
        for index, (segment, transfer_date) in enumerate(
            zip(self.intercity_segments, self.transfer_dates, strict=True)
        ):
            if segment.from_city_index != index or segment.to_city_index != index + 1:
                raise DomainInvariantError(
                    "intercity_segment_order_invalid", field="intercity_segments"
                )
            if (
                segment.departure_at.date() != transfer_date
                or segment.arrival_at.date() != transfer_date
            ):
                raise DomainInvariantError("intercity_time_invalid", field="intercity_segments")

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


@dataclass(frozen=True, slots=True)
class BookedRailTrip:
    """A V4 trip whose adjacent transfers are all user-provided rail segments."""

    start_date: date
    end_date: date
    city_stays: tuple[CityStay, ...]
    intercity_segments: tuple[BookedRailIntercitySegment, ...]

    def __post_init__(self) -> None:
        _require_date(self.start_date, field="start_date")
        _require_date(self.end_date, field="end_date")
        if self.end_date <= self.start_date or not 3 <= self.day_count <= 7:
            raise DomainInvariantError("trip_day_count_invalid", field="end_date")
        if (
            not isinstance(self.city_stays, tuple)
            or not 2 <= len(self.city_stays) <= 3
            or not all(isinstance(item, CityStay) for item in self.city_stays)
        ):
            raise DomainInvariantError("multicity_city_count_invalid", field="city_stays")
        normalized_cities = tuple(item.city.casefold() for item in self.city_stays)
        accommodation_ids = tuple(item.accommodation_location_id for item in self.city_stays)
        if len(set(normalized_cities)) != len(normalized_cities):
            raise DomainInvariantError("multicity_city_order_invalid", field="city_stays")
        if len(set(accommodation_ids)) != len(accommodation_ids):
            raise DomainInvariantError("multicity_accommodation_invalid", field="city_stays")
        if sum(item.nights for item in self.city_stays) != self.day_count - 1:
            raise DomainInvariantError("multicity_nights_invalid", field="city_stays")
        if (
            not isinstance(self.intercity_segments, tuple)
            or len(self.intercity_segments) != len(self.city_stays) - 1
            or not all(
                isinstance(item, BookedRailIntercitySegment) for item in self.intercity_segments
            )
        ):
            raise DomainInvariantError(
                "intercity_segment_order_invalid", field="intercity_segments"
            )
        for index, (segment, transfer_date) in enumerate(
            zip(self.intercity_segments, self.transfer_dates, strict=True)
        ):
            if segment.from_city_index != index or segment.to_city_index != index + 1:
                raise DomainInvariantError(
                    "intercity_segment_order_invalid", field="intercity_segments"
                )
            if (
                segment.departure_at.date() != transfer_date
                or segment.arrival_at.date() != transfer_date
            ):
                raise DomainInvariantError("intercity_time_invalid", field="intercity_segments")

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def transfer_dates(self) -> tuple[date, ...]:
        elapsed_nights = 0
        dates: list[date] = []
        for stay in self.city_stays[:-1]:
            elapsed_nights += stay.nights
            dates.append(self.start_date + timedelta(days=elapsed_nights))
        return tuple(dates)


@dataclass(frozen=True, slots=True)
class MultiCityActivitySlot:
    city_index: int
    start_time: time
    end_time: time

    def __post_init__(self) -> None:
        _require_city_index(self.city_index, field="city_index")
        _require_local_time(self.start_time, field="start_time")
        _require_local_time(self.end_time, field="end_time")
        if self.end_time <= self.start_time:
            raise DomainInvariantError("activity_time_invalid", field="end_time")


@dataclass(frozen=True, slots=True)
class MultiCityDaySchedule:
    local_date: date
    departure_city_index: int
    arrival_city_index: int
    overnight_city_index: int
    intercity_segment: UserProvidedIntercitySegment | None
    activities: tuple[MultiCityActivitySlot, ...]
    local_route_city_pairs: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        _require_date(self.local_date, field="local_date")
        for field, value in (
            ("departure_city_index", self.departure_city_index),
            ("arrival_city_index", self.arrival_city_index),
            ("overnight_city_index", self.overnight_city_index),
        ):
            _require_city_index(value, field=field)
        if not isinstance(self.activities, tuple) or not all(
            isinstance(item, MultiCityActivitySlot) for item in self.activities
        ):
            raise DomainInvariantError("activities_invalid", field="activities")
        _require_local_route_pairs(
            self.local_route_city_pairs,
            allowed_cities={self.departure_city_index, self.arrival_city_index},
        )

        if self.intercity_segment is None:
            if not (
                self.departure_city_index == self.arrival_city_index == self.overnight_city_index
            ):
                raise DomainInvariantError(
                    "multicity_day_continuity_invalid", field="arrival_city_index"
                )
            if not 1 <= len(self.activities) <= 2:
                raise DomainInvariantError("day_activity_count_invalid", field="activities")
            if any(
                activity.city_index != self.departure_city_index for activity in self.activities
            ):
                raise DomainInvariantError("multicity_activity_city_invalid", field="activities")
            return

        segment = self.intercity_segment
        if not isinstance(segment, UserProvidedIntercitySegment):
            raise DomainInvariantError("intercity_segment_invalid", field="intercity_segment")
        if (
            self.local_date != segment.departure_at.date()
            or self.departure_city_index != segment.from_city_index
            or self.arrival_city_index != segment.to_city_index
            or self.overnight_city_index != segment.to_city_index
        ):
            raise DomainInvariantError(
                "multicity_day_continuity_invalid", field="intercity_segment"
            )
        if len(self.activities) > 1:
            raise DomainInvariantError("day_activity_count_invalid", field="activities")
        before_minutes, after_minutes = intercity_buffer(segment.mode)
        departure_cutoff = (segment.departure_at - timedelta(minutes=before_minutes)).time()
        arrival_cutoff = (segment.arrival_at + timedelta(minutes=after_minutes)).time()
        for activity in self.activities:
            if activity.city_index == self.departure_city_index:
                if activity.end_time > departure_cutoff:
                    raise DomainInvariantError("intercity_buffer_conflict", field="activities")
            elif activity.city_index == self.arrival_city_index:
                if activity.start_time < arrival_cutoff:
                    raise DomainInvariantError("intercity_buffer_conflict", field="activities")
            else:
                raise DomainInvariantError("multicity_activity_city_invalid", field="activities")


def intercity_buffer(mode: IntercityMode) -> tuple[int, int]:
    if not isinstance(mode, IntercityMode):
        raise DomainInvariantError("intercity_mode_invalid", field="mode")
    return _BUFFERS[mode]


def build_intercity_cost_item(
    cost_id: UUID,
    fare: Money | None,
    source_id: UUID,
) -> BudgetCostItem:
    if not isinstance(source_id, UUID):
        raise DomainInvariantError("source_ids_invalid", field="source_id")
    return BudgetCostItem(
        cost_id=cost_id,
        category=CostCategory.INTERCITY_TRANSPORT,
        confidence=(CostConfidence.UNKNOWN if fare is None else CostConfidence.USER_PROVIDED),
        amount=fare,
        source_ids=(source_id,),
    )


def classify_multicity_terminal(
    *,
    missing_input: bool = False,
    constraint_conflict: bool = False,
    execution_failed: bool = False,
    partial_facts: bool = False,
    unknown_cost_count: int = 0,
) -> MultiCityTerminalStatus:
    flags = (missing_input, constraint_conflict, execution_failed, partial_facts)
    if any(type(value) is not bool for value in flags):
        raise DomainInvariantError("multicity_terminal_facts_invalid", field="facts")
    if (
        type(unknown_cost_count) is not int
        or unknown_cost_count < 0
        or sum((missing_input, constraint_conflict, execution_failed)) > 1
    ):
        raise DomainInvariantError("multicity_terminal_facts_invalid", field="unknown_cost_count")
    if execution_failed:
        return MultiCityTerminalStatus.FAILED
    if missing_input:
        return MultiCityTerminalStatus.NEEDS_INPUT
    if constraint_conflict:
        return MultiCityTerminalStatus.CONFLICT
    if partial_facts or unknown_cost_count:
        return MultiCityTerminalStatus.PARTIAL
    return MultiCityTerminalStatus.READY


def _require_date(value: object, *, field: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise DomainInvariantError("local_date_invalid", field=field)


def _require_local_time(value: object, *, field: str) -> None:
    if not isinstance(value, time) or value.tzinfo is not None:
        raise DomainInvariantError("local_time_invalid", field=field)


def _require_shanghai_datetime(value: object, *, field: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != _SHANGHAI_OFFSET
    ):
        raise DomainInvariantError("intercity_time_invalid", field=field)


def _require_city_index(value: object, *, field: str) -> None:
    if not _strict_int_between(value, 0, 2):
        raise DomainInvariantError("multicity_city_index_invalid", field=field)


def _strict_int_between(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _require_text(
    value: object,
    *,
    field: str,
    min_length: int,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise DomainInvariantError("text_invalid", field=field)
    normalized = value.strip()
    if not min_length <= len(normalized) <= max_length or any(
        ord(character) < 32 or ord(character) == 127 for character in normalized
    ):
        raise DomainInvariantError("text_invalid", field=field)
    return normalized


def _require_local_route_pairs(
    value: object,
    *,
    allowed_cities: set[int],
) -> None:
    if not isinstance(value, tuple):
        raise DomainInvariantError("multicity_route_city_invalid", field="local_route_city_pairs")
    for pair in value:
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(type(index) is not int for index in pair)
            or pair[0] != pair[1]
            or pair[0] not in allowed_cities
        ):
            raise DomainInvariantError(
                "multicity_route_city_invalid", field="local_route_city_pairs"
            )
