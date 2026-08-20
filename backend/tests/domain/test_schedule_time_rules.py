"""F-001 daily-window and same-day activity time rules."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.contracts import TripPlanRequest, TripPlanResponse
from intelligent_travel_assistant.domain import (
    ActivityTimeSlot,
    DailyAvailability,
    DomainInvariantError,
    TwoDayTimePlan,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
START_DATE = date(2026, 8, 15)
ACTIVITY_ONE = UUID("91000000-0000-4000-8000-000000000001")
ACTIVITY_TWO = UUID("91000000-0000-4000-8000-000000000002")


def window(
    day_offset: int = 0,
    start_time: time = time(9),
    end_time: time = time(20),
) -> DailyAvailability:
    return DailyAvailability(
        day_offset=day_offset,
        start_time=start_time,
        end_time=end_time,
    )


def activity(
    activity_id: UUID = ACTIVITY_ONE,
    local_date: date = START_DATE,
    start_time: time = time(10),
    end_time: time = time(12),
) -> ActivityTimeSlot:
    return ActivityTimeSlot(
        activity_id=activity_id,
        local_date=local_date,
        start_time=start_time,
        end_time=end_time,
    )


def plan(
    *,
    windows: tuple[DailyAvailability, ...] | None = None,
    activities: tuple[ActivityTimeSlot, ...] = (),
) -> TwoDayTimePlan:
    return TwoDayTimePlan(
        start_date=START_DATE,
        windows=windows if windows is not None else (window(), window(1, time(9), time(18))),
        activities=activities,
    )


def window_with_string_start() -> DailyAvailability:
    return window(start_time="09:00")  # type: ignore[arg-type]


def activity_with_datetime_end() -> ActivityTimeSlot:
    return activity(end_time=datetime(2026, 8, 15, 12))  # type: ignore[arg-type]


def window_with_aware_start() -> DailyAvailability:
    return window(start_time=time(9, tzinfo=UTC))


def test_two_daily_windows_must_cover_offsets_zero_and_one_once() -> None:
    valid = plan()
    assert tuple(item.day_offset for item in valid.windows) == (0, 1)

    with pytest.raises(DomainInvariantError) as error:
        plan(windows=(window(), window()))
    assert error.value.code == "day_window_offsets_invalid"
    assert error.value.field == "windows"

    with pytest.raises(DomainInvariantError):
        TwoDayTimePlan(start_date=START_DATE, windows=(window(),), activities=())


@pytest.mark.parametrize("day_offset", [-1, 7, True, "0"])
def test_base_day_offset_is_a_strict_integer_from_zero_to_six(day_offset: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        window(day_offset=day_offset)  # type: ignore[arg-type]

    assert error.value.code == "day_offset_invalid"
    assert error.value.field == "day_offset"


def test_legacy_two_day_plan_still_rejects_an_offset_after_one() -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(windows=(window(0), window(2)))

    assert error.value.code == "day_window_offsets_invalid"
    assert error.value.field == "windows"


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [(time(9), time(9)), (time(10), time(9))],
)
def test_daily_window_requires_positive_same_day_duration(start_time: time, end_time: time) -> None:
    with pytest.raises(DomainInvariantError) as error:
        window(start_time=start_time, end_time=end_time)

    assert error.value.code == "day_window_time_order_invalid"
    assert error.value.field == "end_time"


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [(time(10), time(10)), (time(12), time(10))],
)
def test_activity_requires_positive_same_day_duration(start_time: time, end_time: time) -> None:
    with pytest.raises(DomainInvariantError) as error:
        activity(start_time=start_time, end_time=end_time)

    assert error.value.code == "activity_time_order_invalid"
    assert error.value.field == "end_time"


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (window_with_string_start, "start_time"),
        (activity_with_datetime_end, "end_time"),
        (window_with_aware_start, "start_time"),
    ],
)
def test_schedule_uses_naive_local_time_values(factory: Callable[[], object], field: str) -> None:
    with pytest.raises(DomainInvariantError) as error:
        factory()

    assert error.value.code == "local_time_invalid"
    assert error.value.field == field


def test_activities_may_touch_window_and_each_other_boundaries() -> None:
    first = activity(start_time=time(9), end_time=time(12))
    second = activity(
        activity_id=ACTIVITY_TWO,
        start_time=time(12),
        end_time=time(20),
    )

    schedule = plan(activities=(second, first))

    assert schedule.activities == (second, first)


def test_windows_are_matched_by_day_offset_not_input_position() -> None:
    second_day = activity(
        local_date=date(2026, 8, 16),
        start_time=time(17),
        end_time=time(18),
    )

    schedule = plan(
        windows=(window(1, time(10), time(18)), window(0, time(9), time(20))),
        activities=(second_day,),
    )

    assert schedule.windows[0].day_offset == 1


@pytest.mark.parametrize(
    ("start_time", "end_time"),
    [(time(8, 59), time(10)), (time(19), time(20, 1))],
)
def test_activity_outside_daily_window_by_one_minute_is_rejected(
    start_time: time, end_time: time
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(activities=(activity(start_time=start_time, end_time=end_time),))

    assert error.value.code == "activity_outside_day_window"
    assert error.value.field == "activities"


def test_activity_date_must_reference_one_of_the_two_trip_days() -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(activities=(activity(local_date=date(2026, 8, 17)),))

    assert error.value.code == "activity_date_outside_trip"
    assert error.value.field == "activities"


@pytest.mark.parametrize(
    "activities",
    [
        (
            activity(start_time=time(10), end_time=time(12)),
            activity(ACTIVITY_TWO, start_time=time(11, 59), end_time=time(13)),
        ),
        (
            activity(ACTIVITY_TWO, start_time=time(11), end_time=time(13)),
            activity(start_time=time(10), end_time=time(12)),
        ),
        (
            activity(start_time=time(10), end_time=time(14)),
            activity(ACTIVITY_TWO, start_time=time(11), end_time=time(12)),
        ),
    ],
)
def test_any_positive_same_day_overlap_is_rejected_regardless_of_input_order(
    activities: tuple[ActivityTimeSlot, ...],
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(activities=activities)

    assert error.value.code == "activities_overlap"
    assert error.value.field == "activities"


def test_same_clock_times_on_different_days_do_not_overlap() -> None:
    schedule = plan(
        activities=(
            activity(),
            activity(
                activity_id=ACTIVITY_TWO,
                local_date=date(2026, 8, 16),
                start_time=time(10),
                end_time=time(12),
            ),
        )
    )
    assert len(schedule.activities) == 2


def test_duplicate_activity_ids_are_rejected() -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan(
            activities=(
                activity(start_time=time(10), end_time=time(11)),
                activity(start_time=time(12), end_time=time(13)),
            )
        )

    assert error.value.code == "duplicate_activity_id"
    assert error.value.field == "activities"


def test_frozen_request_and_ready_plan_map_to_time_rules_without_drift() -> None:
    request_fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )
    ready_fixture = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )
    request = TripPlanRequest.model_validate(request_fixture["request"])
    response = TripPlanResponse.model_validate(ready_fixture["response"])
    assert response.plan is not None

    schedule = TwoDayTimePlan(
        start_date=request.start_date,
        windows=tuple(
            DailyAvailability(
                day_offset=item.day_offset,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            for item in request.day_windows
        ),
        activities=tuple(
            ActivityTimeSlot(
                activity_id=item.item_id,
                local_date=day.local_date,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            for day in response.plan.days
            for item in day.activities
        ),
    )

    assert len(schedule.windows) == 2
    assert len(schedule.activities) == 2
