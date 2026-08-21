"""Pure F-005 failure, freshness, retry schedule, and diagnostic decisions."""

from dataclasses import FrozenInstanceError

import pytest

from intelligent_travel_assistant.domain import (
    DataFreshness,
    DomainInvariantError,
    FactCriticality,
    FactUse,
    FailureDisposition,
    FreshnessDecision,
    PlanDisposition,
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderOperation,
    ResilienceDiagnosticCode,
    RetryDecision,
    decide_freshness,
    decide_provider_failure,
    decide_retry,
    retry_schedule_for,
)


@pytest.mark.parametrize(
    ("provider", "operation", "max_attempts", "provider_extra_limit", "timeout"),
    [
        (Provider.AMAP, ProviderOperation.RESOLVE_CITY, 2, 3, 6.0),
        (Provider.AMAP, ProviderOperation.SEARCH_POIS, 2, 3, 6.0),
        (Provider.AMAP, ProviderOperation.CALCULATE_ROUTES, 2, 3, 6.0),
        (Provider.QWEATHER, ProviderOperation.GET_WEATHER_FORECAST, 2, 1, 6.0),
        (
            Provider.QWEATHER,
            ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
            2,
            1,
            6.0,
        ),
        (Provider.DEEPSEEK, ProviderOperation.GENERATE_PLAN_CANDIDATE, 1, 0, 35.0),
        (Provider.DEEPSEEK, ProviderOperation.REPAIR_PLAN_CANDIDATE, 1, 0, 35.0),
    ],
)
def test_retry_schedule_is_provider_and_operation_specific(
    provider: Provider,
    operation: ProviderOperation,
    max_attempts: int,
    provider_extra_limit: int,
    timeout: float,
) -> None:
    schedule = retry_schedule_for(provider, operation)
    assert schedule.max_http_attempts == max_attempts
    assert schedule.provider_extra_attempt_limit == provider_extra_limit
    assert schedule.task_extra_attempt_limit == 4
    assert schedule.attempt_timeout_seconds == timeout


def test_provider_operation_mismatch_fails_closed() -> None:
    with pytest.raises(DomainInvariantError) as error:
        retry_schedule_for(Provider.AMAP, ProviderOperation.GET_WEATHER_FORECAST)
    assert error.value.code == "provider_operation_invalid"


@pytest.mark.parametrize(
    ("category", "jitter", "expected_delay"),
    [
        (ProviderErrorCategory.TIMEOUT, 0.0, 0.0),
        (ProviderErrorCategory.TIMEOUT, 0.2, 0.2),
        (ProviderErrorCategory.SERVER, 0.125, 0.125),
    ],
)
def test_amap_timeout_and_server_schedule_one_retry_with_full_jitter(
    category: ProviderErrorCategory,
    jitter: float,
    expected_delay: float,
) -> None:
    decision = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.SEARCH_POIS,
        error=ProviderError(category),
        jitter_seconds=jitter,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=6.2,
    )
    assert decision == RetryDecision(True, expected_delay, None)


@pytest.mark.parametrize(
    ("retry_after", "jitter", "expected_delay"),
    [(0.0, 0.2, 0.2), (1.5, 0.125, 1.625), (2.0, 0.2, 2.0)],
)
def test_controlled_rate_limit_uses_retry_after_plus_jitter_capped_at_two_seconds(
    retry_after: float,
    jitter: float,
    expected_delay: float,
) -> None:
    decision = decide_retry(
        provider=Provider.QWEATHER,
        operation=ProviderOperation.GET_WEATHER_FORECAST,
        error=ProviderError(
            ProviderErrorCategory.RATE_LIMITED,
            retry_after_seconds=retry_after,
        ),
        jitter_seconds=jitter,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=8.0,
    )
    assert decision == RetryDecision(True, expected_delay, None)


def test_uncontrolled_rate_limit_does_not_retry_and_uses_only_safe_diagnostic() -> None:
    decision = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        error=ProviderError(ProviderErrorCategory.RATE_LIMITED),
        jitter_seconds=0.1,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=10.0,
    )
    assert decision == RetryDecision(
        False,
        0.0,
        ResilienceDiagnosticCode.RETRY_AFTER_INVALID,
    )


@pytest.mark.parametrize(
    "category",
    [
        ProviderErrorCategory.AUTH,
        ProviderErrorCategory.SCHEMA,
        ProviderErrorCategory.EMPTY_RESULT,
        ProviderErrorCategory.UNKNOWN,
    ],
)
def test_non_retryable_errors_never_schedule_retry(
    category: ProviderErrorCategory,
) -> None:
    decision = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        error=ProviderError(category),
        jitter_seconds=0.2,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=20.0,
    )
    assert decision == RetryDecision(False, 0.0, None)


