"""Pure route-chain completeness and travel-time feasibility validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from intelligent_travel_assistant.domain.foundation import DomainInvariantError, RouteLeg
from intelligent_travel_assistant.domain.schedule import DailyAvailability


class RouteValidationStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class RouteActivity:
    activity_id: UUID
    location_id: UUID
    start_time: time
    end_time: time

    def __post_init__(self) -> None:
        if not isinstance(self.activity_id, UUID):
            raise DomainInvariantError("activity_id_invalid", field="activity_id")
        if not isinstance(self.location_id, UUID):
            raise DomainInvariantError("location_id_invalid", field="location_id")
        _require_local_time(self.start_time, field="start_time")
        _require_local_time(self.end_time, field="end_time")
        if self.end_time <= self.start_time:
            raise DomainInvariantError("activity_time_order_invalid", field="end_time")


@dataclass(frozen=True, slots=True)
class ExpectedRouteLeg:
    origin_location_id: UUID
    destination_location_id: UUID
    available_minutes: int


@dataclass(frozen=True, slots=True)
class RouteValidationResult:
    status: RouteValidationStatus
    missing_legs: tuple[ExpectedRouteLeg, ...] = ()


@dataclass(frozen=True, slots=True)
class DailyRoutePlan:
    """Validate a supplied route chain without fetching or repairing routes."""

    accommodation_location_id: UUID
    availability: DailyAvailability
    activities: tuple[RouteActivity, ...]
    routes: tuple[RouteLeg, ...]

    def validate(self) -> RouteValidationResult:
        expected = self.expected_legs()
        if len(self.routes) > len(expected):
            raise DomainInvariantError("route_chain_extra_leg", field="routes")

        matched_expected_indices: list[int] = []
        search_from = 0
        for route in self.routes:
            matched_index = _find_expected_leg(expected, route, start=search_from)
            if matched_index is None:
                raise DomainInvariantError("route_chain_mismatch", field="routes")
            matched_expected_indices.append(matched_index)
            search_from = matched_index + 1

            available_minutes = expected[matched_index].available_minutes
            if route.duration_minutes > available_minutes:
                raise DomainInvariantError("route_duration_exceeds_gap", field="routes")

        matched = set(matched_expected_indices)
        missing = tuple(item for index, item in enumerate(expected) if index not in matched)
        if missing:
            return RouteValidationResult(RouteValidationStatus.MISSING, missing)
        return RouteValidationResult(RouteValidationStatus.VERIFIED)

    def expected_legs(self) -> tuple[ExpectedRouteLeg, ...]:
        """Return the exact accommodation round-trip chain without fetching it."""

        self._require_inputs()
        return self._expected_legs()

    def _require_inputs(self) -> None:
        if not isinstance(self.accommodation_location_id, UUID):
            raise DomainInvariantError(
                "accommodation_location_id_invalid",
                field="accommodation_location_id",
            )
        if not isinstance(self.availability, DailyAvailability):
            raise DomainInvariantError("day_window_invalid", field="availability")
        if not isinstance(self.activities, tuple) or not all(
            isinstance(item, RouteActivity) for item in self.activities
        ):
            raise DomainInvariantError("activities_invalid", field="activities")
        if not isinstance(self.routes, tuple) or not all(
            isinstance(item, RouteLeg) for item in self.routes
        ):
            raise DomainInvariantError("routes_invalid", field="routes")
        if len({item.activity_id for item in self.activities}) != len(self.activities):
            raise DomainInvariantError("duplicate_activity_id", field="activities")

        previous_end = self.availability.start_time
        for activity in self.activities:
            if (
                activity.start_time < self.availability.start_time
                or activity.end_time > self.availability.end_time
            ):
                raise DomainInvariantError("activity_outside_day_window", field="activities")
            if activity.start_time < previous_end:
                raise DomainInvariantError("activity_visit_order_invalid", field="activities")
            previous_end = activity.end_time

    def _expected_legs(self) -> tuple[ExpectedRouteLeg, ...]:
        if not self.activities:
            return ()

        expected: list[ExpectedRouteLeg] = []
        previous_location = self.accommodation_location_id
        previous_time = self.availability.start_time
        for activity in self.activities:
            _append_expected_leg(
                expected,
                origin=previous_location,
                destination=activity.location_id,
                available_minutes=_minutes_between(previous_time, activity.start_time),
            )
            previous_location = activity.location_id
            previous_time = activity.end_time

        _append_expected_leg(
            expected,
            origin=previous_location,
            destination=self.accommodation_location_id,
            available_minutes=_minutes_between(previous_time, self.availability.end_time),
        )
        return tuple(expected)


def _append_expected_leg(
    expected: list[ExpectedRouteLeg],
    *,
    origin: UUID,
    destination: UUID,
    available_minutes: int,
) -> None:
    if origin != destination:
        if available_minutes <= 0:
            raise DomainInvariantError("route_gap_not_positive", field="activities")
        expected.append(ExpectedRouteLeg(origin, destination, available_minutes))


def _find_expected_leg(
    expected: tuple[ExpectedRouteLeg, ...],
    route: RouteLeg,
    *,
    start: int,
) -> int | None:
    for index in range(start, len(expected)):
        item = expected[index]
        if (
            item.origin_location_id == route.origin_location_id
            and item.destination_location_id == route.destination_location_id
        ):
            return index
    return None


def _minutes_between(start: time, end: time) -> int:
    start_value = datetime.combine(date.min, start)
    end_value = datetime.combine(date.min, end)
    return int((end_value - start_value).total_seconds() // 60)


def _require_local_time(value: object, *, field: str) -> None:
    if not isinstance(value, time) or value.tzinfo is not None:
        raise DomainInvariantError("local_time_invalid", field=field)
