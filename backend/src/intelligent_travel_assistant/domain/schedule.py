"""Pure daily availability and same-day activity time validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from intelligent_travel_assistant.domain.foundation import DomainInvariantError


@dataclass(frozen=True, slots=True)
class DailyAvailability:
    day_offset: int
    start_time: time
    end_time: time

    def __post_init__(self) -> None:
        if (
            not isinstance(self.day_offset, int)
            or isinstance(self.day_offset, bool)
            or self.day_offset not in (0, 1)
        ):
            raise DomainInvariantError("day_offset_invalid", field="day_offset")
        _require_local_time(self.start_time, field="start_time")
        _require_local_time(self.end_time, field="end_time")
        if self.end_time <= self.start_time:
            raise DomainInvariantError("day_window_time_order_invalid", field="end_time")


@dataclass(frozen=True, slots=True)
class ActivityTimeSlot:
    activity_id: UUID
    local_date: date
    start_time: time
    end_time: time

    def __post_init__(self) -> None:
        if not isinstance(self.activity_id, UUID):
            raise DomainInvariantError("activity_id_invalid", field="activity_id")
        _require_local_date(self.local_date, field="local_date")
        _require_local_time(self.start_time, field="start_time")
        _require_local_time(self.end_time, field="end_time")
        if self.end_time <= self.start_time:
            raise DomainInvariantError("activity_time_order_invalid", field="end_time")


@dataclass(frozen=True, slots=True)
class TwoDayTimePlan:
    """Validate two local days without arranging or mutating activities."""

    start_date: date
    windows: tuple[DailyAvailability, ...]
    activities: tuple[ActivityTimeSlot, ...]

    def __post_init__(self) -> None:
        _require_local_date(self.start_date, field="start_date")
        windows = _require_windows(self.windows)
        activities = _require_activities(self.activities)
        dates = (self.start_date, self.start_date + timedelta(days=1))

        activities_by_date: dict[date, list[ActivityTimeSlot]] = {
            dates[0]: [],
            dates[1]: [],
        }
        for activity in activities:
            if activity.local_date not in activities_by_date:
                raise DomainInvariantError("activity_date_outside_trip", field="activities")
            day_offset = (activity.local_date - self.start_date).days
            availability = windows[day_offset]
            if (
                activity.start_time < availability.start_time
                or activity.end_time > availability.end_time
            ):
                raise DomainInvariantError("activity_outside_day_window", field="activities")
            activities_by_date[activity.local_date].append(activity)

        for day_activities in activities_by_date.values():
            ordered = sorted(
                day_activities,
                key=lambda item: (item.start_time, item.end_time, item.activity_id.int),
            )
            for previous, current in zip(ordered, ordered[1:], strict=False):
                if current.start_time < previous.end_time:
                    raise DomainInvariantError("activities_overlap", field="activities")


def _require_windows(
    value: object,
) -> dict[int, DailyAvailability]:
    if not isinstance(value, tuple) or not all(
        isinstance(item, DailyAvailability) for item in value
    ):
        raise DomainInvariantError("day_windows_invalid", field="windows")
    by_offset = {item.day_offset: item for item in value}
    if len(value) != 2 or set(by_offset) != {0, 1}:
        raise DomainInvariantError("day_window_offsets_invalid", field="windows")
    return by_offset


def _require_activities(value: object) -> tuple[ActivityTimeSlot, ...]:
    if not isinstance(value, tuple) or not all(
        isinstance(item, ActivityTimeSlot) for item in value
    ):
        raise DomainInvariantError("activities_invalid", field="activities")
    if len({item.activity_id for item in value}) != len(value):
        raise DomainInvariantError("duplicate_activity_id", field="activities")
    return value


def _require_local_date(value: object, *, field: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise DomainInvariantError("local_date_invalid", field=field)


def _require_local_time(value: object, *, field: str) -> None:
    if not isinstance(value, time) or value.tzinfo is not None:
        raise DomainInvariantError("local_time_invalid", field=field)
