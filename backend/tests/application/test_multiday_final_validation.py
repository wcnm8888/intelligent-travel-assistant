"""F-004A final validation must inspect every day, not only offsets 0 and 1."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from intelligent_travel_assistant.application.planning.final_validation import (
    AccommodationAnchor,
    FinalValidationIssue,
    FinalValidationIssueCode,
    _validate_routes,
    _validate_schedule,
    _validate_weather,
)
from intelligent_travel_assistant.application.ports import (
    CandidateActivity,
    CandidateDay,
    DailyWeather,
    PlanCandidate,
    WeatherForecastResult,
)
from intelligent_travel_assistant.domain import (
    DailyAvailability,
    Provider,
    ProviderResult,
    ProviderResultStatus,
    RouteValidationStatus,
    SourceRecord,
)

START_DATE = date(2026, 8, 14)
HOTEL_ID = UUID("92000000-0000-4000-8000-000000000010")
SOURCE_ID = UUID("42000000-0000-4000-8000-000000000001")
WEATHER_LOCATION_ID = UUID("92000000-0000-4000-8000-000000000020")


def candidate(day_count: int) -> PlanCandidate:
    return PlanCandidate(
        "synthetic",
        tuple(
            CandidateDay(
                START_DATE + timedelta(days=offset),
                (
                    CandidateActivity(
                        HOTEL_ID,
                        START_DATE + timedelta(days=offset),
                        f"synthetic {offset}",
                        time(10),
                        time(11),
                        (SOURCE_ID,),
                    ),
                ),
            )
            for offset in range(day_count)
        ),
        "synthetic",
        (),
    )


def windows(day_count: int) -> tuple[DailyAvailability, ...]:
    return tuple(DailyAvailability(offset, time(9), time(18)) for offset in range(day_count))


def test_schedule_validation_checks_valid_three_and_seven_day_candidates() -> None:
    for day_count in (3, 7):
        issues: list[FinalValidationIssue] = []
        _validate_schedule(candidate(day_count), windows(day_count), issues)
        assert issues == []


def test_schedule_validation_detects_a_middle_day_window_conflict() -> None:
    day_windows = list(windows(3))
    day_windows[1] = DailyAvailability(1, time(12), time(18))
    issues: list[FinalValidationIssue] = []

    _validate_schedule(candidate(3), tuple(day_windows), issues)

    assert tuple(item.code for item in issues) == (FinalValidationIssueCode.SCHEDULE_CONFLICT,)


def test_route_validation_returns_one_result_for_every_trip_day() -> None:
    issues: list[FinalValidationIssue] = []
    validations = _validate_routes(
        candidate(7),
        AccommodationAnchor(HOTEL_ID, "330100", None),
        windows(7),
        (),
        issues,
    )

    assert len(validations) == 7
    assert all(item.status is RouteValidationStatus.VERIFIED for item in validations)
    assert issues == []


def weather_result(day_offsets: tuple[int, ...]) -> ProviderResult[WeatherForecastResult]:
    fetched_at = datetime(2026, 8, 13, 2, tzinfo=UTC)
    source = SourceRecord(
        SOURCE_ID,
        Provider.QWEATHER,
        "weather_forecast",
        fetched_at,
        fetched_at + timedelta(days=7),
    )
    return ProviderResult(
        ProviderResultStatus.OK,
        Provider.QWEATHER,
        WeatherForecastResult(
            WEATHER_LOCATION_ID,
            tuple(
                DailyWeather(
                    START_DATE + timedelta(days=offset),
                    "clear",
                    "clear",
                    Decimal("20.0"),
                    Decimal("28.0"),
                )
                for offset in day_offsets
            ),
        ),
        fetched_at,
        source.valid_until,
        (),
        None,
        (source,),
    )


def test_weather_validation_requires_every_date_including_middle_days() -> None:
    complete_issues: list[FinalValidationIssue] = []
    _validate_weather(
        candidate(7), weather_result(tuple(range(7))), WEATHER_LOCATION_ID, complete_issues
    )
    assert complete_issues == []

    missing_middle_issues: list[FinalValidationIssue] = []
    _validate_weather(
        candidate(7),
        weather_result((0, 1, 2, 4, 5, 6)),
        WEATHER_LOCATION_ID,
        missing_middle_issues,
    )
    assert tuple(item.code for item in missing_middle_issues) == (
        FinalValidationIssueCode.WEATHER_INCOMPLETE,
    )