def test_deepseek_has_zero_automatic_transport_retry() -> None:
    decision = decide_retry(
        provider=Provider.DEEPSEEK,
        operation=ProviderOperation.GENERATE_PLAN_CANDIDATE,
        error=ProviderError(ProviderErrorCategory.TIMEOUT),
        jitter_seconds=0.1,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=90.0,
    )
    assert decision == RetryDecision(False, 0.0, None)


@pytest.mark.parametrize(
    ("attempts_started", "provider_used", "task_used"),
    [(2, 0, 0), (1, 3, 3), (1, 0, 4)],
)
def test_attempt_or_extra_budget_exhaustion_stops_retry(
    attempts_started: int,
    provider_used: int,
    task_used: int,
) -> None:
    decision = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        error=ProviderError(ProviderErrorCategory.TIMEOUT),
        jitter_seconds=0.1,
        attempts_started=attempts_started,
        provider_extra_attempts_used=provider_used,
        task_extra_attempts_used=task_used,
        remaining_seconds=20.0,
    )
    assert decision == RetryDecision(
        False,
        0.0,
        ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED,
    )


def test_remaining_deadline_must_cover_delay_and_full_attempt_timeout() -> None:
    allowed = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        error=ProviderError(ProviderErrorCategory.TIMEOUT),
        jitter_seconds=0.2,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=6.2,
    )
    refused = decide_retry(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        error=ProviderError(ProviderErrorCategory.TIMEOUT),
        jitter_seconds=0.2,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=6.199999,
    )
    assert allowed.should_retry is True
    assert refused == RetryDecision(
        False,
        0.0,
        ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED,
    )


@pytest.mark.parametrize(("terminal", "cancelled"), [(True, False), (False, True)])
def test_terminal_or_cancelled_context_starts_no_retry(
    terminal: bool,
    cancelled: bool,
) -> None:
    decision = decide_retry(
        provider=Provider.QWEATHER,
        operation=ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
        error=ProviderError(ProviderErrorCategory.SERVER),
        jitter_seconds=0.1,
        attempts_started=1,
        provider_extra_attempts_used=0,
        task_extra_attempts_used=0,
        remaining_seconds=20.0,
        terminal=terminal,
        cancelled=cancelled,
    )
    assert decision == RetryDecision(False, 0.0, None)


@pytest.mark.parametrize("jitter", [-0.000001, 0.200001, float("nan"), True])
def test_retry_rejects_invalid_injected_jitter(jitter: object) -> None:
    with pytest.raises(DomainInvariantError) as error:
        decide_retry(
            provider=Provider.AMAP,
            operation=ProviderOperation.RESOLVE_CITY,
            error=ProviderError(ProviderErrorCategory.TIMEOUT),
            jitter_seconds=jitter,  # type: ignore[arg-type]
            attempts_started=1,
            provider_extra_attempts_used=0,
            task_extra_attempts_used=0,
            remaining_seconds=20.0,
        )
    assert error.value.code == "retry_jitter_invalid"


@pytest.mark.parametrize(
    "overrides",
    [
        {"attempts_started": 0},
        {"provider_extra_attempts_used": True},
        {"task_extra_attempts_used": -1},
        {"remaining_seconds": float("nan")},
        {"terminal": 1},
        {"cancelled": "yes"},
    ],
)
def test_retry_context_rejects_invalid_counts_time_or_flags(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "provider": Provider.AMAP,
        "operation": ProviderOperation.RESOLVE_CITY,
        "error": ProviderError(ProviderErrorCategory.TIMEOUT),
        "jitter_seconds": 0.1,
        "attempts_started": 1,
        "provider_extra_attempts_used": 0,
        "task_extra_attempts_used": 0,
        "remaining_seconds": 20.0,
        "terminal": False,
        "cancelled": False,
    }
    values.update(overrides)
    with pytest.raises(DomainInvariantError) as error:
        decide_retry(**values)  # type: ignore[arg-type]
    assert error.value.code == "retry_context_invalid"


