"""F-004A variable daily-window and activity schedule invariants."""

from datetime import date, time, timedelta
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    ActivityTimeSlot,
    DailyAvailability,
    DomainInvariantError,
    MultiDayTimePlan,
)

START_DATE = date(2026, 8, 14)


def windows(day_count: int) -> tuple[DailyAvailability, ...]:
    return tuple(DailyAvailability(offset, time(9), time(18)) for offset in range(day_count))


def activity(day_offset: int, sequence: int = 1) -> ActivityTimeSlot:
    return ActivityTimeSlot(
        UUID(f"91000000-0000-4000-8000-{day_offset * 10 + sequence:012d}"),
        START_DATE + timedelta(days=day_offset),
        time(9 + sequence),
        time(10 + sequence),
    )


def plan(
    day_count: int,
    *,
    day_windows: tuple[DailyAvailability, ...] | None = None,
    activities: tuple[ActivityTimeSlot, ...] | None = None,
) -> MultiDayTimePlan:
    return MultiDayTimePlan(
        start_date=START_DATE,
        end_date=START_DATE + timedelta(days=day_count - 1),
        windows=day_windows if day_windows is not None else windows(day_count),
        activities=(
            activities
            if activities is not None
            else tuple(activity(offset) for offset in range(day_count))
        ),
    )


@pytest.mark.parametrize("day_count", [2, 3, 7])
def test_multiday_time_plan_accepts_exact_windows_and_one_activity_per_day(
    day_count: int,
) -> None:
    value = plan(day_count)

    assert value.day_count == day_count
    assert tuple(item.day_offset for item in value.windows) == tuple(range(day_count))


def test_base_availability_accepts_offsets_zero_through_six() -> None:
    assert DailyAvailability(6, time(9), time(18)).day_offset == 6
    for invalid in (-1, 7, True, "2"):
        with pytest.raises(DomainInvariantError) as error:
            DailyAvailability(invalid, time(9), time(18))  # type: ignore[arg-type]
        assert error.value.code == "day_offset_invalid"


@pytest.mark.parametrize(
    "day_windows",
    [
        windows(3)[:2],
        (windows(3)[0], windows(3)[1], windows(3)[1]),
        (windows(3)[2], windows(3)[0], windows(3)[1]),
    ],
)
def test_multiday_windows_require_the_exact_ordered_offset_set(
    day_windows: tuple[DailyAvailability, ...],
) -> None:
    if tuple(item.day_offset for item in day_windows) == (2, 0, 1):
        value = plan(3, day_windows=day_windows)
        assert value.windows == day_windows
        return

    with pytest.raises(DomainInvariantError) as error:
        plan(3, day_windows=day_windows)
    assert error.value.code == "day_window_offsets_invalid"


def test_multiday_activity_dates_and_daily_count_are_closed_over_the_trip() -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(3, activities=(activity(0), activity(1)))
    assert error.value.code == "day_activity_count_invalid"

    with pytest.raises(DomainInvariantError) as error:
        plan(3, activities=tuple(activity(offset) for offset in range(4)))
    assert error.value.code == "activity_date_outside_trip"

    with pytest.raises(DomainInvariantError) as error:
        plan(2, activities=(activity(0), activity(0, 2), activity(0, 3), activity(1)))
    assert error.value.code == "day_activity_count_invalid"


def test_multiday_plan_rejects_eight_days_and_middle_day_overlap() -> None:
    with pytest.raises(DomainInvariantError) as error:
        MultiDayTimePlan(
            start_date=START_DATE,
            end_date=START_DATE + timedelta(days=7),
            windows=windows(7),
            activities=tuple(activity(offset) for offset in range(7)),
        )
    assert error.value.code == "trip_day_count_invalid"

    overlapping = (
        activity(0),
        activity(1),
        ActivityTimeSlot(
            UUID("91000000-0000-4000-8000-000000000099"),
            START_DATE + timedelta(days=1),
            time(10, 30),
            time(11, 30),
        ),
        activity(2),
    )
    with pytest.raises(DomainInvariantError) as error:
        plan(3, activities=overlapping)
    assert error.value.code == "activities_overlap"
