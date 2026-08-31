"""Pure fake-clock contracts for the F-007 process-shared paced-slot limiter."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from intelligent_travel_assistant.application.tooling import (
    PacedAttemptLimiter,
    PacedAttemptLimiterError,
    PacedAttemptLimiterErrorCode,
)
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderOperation,
    attempt_pacing_policy_for,
)


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def limiter(
    clock: ManualClock,
    *,
    sleeper: Callable[[float], Awaitable[None]] | None = None,
) -> PacedAttemptLimiter:
    policy = attempt_pacing_policy_for(
        Provider.AMAP,
        ProviderOperation.CALCULATE_ROUTES,
    )
    assert policy is not None

    async def advancing_sleep(delay: float) -> None:
        clock.advance(delay)

    return PacedAttemptLimiter(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        policy=policy,
        clock=clock,
        sleeper=sleeper or advancing_sleep,
    )


@pytest.mark.anyio
async def test_paced_slots_have_no_burst_and_obey_half_open_windows() -> None:
    clock = ManualClock()
    attempt_limiter = limiter(clock)

    outcomes = [
        await attempt_limiter.acquire(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            latest_start_at=10.0,
        )
        for _ in range(5)
    ]

    starts = tuple(outcome.started_at for outcome in outcomes)
    assert starts == (0.0, 0.5, 1.0, 1.5, 2.0)
    assert all(outcome.granted and outcome.paced for outcome in outcomes)
    for start in (0.0, 0.25, 0.5, 1.0, 1.25):
        assert sum(value is not None and start <= value < start + 1.0 for value in starts) <= 2


@pytest.mark.anyio
async def test_idle_time_does_not_accumulate_burst_tokens() -> None:
    clock = ManualClock()
    attempt_limiter = limiter(clock)
    first = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=20.0,
    )
    clock.advance(10.0)
    second = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=20.0,
    )
    third = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=20.0,
    )

    assert (first.started_at, second.started_at, third.started_at) == (0.0, 10.0, 10.5)


@pytest.mark.anyio
async def test_concurrent_waiters_share_one_monotonic_timeline() -> None:
    clock = ManualClock()
    attempt_limiter = limiter(clock)

    outcomes = await asyncio.gather(
        *(
            attempt_limiter.acquire(
                provider=Provider.AMAP,
                operation=ProviderOperation.CALCULATE_ROUTES,
                latest_start_at=10.0,
            )
            for _ in range(4)
        )
    )

    assert tuple(outcome.started_at for outcome in outcomes) == (0.0, 0.5, 1.0, 1.5)


@pytest.mark.anyio
async def test_nonmatching_provider_or_operation_bypasses_clock_and_sleep() -> None:
    clock = ManualClock()
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)
        clock.advance(delay)

    attempt_limiter = limiter(clock, sleeper=sleeper)
    outcomes = (
        await attempt_limiter.acquire(
            provider=Provider.AMAP,
            operation=ProviderOperation.SEARCH_POIS,
            latest_start_at=-1.0,
        ),
        await attempt_limiter.acquire(
            provider=Provider.QWEATHER,
            operation=ProviderOperation.GET_WEATHER_FORECAST,
            latest_start_at=-1.0,
        ),
    )

    assert all(outcome.granted and not outcome.paced for outcome in outcomes)
    assert all(outcome.started_at is None for outcome in outcomes)
    assert clock.value == 0.0
    assert sleeps == []


@pytest.mark.anyio
async def test_deadline_equality_is_allowed_but_shortfall_is_refused_without_sleep() -> None:
    clock = ManualClock()
    sleeps: list[float] = []

    async def sleeper(delay: float) -> None:
        sleeps.append(delay)
        clock.advance(delay)

    attempt_limiter = limiter(clock, sleeper=sleeper)
    first = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.0,
    )
    refused = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.499999,
    )
    equality = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.5,
    )

    assert first.granted is True
    assert refused.granted is False
    assert refused.started_at is None
    assert equality.granted is True
    assert equality.started_at == 0.5
    assert sleeps == [0.5]


@pytest.mark.anyio
async def test_oversleep_is_refused_and_does_not_advance_next_slot() -> None:
    clock = ManualClock()

    async def oversleep(delay: float) -> None:
        clock.advance(delay + 0.1)

    attempt_limiter = limiter(clock, sleeper=oversleep)
    first = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.0,
    )
    refused = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.5,
    )
    recovered = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=0.6,
    )

    assert first.started_at == 0.0
    assert refused.granted is False
    assert clock.value == 0.6
    assert recovered.started_at == 0.6


@pytest.mark.anyio
async def test_cancelled_waiter_starts_nothing_and_limiter_remains_reusable() -> None:
    clock = ManualClock()
    entered_sleep = asyncio.Event()
    release_sleep = asyncio.Event()

    async def blocking_sleep(delay: float) -> None:
        entered_sleep.set()
        await release_sleep.wait()
        clock.advance(delay)

    attempt_limiter = limiter(clock, sleeper=blocking_sleep)
    first = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=10.0,
    )
    waiter = asyncio.create_task(
        attempt_limiter.acquire(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            latest_start_at=10.0,
        )
    )
    await entered_sleep.wait()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    release_sleep.set()
    recovered = await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=10.0,
    )

    assert first.started_at == 0.0
    assert recovered.started_at == 0.5


@pytest.mark.anyio
async def test_regressing_clock_fails_closed() -> None:
    clock = ManualClock(1.0)
    attempt_limiter = limiter(clock)
    await attempt_limiter.acquire(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        latest_start_at=10.0,
    )
    clock.value = 0.5

    with pytest.raises(PacedAttemptLimiterError) as error:
        await attempt_limiter.acquire(
            provider=Provider.AMAP,
            operation=ProviderOperation.CALCULATE_ROUTES,
            latest_start_at=10.0,
        )
    assert error.value.code is PacedAttemptLimiterErrorCode.CLOCK_INVALID