@pytest.mark.parametrize(
    ("operation", "freshness", "criticality", "expected"),
    [
        (
            ProviderOperation.CALCULATE_ROUTES,
            DataFreshness.FRESH,
            FactCriticality.REQUIRED,
            FreshnessDecision(FactUse.USE, PlanDisposition.CONTINUE, None),
        ),
        (
            ProviderOperation.CALCULATE_ROUTES,
            DataFreshness.STALE,
            FactCriticality.REQUIRED,
            FreshnessDecision(
                FactUse.REJECT,
                PlanDisposition.FAILED,
                ResilienceDiagnosticCode.ROUTE_SOURCE_STALE,
            ),
        ),
        (
            ProviderOperation.CALCULATE_ROUTES,
            DataFreshness.UNKNOWN_VALIDITY,
            FactCriticality.REQUIRED,
            FreshnessDecision(FactUse.USE, PlanDisposition.PARTIAL, None),
        ),
        (
            ProviderOperation.GET_WEATHER_FORECAST,
            DataFreshness.STALE,
            FactCriticality.OPTIONAL,
            FreshnessDecision(
                FactUse.OMIT,
                PlanDisposition.PARTIAL,
                ResilienceDiagnosticCode.WEATHER_FORECAST_STALE,
            ),
        ),
        (
            ProviderOperation.GET_CURRENT_WEATHER_ALERTS,
            DataFreshness.STALE,
            FactCriticality.OPTIONAL,
            FreshnessDecision(
                FactUse.OMIT,
                PlanDisposition.PARTIAL,
                ResilienceDiagnosticCode.WEATHER_ALERT_STALE,
            ),
        ),
        (
            ProviderOperation.SEARCH_POIS,
            DataFreshness.STALE,
            FactCriticality.REQUIRED,
            FreshnessDecision(
                FactUse.USE,
                PlanDisposition.PARTIAL,
                ResilienceDiagnosticCode.LOCATION_SOURCE_STALE,
            ),
        ),
        (
            ProviderOperation.RESOLVE_CITY,
            DataFreshness.UNKNOWN_VALIDITY,
            FactCriticality.REQUIRED,
            FreshnessDecision(FactUse.USE, PlanDisposition.PARTIAL, None),
        ),
        (
            ProviderOperation.GENERATE_PLAN_CANDIDATE,
            DataFreshness.STALE,
            FactCriticality.REQUIRED,
            FreshnessDecision(FactUse.REJECT, PlanDisposition.FAILED, None),
        ),
    ],
)
def test_freshness_decision_is_capability_and_criticality_specific(
    operation: ProviderOperation,
    freshness: DataFreshness,
    criticality: FactCriticality,
    expected: FreshnessDecision,
) -> None:
    assert decide_freshness(operation, freshness, criticality) == expected


@pytest.mark.parametrize(
    ("criticality", "expected"),
    [
        (FactCriticality.REQUIRED, FailureDisposition.FAILED),
        (FactCriticality.OPTIONAL, FailureDisposition.PARTIAL),
    ],
)
@pytest.mark.parametrize("category", list(ProviderErrorCategory))
def test_provider_failure_can_only_be_failed_or_partial(
    category: ProviderErrorCategory,
    criticality: FactCriticality,
    expected: FailureDisposition,
) -> None:
    assert decide_provider_failure(ProviderError(category), criticality) is expected


def test_resilience_decisions_are_immutable_and_diagnostics_are_closed() -> None:
    decision = RetryDecision(
        False,
        0.0,
        ResilienceDiagnosticCode.PROVIDER_ATTEMPT_TIMEOUT,
    )
    with pytest.raises(FrozenInstanceError):
        decision.delay_seconds = 1.0  # type: ignore[misc]

    assert {item.value for item in ResilienceDiagnosticCode} == {
        "provider_attempt_timeout",
        "retry_budget_exhausted",
        "retry_deadline_exhausted",
        "retry_after_invalid",
        "route_source_stale",
        "location_source_stale",
        "weather_forecast_stale",
        "weather_alert_stale",
    }


@pytest.mark.parametrize(
    ("fact_use", "disposition", "diagnostic_code"),
    [
        (FactUse.REJECT, PlanDisposition.CONTINUE, None),
        (
            FactUse.USE,
            PlanDisposition.CONTINUE,
            ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED,
        ),
    ],
)
def test_freshness_decision_rejects_impossible_or_non_freshness_combinations(
    fact_use: FactUse,
    disposition: PlanDisposition,
    diagnostic_code: ResilienceDiagnosticCode | None,
) -> None:
    with pytest.raises(DomainInvariantError, match="freshness_decision_invalid"):
        FreshnessDecision(fact_use, disposition, diagnostic_code)


def test_retry_context_rejects_provider_attempts_above_task_total() -> None:
    with pytest.raises(DomainInvariantError, match="retry_context_invalid"):
        decide_retry(
            provider=Provider.AMAP,
            operation=ProviderOperation.RESOLVE_CITY,
            error=ProviderError(ProviderErrorCategory.TIMEOUT),
            jitter_seconds=0.0,
            attempts_started=1,
            provider_extra_attempts_used=1,
            task_extra_attempts_used=0,
            remaining_seconds=90.0,
        )
