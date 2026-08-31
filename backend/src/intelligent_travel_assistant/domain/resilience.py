"""Pure F-005 resilience, freshness-use, and retry-schedule policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Final

from intelligent_travel_assistant.domain.foundation import DomainInvariantError, Provider
from intelligent_travel_assistant.domain.provider_result import (
    DataFreshness,
    ProviderError,
    ProviderErrorCategory,
)


class ProviderOperation(StrEnum):
    RESOLVE_CITY = "resolve_city"
    SEARCH_POIS = "search_pois"
    GET_WEATHER_FORECAST = "get_weather_forecast"
    GET_CURRENT_WEATHER_ALERTS = "get_current_weather_alerts"
    CALCULATE_ROUTES = "calculate_routes"
    GENERATE_PLAN_CANDIDATE = "generate_plan_candidate"
    REPAIR_PLAN_CANDIDATE = "repair_plan_candidate"


class FactCriticality(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class FactUse(StrEnum):
    USE = "use"
    OMIT = "omit"
    REJECT = "reject"


class PlanDisposition(StrEnum):
    CONTINUE = "continue"
    PARTIAL = "partial"
    FAILED = "failed"


class FailureDisposition(StrEnum):
    PARTIAL = "partial"
    FAILED = "failed"


class ResilienceDiagnosticCode(StrEnum):
    PROVIDER_ATTEMPT_TIMEOUT = "provider_attempt_timeout"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    RETRY_DEADLINE_EXHAUSTED = "retry_deadline_exhausted"
    RETRY_AFTER_INVALID = "retry_after_invalid"
    ROUTE_SOURCE_STALE = "route_source_stale"
    LOCATION_SOURCE_STALE = "location_source_stale"
    WEATHER_FORECAST_STALE = "weather_forecast_stale"
    WEATHER_ALERT_STALE = "weather_alert_stale"


@dataclass(frozen=True, slots=True)
class AttemptPacingPolicy:
    interval_seconds: float

    def __post_init__(self) -> None:
        if (
            not isinstance(self.interval_seconds, int | float)
            or isinstance(self.interval_seconds, bool)
            or not isfinite(self.interval_seconds)
            or self.interval_seconds <= 0
        ):
            raise DomainInvariantError(
                "attempt_pacing_policy_invalid",
                field="interval_seconds",
            )
        object.__setattr__(self, "interval_seconds", float(self.interval_seconds))


_FRESHNESS_DECISION_COMBINATIONS: Final = frozenset(
    {
        (FactUse.USE, PlanDisposition.CONTINUE, None),
        (FactUse.USE, PlanDisposition.PARTIAL, None),
        (
            FactUse.USE,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.LOCATION_SOURCE_STALE,
        ),
        (FactUse.OMIT, PlanDisposition.PARTIAL, None),
        (
            FactUse.OMIT,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.ROUTE_SOURCE_STALE,
        ),
        (
            FactUse.OMIT,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.WEATHER_FORECAST_STALE,
        ),
        (
            FactUse.OMIT,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.WEATHER_ALERT_STALE,
        ),
        (FactUse.REJECT, PlanDisposition.FAILED, None),
        (
            FactUse.REJECT,
            PlanDisposition.FAILED,
            ResilienceDiagnosticCode.ROUTE_SOURCE_STALE,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class RetrySchedule:
    max_http_attempts: int
    provider_extra_attempt_limit: int
    task_extra_attempt_limit: int
    attempt_timeout_seconds: float

    def __post_init__(self) -> None:
        for field, value in (
            ("max_http_attempts", self.max_http_attempts),
            ("provider_extra_attempt_limit", self.provider_extra_attempt_limit),
            ("task_extra_attempt_limit", self.task_extra_attempt_limit),
        ):
            if type(value) is not int or value < 0:
                raise DomainInvariantError("retry_schedule_invalid", field=field)
        if self.max_http_attempts < 1:
            raise DomainInvariantError("retry_schedule_invalid", field="max_http_attempts")
        if (
            not isinstance(self.attempt_timeout_seconds, int | float)
            or isinstance(self.attempt_timeout_seconds, bool)
            or not isfinite(self.attempt_timeout_seconds)
            or self.attempt_timeout_seconds <= 0
        ):
            raise DomainInvariantError(
                "retry_schedule_invalid",
                field="attempt_timeout_seconds",
            )
        object.__setattr__(
            self,
            "attempt_timeout_seconds",
            float(self.attempt_timeout_seconds),
        )


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: float
    diagnostic_code: ResilienceDiagnosticCode | None

    def __post_init__(self) -> None:
        if not isinstance(self.should_retry, bool):
            raise DomainInvariantError("retry_decision_invalid", field="should_retry")
        if (
            not isinstance(self.delay_seconds, int | float)
            or isinstance(self.delay_seconds, bool)
            or not isfinite(self.delay_seconds)
            or not 0 <= self.delay_seconds <= 2
        ):
            raise DomainInvariantError("retry_decision_invalid", field="delay_seconds")
        if self.diagnostic_code is not None and not isinstance(
            self.diagnostic_code,
            ResilienceDiagnosticCode,
        ):
            raise DomainInvariantError("retry_decision_invalid", field="diagnostic_code")
        if self.should_retry and self.diagnostic_code is not None:
            raise DomainInvariantError("retry_decision_invalid", field="diagnostic_code")
        if not self.should_retry and self.delay_seconds != 0:
            raise DomainInvariantError("retry_decision_invalid", field="delay_seconds")
        object.__setattr__(self, "delay_seconds", float(self.delay_seconds))


@dataclass(frozen=True, slots=True)
class FreshnessDecision:
    fact_use: FactUse
    disposition: PlanDisposition
    diagnostic_code: ResilienceDiagnosticCode | None

    def __post_init__(self) -> None:
        if not isinstance(self.fact_use, FactUse):
            raise DomainInvariantError("freshness_decision_invalid", field="fact_use")
        if not isinstance(self.disposition, PlanDisposition):
            raise DomainInvariantError("freshness_decision_invalid", field="disposition")
        if self.diagnostic_code is not None and not isinstance(
            self.diagnostic_code,
            ResilienceDiagnosticCode,
        ):
            raise DomainInvariantError("freshness_decision_invalid", field="diagnostic_code")
        if (self.fact_use, self.disposition, self.diagnostic_code) not in (
            _FRESHNESS_DECISION_COMBINATIONS
        ):
            raise DomainInvariantError("freshness_decision_invalid", field="disposition")


_RETRY_SCHEDULES: Final = MappingProxyType(
    {
        (Provider.AMAP, ProviderOperation.RESOLVE_CITY): RetrySchedule(2, 3, 4, 6.0),
        (Provider.AMAP, ProviderOperation.SEARCH_POIS): RetrySchedule(2, 3, 4, 6.0),
        (Provider.AMAP, ProviderOperation.CALCULATE_ROUTES): RetrySchedule(2, 3, 4, 6.0),
        (Provider.QWEATHER, ProviderOperation.GET_WEATHER_FORECAST): RetrySchedule(
            2,
            1,
            4,
            6.0,
        ),
        (Provider.QWEATHER, ProviderOperation.GET_CURRENT_WEATHER_ALERTS): RetrySchedule(
            2,
            1,
            4,
            6.0,
        ),
        (Provider.DEEPSEEK, ProviderOperation.GENERATE_PLAN_CANDIDATE): RetrySchedule(
            1,
            0,
            4,
            35.0,
        ),
        (Provider.DEEPSEEK, ProviderOperation.REPAIR_PLAN_CANDIDATE): RetrySchedule(
            1,
            0,
            4,
            35.0,
        ),
    }
)
_ATTEMPT_PACING_POLICIES: Final = MappingProxyType(
    {
        (Provider.AMAP, ProviderOperation.CALCULATE_ROUTES): AttemptPacingPolicy(0.5),
    }
)
_LOCATION_OPERATIONS: Final = frozenset(
    {
        ProviderOperation.RESOLVE_CITY,
        ProviderOperation.SEARCH_POIS,
    }
)
_MODEL_OPERATIONS: Final = frozenset(
    {
        ProviderOperation.GENERATE_PLAN_CANDIDATE,
        ProviderOperation.REPAIR_PLAN_CANDIDATE,
    }
)
_RETRYABLE_CATEGORIES: Final = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.RATE_LIMITED,
        ProviderErrorCategory.SERVER,
    }
)


def retry_schedule_for(
    provider: Provider,
    operation: ProviderOperation,
) -> RetrySchedule:
    if not isinstance(provider, Provider):
        raise DomainInvariantError("provider_invalid", field="provider")
    if not isinstance(operation, ProviderOperation):
        raise DomainInvariantError("provider_operation_invalid", field="operation")
    schedule = _RETRY_SCHEDULES.get((provider, operation))
    if schedule is None:
        raise DomainInvariantError("provider_operation_invalid", field="operation")
    return schedule


def attempt_pacing_policy_for(
    provider: Provider,
    operation: ProviderOperation,
) -> AttemptPacingPolicy | None:
    if not isinstance(provider, Provider):
        raise DomainInvariantError("attempt_pacing_scope_invalid", field="provider")
    if not isinstance(operation, ProviderOperation):
        raise DomainInvariantError("attempt_pacing_scope_invalid", field="operation")
    return _ATTEMPT_PACING_POLICIES.get((provider, operation))


def decide_retry(
    *,
    provider: Provider,
    operation: ProviderOperation,
    error: ProviderError,
    jitter_seconds: float,
    attempts_started: int,
    provider_extra_attempts_used: int,
    task_extra_attempts_used: int,
    remaining_seconds: float,
    terminal: bool = False,
    cancelled: bool = False,
) -> RetryDecision:
    schedule = retry_schedule_for(provider, operation)
    if not isinstance(error, ProviderError):
        raise DomainInvariantError("provider_error_invalid", field="error")
    _require_jitter(jitter_seconds)
    _require_positive_int(attempts_started, field="attempts_started")
    _require_nonnegative_int(
        provider_extra_attempts_used,
        field="provider_extra_attempts_used",
    )
    _require_nonnegative_int(task_extra_attempts_used, field="task_extra_attempts_used")
    if task_extra_attempts_used < provider_extra_attempts_used:
        raise DomainInvariantError(
            "retry_context_invalid",
            field="task_extra_attempts_used",
        )
    _require_nonnegative_finite(remaining_seconds, field="remaining_seconds")
    if not isinstance(terminal, bool):
        raise DomainInvariantError("retry_context_invalid", field="terminal")
    if not isinstance(cancelled, bool):
        raise DomainInvariantError("retry_context_invalid", field="cancelled")

    if terminal or cancelled:
        return RetryDecision(False, 0.0, None)
    if schedule.max_http_attempts == 1 or error.category not in _RETRYABLE_CATEGORIES:
        return RetryDecision(False, 0.0, None)
    if error.category is ProviderErrorCategory.RATE_LIMITED:
        if error.retry_after_seconds is None:
            return RetryDecision(
                False,
                0.0,
                ResilienceDiagnosticCode.RETRY_AFTER_INVALID,
            )
        delay_seconds = min(2.0, error.retry_after_seconds + float(jitter_seconds))
    else:
        delay_seconds = float(jitter_seconds)

    if (
        attempts_started >= schedule.max_http_attempts
        or provider_extra_attempts_used >= schedule.provider_extra_attempt_limit
        or task_extra_attempts_used >= schedule.task_extra_attempt_limit
    ):
        return RetryDecision(
            False,
            0.0,
            ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED,
        )
    required_seconds = delay_seconds + schedule.attempt_timeout_seconds
    if remaining_seconds < required_seconds:
        return RetryDecision(
            False,
            0.0,
            ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED,
        )
    return RetryDecision(True, delay_seconds, None)


def decide_freshness(
    operation: ProviderOperation,
    freshness: DataFreshness,
    criticality: FactCriticality,
) -> FreshnessDecision:
    if not isinstance(operation, ProviderOperation):
        raise DomainInvariantError("provider_operation_invalid", field="operation")
    if not isinstance(freshness, DataFreshness):
        raise DomainInvariantError("data_freshness_invalid", field="freshness")
    if not isinstance(criticality, FactCriticality):
        raise DomainInvariantError("fact_criticality_invalid", field="criticality")
    if freshness is DataFreshness.FRESH:
        return FreshnessDecision(FactUse.USE, PlanDisposition.CONTINUE, None)
    if freshness is DataFreshness.UNKNOWN_VALIDITY:
        return FreshnessDecision(FactUse.USE, PlanDisposition.PARTIAL, None)
    if operation is ProviderOperation.CALCULATE_ROUTES:
        return FreshnessDecision(
            FactUse.REJECT if criticality is FactCriticality.REQUIRED else FactUse.OMIT,
            (
                PlanDisposition.FAILED
                if criticality is FactCriticality.REQUIRED
                else PlanDisposition.PARTIAL
            ),
            ResilienceDiagnosticCode.ROUTE_SOURCE_STALE,
        )
    if operation is ProviderOperation.GET_WEATHER_FORECAST:
        return FreshnessDecision(
            FactUse.OMIT,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.WEATHER_FORECAST_STALE,
        )
    if operation is ProviderOperation.GET_CURRENT_WEATHER_ALERTS:
        return FreshnessDecision(
            FactUse.OMIT,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.WEATHER_ALERT_STALE,
        )
    if operation in _LOCATION_OPERATIONS:
        return FreshnessDecision(
            FactUse.USE,
            PlanDisposition.PARTIAL,
            ResilienceDiagnosticCode.LOCATION_SOURCE_STALE,
        )
    if operation in _MODEL_OPERATIONS:
        return FreshnessDecision(
            FactUse.REJECT if criticality is FactCriticality.REQUIRED else FactUse.OMIT,
            (
                PlanDisposition.FAILED
                if criticality is FactCriticality.REQUIRED
                else PlanDisposition.PARTIAL
            ),
            None,
        )
    raise DomainInvariantError("provider_operation_invalid", field="operation")


def decide_provider_failure(
    error: ProviderError,
    criticality: FactCriticality,
) -> FailureDisposition:
    if not isinstance(error, ProviderError):
        raise DomainInvariantError("provider_error_invalid", field="error")
    if not isinstance(criticality, FactCriticality):
        raise DomainInvariantError("fact_criticality_invalid", field="criticality")
    if criticality is FactCriticality.REQUIRED:
        return FailureDisposition.FAILED
    return FailureDisposition.PARTIAL


def _require_jitter(value: object) -> None:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
        or not 0 <= value <= 0.2
    ):
        raise DomainInvariantError("retry_jitter_invalid", field="jitter_seconds")


def _require_positive_int(value: object, *, field: str) -> None:
    if type(value) is not int or value < 1:
        raise DomainInvariantError("retry_context_invalid", field=field)


def _require_nonnegative_int(value: object, *, field: str) -> None:
    if type(value) is not int or value < 0:
        raise DomainInvariantError("retry_context_invalid", field=field)


def _require_nonnegative_finite(value: object, *, field: str) -> None:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0
    ):
        raise DomainInvariantError("retry_context_invalid", field=field)
