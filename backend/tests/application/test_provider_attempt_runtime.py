"""Task-scoped F-005 provider attempt runtime and orchestration boundary."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.application.tooling import (
    PacedAttemptLimiter,
    ProviderAttemptOutcome,
    ProviderAttemptRuntime,
    ProviderAttemptRuntimeError,
    ProviderAttemptRuntimeErrorCode,
    parse_retry_after_seconds,
)
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderOperation,
    ProviderResult,
    ProviderResultStatus,
    ResilienceDiagnosticCode,
    SourceRecord,
    attempt_pacing_policy_for,
)

NOW = datetime(2026, 8, 21, 8, 0, tzinfo=UTC)
SOURCE_ID = UUID("f0050000-0000-4000-8000-000000000003")


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def unavailable(
    provider: Provider,
    category: ProviderErrorCategory,
    *,
    retry_after_seconds: float | None = None,
) -> ProviderResult[str]:
    return ProviderResult(
        ProviderResultStatus.UNAVAILABLE,
        provider,
        None,
        None,
        None,
        (),
        ProviderError(category, retry_after_seconds=retry_after_seconds),
        (),
    )


def ok(provider: Provider) -> ProviderResult[str]:
    valid_until = NOW + timedelta(minutes=10)
    source = SourceRecord(
        SOURCE_ID,
        provider,
        "synthetic_runtime",
        NOW,
        valid_until,
    )
    return ProviderResult(
        ProviderResultStatus.OK,
        provider,
        "ok",
        NOW,
        valid_until,
        (),
        None,
        (source,),
    )


def runtime(
    clock: ManualClock,
    *,
    task_timeout_seconds: float = 90.0,
    jitter_seconds: float = 0.2,
    sleeps: list[float] | None = None,
    attempt_limiter: PacedAttemptLimiter | None = None,
) -> ProviderAttemptRuntime:
    async def sleeper(delay: float) -> None:
        if sleeps is not None:
            sleeps.append(delay)
        clock.advance(delay)

    return ProviderAttemptRuntime(
        clock=clock,
        sleeper=sleeper,
        jitter=lambda: jitter_seconds,
        task_timeout_seconds=task_timeout_seconds,
        attempt_limiter=attempt_limiter,
    )


def route_limiter(clock: ManualClock, sleeps: list[float]) -> PacedAttemptLimiter:
    policy = attempt_pacing_policy_for(
        Provider.AMAP,
        ProviderOperation.CALCULATE_ROUTES,
    )
    assert policy is not None

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)
        clock.advance(delay)

    return PacedAttemptLimiter(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        policy=policy,
        clock=clock,
        sleeper=sleeper,
    )


def scripted_call[T](
    *results: ProviderResult[T],
) -> tuple[Callable[[], Awaitable[ProviderResult[T]]], list[int]]:
    observed: list[int] = []
    remaining = iter(results)

    async def call() -> ProviderResult[T]:
        observed.append(len(observed) + 1)
        return next(remaining)

    return call, observed


@pytest.mark.anyio
async def test_timeout_then_success_uses_one_retry_and_task_scoped_budget() -> None:
    clock = ManualClock()
    sleeps: list[float] = []
    attempt_runtime = runtime(clock, sleeps=sleeps)
    call, observed = scripted_call(
        unavailable(Provider.AMAP, ProviderErrorCategory.TIMEOUT),
        ok(Provider.AMAP),
    )

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=call,
    )

    assert outcome.result.status is ProviderResultStatus.OK
    assert outcome.attempts_started == 2
    assert outcome.retry_diagnostic_code is None
    assert observed == [1, 2]
    assert sleeps == [0.2]
    snapshot = attempt_runtime.snapshot()
    assert snapshot.amap_extra_attempts == 1
    assert snapshot.qweather_extra_attempts == 0
    assert snapshot.task_extra_attempts == 1
    assert snapshot.active_executions == 0
    assert tuple(record.attempt_number for record in snapshot.records) == (1, 2)


@pytest.mark.anyio
async def test_controlled_rate_limit_uses_safe_delay_without_retaining_header() -> None:
    clock = ManualClock()
    sleeps: list[float] = []
    attempt_runtime = runtime(clock, jitter_seconds=0.2, sleeps=sleeps)
    call, _ = scripted_call(
        unavailable(
            Provider.QWEATHER,
            ProviderErrorCategory.RATE_LIMITED,
            retry_after_seconds=1.9,
        ),
        ok(Provider.QWEATHER),
    )

    outcome = await attempt_runtime.execute(
        provider=Provider.QWEATHER,
        operation=ProviderOperation.GET_WEATHER_FORECAST,
        call=call,
    )

    assert outcome.result.status is ProviderResultStatus.OK
    assert sleeps == [2.0]
    assert "Retry-After" not in repr(attempt_runtime.snapshot())


@pytest.mark.anyio
async def test_consumed_retry_after_is_not_counted_twice_at_deadline_boundary() -> None:
    clock = ManualClock()
    sleeps: list[float] = []
    attempt_runtime = runtime(
        clock,
        task_timeout_seconds=8.0,
        jitter_seconds=0.2,
        sleeps=sleeps,
    )
    call, observed = scripted_call(
        unavailable(
            Provider.QWEATHER,
            ProviderErrorCategory.RATE_LIMITED,
            retry_after_seconds=1.9,
        ),
        ok(Provider.QWEATHER),
    )

    outcome = await attempt_runtime.execute(
        provider=Provider.QWEATHER,
        operation=ProviderOperation.GET_WEATHER_FORECAST,
        call=call,
    )

    assert outcome.result.status is ProviderResultStatus.OK
    assert outcome.attempts_started == 2
    assert observed == [1, 2]
    assert sleeps == [2.0]


@pytest.mark.anyio
async def test_deepseek_and_non_retryable_error_use_one_attempt() -> None:
    clock = ManualClock()
    attempt_runtime = runtime(clock)
    deepseek_call, deepseek_observed = scripted_call(
        unavailable(Provider.DEEPSEEK, ProviderErrorCategory.TIMEOUT)
    )
    auth_call, auth_observed = scripted_call(unavailable(Provider.AMAP, ProviderErrorCategory.AUTH))

    deepseek = await attempt_runtime.execute(
        provider=Provider.DEEPSEEK,
        operation=ProviderOperation.GENERATE_PLAN_CANDIDATE,
        call=deepseek_call,
    )
    auth = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.SEARCH_POIS,
        call=auth_call,
    )

    assert deepseek.attempts_started == 1
    assert auth.attempts_started == 1
    assert deepseek_observed == [1]
    assert auth_observed == [1]
    assert attempt_runtime.snapshot().task_extra_attempts == 0


@pytest.mark.anyio
async def test_provider_and_task_extra_budgets_are_shared_only_inside_one_runtime() -> None:
    clock = ManualClock()
    attempt_runtime = runtime(clock, jitter_seconds=0.0)

    for _ in range(3):
        call, observed = scripted_call(
            unavailable(Provider.AMAP, ProviderErrorCategory.SERVER),
            ok(Provider.AMAP),
        )
        outcome = await attempt_runtime.execute(
            provider=Provider.AMAP,
            operation=ProviderOperation.RESOLVE_CITY,
            call=call,
        )
        assert outcome.result.status is ProviderResultStatus.OK
        assert observed == [1, 2]

    blocked_call, blocked_observed = scripted_call(
        unavailable(Provider.AMAP, ProviderErrorCategory.SERVER)
    )
    blocked = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=blocked_call,
    )
    assert blocked.attempts_started == 1
    assert blocked.retry_diagnostic_code is ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED
    assert blocked_observed == [1]

    weather_call, weather_observed = scripted_call(
        unavailable(Provider.QWEATHER, ProviderErrorCategory.SERVER),
        ok(Provider.QWEATHER),
    )
    weather = await attempt_runtime.execute(
        provider=Provider.QWEATHER,
        operation=ProviderOperation.GET_WEATHER_FORECAST,
        call=weather_call,
    )
    assert weather.result.status is ProviderResultStatus.OK
    assert weather_observed == [1, 2]
    assert attempt_runtime.snapshot().task_extra_attempts == 4

    isolated_clock = ManualClock()
    isolated_runtime = runtime(isolated_clock, jitter_seconds=0.0)
    isolated_call, isolated_observed = scripted_call(
        unavailable(Provider.AMAP, ProviderErrorCategory.SERVER),
        ok(Provider.AMAP),
    )
    isolated = await isolated_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=isolated_call,
    )
    assert isolated.result.status is ProviderResultStatus.OK
    assert isolated_observed == [1, 2]
    assert isolated_runtime.snapshot().task_extra_attempts == 1


@pytest.mark.anyio
async def test_concurrent_retry_reservations_cannot_oversell_provider_or_task_budgets() -> None:
    waiting = 0
    release = asyncio.Event()
    calls = [0] * 6

    async def sleeper(_delay: float) -> None:
        nonlocal waiting
        waiting += 1
        if waiting == len(calls):
            release.set()
        await release.wait()

    attempt_runtime = ProviderAttemptRuntime(
        clock=lambda: 0.0,
        sleeper=sleeper,
        jitter=lambda: 0.0,
        task_timeout_seconds=90.0,
    )

    async def execute(index: int, provider: Provider) -> ProviderAttemptOutcome[str]:
        async def call() -> ProviderResult[str]:
            calls[index] += 1
            return unavailable(provider, ProviderErrorCategory.TIMEOUT)

        operation = (
            ProviderOperation.RESOLVE_CITY
            if provider is Provider.AMAP
            else ProviderOperation.GET_WEATHER_FORECAST
        )
        return await attempt_runtime.execute(
            provider=provider,
            operation=operation,
            call=call,
        )

    outcomes = await asyncio.gather(
        *(execute(index, Provider.AMAP) for index in range(4)),
        *(execute(index, Provider.QWEATHER) for index in range(4, 6)),
    )

    snapshot = attempt_runtime.snapshot()
    assert snapshot.amap_extra_attempts == 3
    assert snapshot.qweather_extra_attempts == 1
    assert snapshot.task_extra_attempts == 4
    assert sorted(calls) == [1, 1, 2, 2, 2, 2]
    assert sorted(outcome.attempts_started for outcome in outcomes) == [1, 1, 2, 2, 2, 2]


@pytest.mark.anyio
async def test_remaining_deadline_stops_retry_before_sleep_or_second_call() -> None:
    clock = ManualClock()
    sleeps: list[float] = []
    attempt_runtime = runtime(clock, task_timeout_seconds=6.1, sleeps=sleeps)
    call, observed = scripted_call(unavailable(Provider.AMAP, ProviderErrorCategory.TIMEOUT))

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=call,
    )

    assert observed == [1]
    assert sleeps == []
    assert outcome.retry_diagnostic_code is ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED
    assert attempt_runtime.snapshot().task_extra_attempts == 0


@pytest.mark.anyio
async def test_backoff_deadline_expiry_does_not_consume_unstarted_attempt_budget() -> None:
    clock = ManualClock()
    sleeps: list[float] = []

    async def oversleep(delay: float) -> None:
        sleeps.append(delay)
        clock.advance(delay + 0.1)

    attempt_runtime = ProviderAttemptRuntime(
        clock=clock,
        sleeper=oversleep,
        jitter=lambda: 0.2,
        task_timeout_seconds=6.2,
    )
    call, observed = scripted_call(unavailable(Provider.AMAP, ProviderErrorCategory.TIMEOUT))

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=call,
    )

    assert observed == [1]
    assert sleeps == [0.2]
    assert outcome.retry_diagnostic_code is ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED
    assert attempt_runtime.snapshot().task_extra_attempts == 0


@pytest.mark.anyio
async def test_exhausted_deadline_returns_safe_timeout_without_starting_http_attempt() -> None:
    clock = ManualClock()
    attempt_runtime = runtime(clock, task_timeout_seconds=5.0)
    call, observed = scripted_call(ok(Provider.AMAP))

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.RESOLVE_CITY,
        call=call,
    )

    assert observed == []
    assert outcome.attempts_started == 0
    assert outcome.result.error is not None
    assert outcome.result.error.category is ProviderErrorCategory.TIMEOUT
    assert outcome.retry_diagnostic_code is ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED
    assert attempt_runtime.snapshot().records == ()


@pytest.mark.anyio
async def test_two_task_runtimes_share_route_limiter_but_close_independently() -> None:
    clock = ManualClock()
    slot_sleeps: list[float] = []
    shared = route_limiter(clock, slot_sleeps)
    first_runtime = runtime(clock, attempt_limiter=shared)
    second_runtime = runtime(clock, attempt_limiter=shared)
    starts: list[float] = []

    async def route_call() -> ProviderResult[str]:
        starts.append(clock.value)
        return ok(Provider.AMAP)

    first = await first_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=route_call,
    )
    await first_runtime.close()
    second = await second_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=route_call,
    )

    assert first.result.status is ProviderResultStatus.OK
    assert second.result.status is ProviderResultStatus.OK
    assert starts == [0.0, 0.5]
    assert slot_sleeps == [0.5]
    assert first_runtime.snapshot().closed is True
    assert second_runtime.snapshot().closed is False


@pytest.mark.anyio
async def test_route_retry_backoff_precedes_shared_qps_slot() -> None:
    clock = ManualClock()
    retry_sleeps: list[float] = []
    slot_sleeps: list[float] = []
    shared = route_limiter(clock, slot_sleeps)
    attempt_runtime = runtime(
        clock,
        jitter_seconds=0.2,
        sleeps=retry_sleeps,
        attempt_limiter=shared,
    )
    starts: list[float] = []
    remaining = iter(
        (
            unavailable(Provider.AMAP, ProviderErrorCategory.TIMEOUT),
            ok(Provider.AMAP),
        )
    )

    async def route_call() -> ProviderResult[str]:
        starts.append(clock.value)
        return next(remaining)

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=route_call,
    )

    assert outcome.result.status is ProviderResultStatus.OK
    assert starts == [0.0, 0.5]
    assert retry_sleeps == [0.2]
    assert slot_sleeps == [0.3]
    assert attempt_runtime.snapshot().amap_extra_attempts == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("category", "retry_after_seconds", "expected_attempts"),
    (
        (ProviderErrorCategory.TIMEOUT, None, 2),
        (ProviderErrorCategory.SERVER, None, 2),
        (ProviderErrorCategory.RATE_LIMITED, 0.25, 2),
        (ProviderErrorCategory.RATE_LIMITED, None, 1),
        (ProviderErrorCategory.AUTH, None, 1),
        (ProviderErrorCategory.SCHEMA, None, 1),
        (ProviderErrorCategory.EMPTY_RESULT, None, 1),
        (ProviderErrorCategory.UNKNOWN, None, 1),
    ),
)
async def test_route_retry_matrix_paces_only_approved_second_attempts(
    category: ProviderErrorCategory,
    retry_after_seconds: float | None,
    expected_attempts: int,
) -> None:
    clock = ManualClock()
    retry_sleeps: list[float] = []
    slot_sleeps: list[float] = []
    shared = route_limiter(clock, slot_sleeps)
    attempt_runtime = runtime(
        clock,
        jitter_seconds=0.0,
        sleeps=retry_sleeps,
        attempt_limiter=shared,
    )
    failure = unavailable(
        Provider.AMAP,
        category,
        retry_after_seconds=retry_after_seconds,
    )
    call, observed = (
        scripted_call(failure, ok(Provider.AMAP))
        if expected_attempts == 2
        else scripted_call(failure)
    )

    outcome = await attempt_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=call,
    )

    assert outcome.attempts_started == expected_attempts
    assert observed == list(range(1, expected_attempts + 1))
    assert attempt_runtime.snapshot().task_extra_attempts == expected_attempts - 1
    if expected_attempts == 2:
        assert outcome.result.status is ProviderResultStatus.OK
        assert clock.value >= 0.5
    else:
        assert outcome.result.status is ProviderResultStatus.UNAVAILABLE
        assert slot_sleeps == []


@pytest.mark.anyio
async def test_route_slot_deadline_boundary_refuses_shortfall_without_http_or_budget() -> None:
    clock = ManualClock()
    slot_sleeps: list[float] = []
    shared = route_limiter(clock, slot_sleeps)
    seed_runtime = runtime(clock, attempt_limiter=shared)
    seed_call, _ = scripted_call(ok(Provider.AMAP))
    await seed_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=seed_call,
    )

    short_runtime = runtime(
        clock,
        task_timeout_seconds=6.499999,
        attempt_limiter=shared,
    )
    short_call, short_observed = scripted_call(ok(Provider.AMAP))
    refused = await short_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=short_call,
    )
    equality_runtime = runtime(
        clock,
        task_timeout_seconds=6.5,
        attempt_limiter=shared,
    )
    equality_call, equality_observed = scripted_call(ok(Provider.AMAP))
    allowed = await equality_runtime.execute(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        call=equality_call,
    )

    assert short_observed == []
    assert refused.attempts_started == 0
    assert refused.retry_diagnostic_code is ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED
    assert short_runtime.snapshot().task_extra_attempts == 0
    assert equality_observed == [1]
    assert allowed.result.status is ProviderResultStatus.OK
    assert slot_sleeps == [0.5]


@pytest.mark.anyio
async def test_runtime_closed_during_slot_wait_starts_no_retry_and_consumes_no_budget() -> None:
    clock = ManualClock()
    holder: list[ProviderAttemptRuntime] = []

    async def closing_slot_sleep(delay: float) -> None:
        clock.advance(delay)
        await holder[0].close()

    policy = attempt_pacing_policy_for(
        Provider.AMAP,
        ProviderOperation.CALCULATE_ROUTES,
    )
    assert policy is not None
    shared = PacedAttemptLimiter(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        policy=policy,
        clock=clock,
        sleeper=closing_slot_sleep,
    )
    attempt_runtime = runtime(
        clock,
        jitter_seconds=0.0,
        attempt_limiter=shared,
    )
    holder.append(attempt_runtime)
    call, observed = scripted_call(
        unavailable(Provider.AMAP, ProviderErrorCategory.TIMEOUT),
        ok(Provider.AMAP),
    )

    with pytest.raises(ProviderAttemptRuntimeError) as error:
        await attempt_runtime.execute(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            call=call,
        )

    assert error.value.code is ProviderAttemptRuntimeErrorCode.RUNTIME_CLOSED
    assert observed == [1]
    assert attempt_runtime.snapshot().task_extra_attempts == 0


@pytest.mark.anyio
async def test_close_cancels_and_drains_active_peers_then_rejects_new_execution() -> None:
    clock = ManualClock()
    attempt_runtime = runtime(clock)
    both_started = asyncio.Event()
    started = 0

    async def blocking_call() -> ProviderResult[str]:
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    first = asyncio.create_task(
        attempt_runtime.execute(
            provider=Provider.AMAP,
            operation=ProviderOperation.RESOLVE_CITY,
            call=blocking_call,
        )
    )
    second = asyncio.create_task(
        attempt_runtime.execute(
            provider=Provider.AMAP,
            operation=ProviderOperation.SEARCH_POIS,
            call=blocking_call,
        )
    )
    await both_started.wait()

    await attempt_runtime.close()

    assert first.cancelled()
    assert second.cancelled()
    assert attempt_runtime.snapshot().active_executions == 0
    assert attempt_runtime.snapshot().closed is True

    calls = 0

    async def forbidden_call() -> ProviderResult[str]:
        nonlocal calls
        calls += 1
        return ok(Provider.AMAP)

    with pytest.raises(ProviderAttemptRuntimeError) as error:
        await attempt_runtime.execute(
            provider=Provider.AMAP,
            operation=ProviderOperation.RESOLVE_CITY,
            call=forbidden_call,
        )
    assert error.value.code is ProviderAttemptRuntimeErrorCode.RUNTIME_CLOSED
    assert calls == 0


@pytest.mark.parametrize(
    ("value", "now", "expected"),
    [
        ("0", NOW, 0.0),
        ("2", NOW, 2.0),
        (format_datetime(NOW + timedelta(seconds=1), usegmt=True), NOW, 1.0),
        (format_datetime(NOW - timedelta(seconds=1), usegmt=True), NOW, 0.0),
        ("3", NOW, None),
        (format_datetime(NOW + timedelta(seconds=3), usegmt=True), NOW, None),
        ("1.5", NOW, None),
        (" 1", NOW, None),
        ("bad", NOW, None),
        (None, NOW, None),
        ("1", datetime(2026, 8, 21, 8, 0), None),
    ],
)
def test_retry_after_parser_accepts_only_bounded_delta_or_http_date(
    value: str | None,
    now: datetime,
    expected: float | None,
) -> None:
    assert parse_retry_after_seconds(value, now=now) == expected


def test_runtime_source_has_no_global_budget_context_variable_or_network_dependency() -> None:
    runtime_one = runtime(ManualClock())
    runtime_two = runtime(ManualClock())
    assert runtime_one.snapshot().task_extra_attempts == 0
    assert runtime_two.snapshot().task_extra_attempts == 0

    runtime_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "intelligent_travel_assistant"
        / "application"
        / "tooling"
        / "resilience.py"
    )
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"), filename=str(runtime_path))
    forbidden_roots = {
        "contextvars",
        "fastapi",
        "httpx",
        "openai",
        "os",
        "requests",
        "socket",
        "urllib",
    }
    observed_imports: list[str] = []
    observed_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules = (node.module,)
        else:
            modules = ()
        observed_imports.extend(
            module for module in modules if module.split(".", 1)[0] in forbidden_roots
        )
        if isinstance(node, ast.Call):
            rendered = ast.unparse(node.func).casefold()
            if rendered in {"asyncio.sleep", "time.sleep"} or any(
                forbidden in rendered for forbidden in ("getenv", "environ")
            ):
                observed_calls.append(rendered)

    assert observed_imports == []
    assert observed_calls == []
