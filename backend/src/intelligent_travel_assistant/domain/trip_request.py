"""Pure F-001 request normalization and deterministic input constraints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from intelligent_travel_assistant.domain.foundation import DomainInvariantError

# F-001 only accepts current/future dates within five days. China Standard
# Time is UTC+08:00 throughout that window, so this remains stdlib-only on
# Windows hosts that do not ship an IANA zoneinfo database.
SHANGHAI_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
MIN_START_OFFSET_DAYS = 1
MAX_START_OFFSET_DAYS = 5
MIN_TRAVELERS = 1
MAX_TRAVELERS = 8
MAX_INTERESTS = 5
MAX_SHORT_TEXT_LENGTH = 120
MAX_FREE_TEXT_LENGTH = 200


@dataclass(frozen=True, slots=True)
class TripRequestInput:
    """Normalized primitive request data before provider or schedule work.

    ``evaluated_at`` is supplied by the application boundary. The domain never
    reads the system clock, which keeps the rolling D+1 to D+5 window
    deterministic and testable.
    """

    city: str
    start_date: date
    end_date: date
    travelers: int
    interests: tuple[str, ...]
    free_text: str
    evaluated_at: datetime

    def __post_init__(self) -> None:
        local_evaluated_at = _normalize_evaluation_time(self.evaluated_at)
        city = _normalize_required_text(
            self.city,
            field="city",
            min_length=2,
            max_length=30,
        )
        interests = _normalize_interests(self.interests)
        free_text = _normalize_optional_text(
            self.free_text,
            field="free_text",
            max_length=MAX_FREE_TEXT_LENGTH,
        )

        _validate_trip_dates(
            start_date=self.start_date,
            end_date=self.end_date,
            local_today=local_evaluated_at.date(),
        )
        _validate_travelers(self.travelers)

        object.__setattr__(self, "city", city)
        object.__setattr__(self, "interests", interests)
        object.__setattr__(self, "free_text", free_text)
        object.__setattr__(self, "evaluated_at", local_evaluated_at)


def _normalize_evaluation_time(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainInvariantError("timezone_required", field="evaluated_at")
    return value.astimezone(SHANGHAI_TIMEZONE)


def _validate_trip_dates(*, start_date: object, end_date: object, local_today: date) -> None:
    checked_start_date = _require_strict_date(start_date, field="start_date")
    checked_end_date = _require_strict_date(end_date, field="end_date")
    if checked_end_date <= checked_start_date:
        raise DomainInvariantError("trip_date_order_invalid", field="end_date")
    if checked_end_date != checked_start_date + timedelta(days=1):
        raise DomainInvariantError("trip_dates_not_consecutive", field="end_date")

    earliest_start = local_today + timedelta(days=MIN_START_OFFSET_DAYS)
    latest_start = local_today + timedelta(days=MAX_START_OFFSET_DAYS)
    if not earliest_start <= checked_start_date <= latest_start:
        raise DomainInvariantError("trip_start_date_out_of_window", field="start_date")


def _validate_travelers(value: object) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not MIN_TRAVELERS <= value <= MAX_TRAVELERS
    ):
        raise DomainInvariantError("travelers_invalid", field="travelers")


def _normalize_interests(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple) or len(value) > MAX_INTERESTS:
        raise DomainInvariantError("interests_invalid", field="interests")

    normalized = tuple(
        _normalize_required_text(
            interest,
            field="interests",
            min_length=1,
            max_length=MAX_SHORT_TEXT_LENGTH,
        )
        for interest in value
    )
    if len(set(normalized)) != len(normalized):
        raise DomainInvariantError("duplicate_interest", field="interests")
    return normalized


def _normalize_required_text(
    value: object,
    *,
    field: str,
    min_length: int,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise DomainInvariantError(f"{field}_type_invalid", field=field)
    normalized = value.strip()
    if not min_length <= len(normalized) <= max_length:
        raise DomainInvariantError(f"{field}_length_invalid", field=field)
    return normalized


def _normalize_optional_text(value: object, *, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise DomainInvariantError(f"{field}_type_invalid", field=field)
    normalized = value.strip()
    if len(normalized) > max_length:
        raise DomainInvariantError(f"{field}_length_invalid", field=field)
    return normalized


def _require_strict_date(value: object, *, field: str) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise DomainInvariantError("trip_date_type_invalid", field=field)
    return value
