"""Task-scoped provider attempt execution for planning orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from math import isfinite

from intelligent_travel_assistant.domain import (
    Provider,
    ProviderError,
    ProviderErrorCategory,
    ProviderErrorCode,
    ProviderErrorReason,
    ProviderOperation,
    ProviderResult,
    ProviderResultStatus,
    ResilienceDiagnosticCode,
    RetrySchedule,
    decide_retry,
    retry_schedule_for,
)

from .rate_limiting import PacedAttemptLimiter


class ProviderAttemptRuntimeErrorCode(StrEnum):
    RUNTIME_CLOSED = "provider_attempt_runtime_closed"
    TASK_DEADLINE_EXHAUSTED = "provider_attempt_task_deadline_exhausted"
    CLOCK_INVALID = "provider_attempt_clock_invalid"
    RESULT_INVALID = "provider_attempt_result_invalid"


class ProviderAttemptRuntimeError(RuntimeError):
    __slots__ = ("code",)

    def __init__(self, code: ProviderAttemptRuntimeErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ProviderAttemptRecord:
    sequence: int
    provider: Provider
    operation: ProviderOperation
    attempt_number: int
    status: ProviderResultStatus
    error_code: ProviderErrorCode | None


@dataclass(frozen=True, slots=True)
class ProviderAttemptSnapshot:
    records: tuple[ProviderAttemptRecord, ...]
    amap_extra_attempts: int
    qweather_extra_attempts: int
    task_extra_attempts: int
    active_executions: int
    closed: bool


@dataclass(frozen=True, slots=True)
class ProviderAttemptOutcome[T]:
    result: ProviderResult[T]
    attempts_started: int
    retry_diagnostic_code: ResilienceDiagnosticCode | None


class ProviderAttemptRuntime:
    """Explicit mutable budget owned by exactly one planning attempt."""

    __slots__ = (
        "_active_tasks",
        "_amap_extra_attempts",
        "_attempt_limiter",
        "_clock",
        "_closed",
        "_jitter",
        "_last_clock",
        "_qweather_extra_attempts",
        "_records",
        "_reservation_lock",
        "_sleeper",
        "_started_at",
        "_task_extra_attempts",
        "_task_timeout_seconds",
    )

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        sleeper: Callable[[float], Awaitable[None]],
        jitter: Callable[[], float],
        task_timeout_seconds: float,
        attempt_limiter: PacedAttemptLimiter | None = None,
    ) -> None:
        if not callable(clock):
            raise ValueError("provider_attempt_clock_invalid")
        if not callable(sleeper):
            raise ValueError("provider_attempt_sleeper_invalid")
        if not callable(jitter):
            raise ValueError("provider_attempt_jitter_invalid")
        if (
            not isinstance(task_timeout_seconds, int | float)
            or isinstance(task_timeout_seconds, bool)
            or not isfinite(task_timeout_seconds)
            or task_timeout_seconds <= 0
        ):
            raise ValueError("provider_attempt_task_timeout_invalid")
        self._clock = clock
        self._sleeper = sleeper
        self._jitter = jitter
        self._task_timeout_seconds = float(task_timeout_seconds)
        if attempt_limiter is not None and not isinstance(
            attempt_limiter,
            PacedAttemptLimiter,
        ):
            raise ValueError("provider_attempt_limiter_invalid")
        self._attempt_limiter = attempt_limiter
        self._last_clock = self._read_initial_clock()
        self._started_at = self._last_clock
        self._records: list[ProviderAttemptRecord] = []
        self._reservation_lock = asyncio.Lock()
        self._amap_extra_attempts = 0
        self._qweather_extra_attempts = 0
        self._task_extra_attempts = 0
        self._active_tasks: set[asyncio.Task[object]] = set()
        self._closed = False

    async def execute[T](
        self,
        *,
        provider: Provider,
        operation: ProviderOperation,
        call: Callable[[], Awaitable[ProviderResult[T]]],
    ) -> ProviderAttemptOutcome[T]:
        if self._closed:
            raise ProviderAttemptRuntimeError(ProviderAttemptRuntimeErrorCode.RUNTIME_CLOSED)
        if not callable(call):
            raise ValueError("provider_attempt_call_invalid")
        schedule = retry_schedule_for(provider, operation)
        current = asyncio.current_task()
        if current is None:
            raise ProviderAttemptRuntimeError(ProviderAttemptRuntimeErrorCode.RESULT_INVALID)
        task = current  # narrow the invariant for mypy and the active-task set
        self._active_tasks.add(task)
        attempts_started = 0
        last_result: ProviderResult[T] | None = None
        retry_pending = False

        def stopped_outcome(
            diagnostic_code: ResilienceDiagnosticCode,
        ) -> ProviderAttemptOutcome[T]:
            if last_result is None:
                result = ProviderResult[T](
                    ProviderResultStatus.UNAVAILABLE,
                    provider,
                    None,
                    None,
                    None,
                    (),
                    ProviderError(ProviderErrorCategory.TIMEOUT),
                    (),
                )
            else:
                result = last_result
            return ProviderAttemptOutcome(
                result,
                attempts_started,
                diagnostic_code,
            )

        try:
            while True:
                if self._closed:
                    raise ProviderAttemptRuntimeError(
                        ProviderAttemptRuntimeErrorCode.RUNTIME_CLOSED
                    )
                if task.cancelling():
                    raise asyncio.CancelledError
                if self._remaining_seconds() < schedule.attempt_timeout_seconds:
                    return stopped_outcome(ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED)
                if retry_pending:
                    async with self._reservation_lock:
                        if self._retry_budget_exhausted(provider, schedule):
                            return stopped_outcome(ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED)

                if self._attempt_limiter is not None:
                    slot = await self._attempt_limiter.acquire(
                        provider=provider,
                        operation=operation,
                        latest_start_at=(
                            self._started_at
                            + self._task_timeout_seconds
                            - schedule.attempt_timeout_seconds
                        ),
                    )
                    if not slot.granted:
                        return stopped_outcome(ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED)

                async with self._reservation_lock:
                    if self._closed:
                        raise ProviderAttemptRuntimeError(
                            ProviderAttemptRuntimeErrorCode.RUNTIME_CLOSED
                        )
                    if task.cancelling():
                        raise asyncio.CancelledError
                    if self._remaining_seconds() < schedule.attempt_timeout_seconds:
                        return stopped_outcome(ResilienceDiagnosticCode.RETRY_DEADLINE_EXHAUSTED)
                    if retry_pending:
                        if self._retry_budget_exhausted(provider, schedule):
                            return stopped_outcome(ResilienceDiagnosticCode.RETRY_BUDGET_EXHAUSTED)
                        self._reserve_extra_attempt(provider)
                    attempts_started += 1

                result = await self._run_attempt(
                    provider=provider,
                    call=call,
                    timeout_seconds=schedule.attempt_timeout_seconds,
                )
                last_result = result
                self._append_record(
                    provider=provider,
                    operation=operation,
                    attempt_number=attempts_started,
                    result=result,
                )
                if result.error is None:
                    return ProviderAttemptOutcome(result, attempts_started, None)

                jitter_seconds = 0.0
                if result.error.category in {
                    ProviderErrorCategory.TIMEOUT,
                    ProviderErrorCategory.SERVER,
                } or (
                    result.error.category is ProviderErrorCategory.RATE_LIMITED
                    and result.error.retry_after_seconds is not None
                ):
                    jitter_seconds = self._jitter()
                decision = decide_retry(
                    provider=provider,
                    operation=operation,
                    error=result.error,
                    jitter_seconds=jitter_seconds,
                    attempts_started=attempts_started,
                    provider_extra_attempts_used=self._provider_extra_attempts(provider),
                    task_extra_attempts_used=self._task_extra_attempts,
                    remaining_seconds=self._remaining_seconds(),
                    terminal=self._closed,
                    cancelled=False,
                )
                if not decision.should_retry:
                    diagnostic_code = decision.diagnostic_code
                    if (
                        diagnostic_code is None
                        and result.error.category is ProviderErrorCategory.TIMEOUT
                    ):
                        diagnostic_code = ResilienceDiagnosticCode.PROVIDER_ATTEMPT_TIMEOUT
                    return ProviderAttemptOutcome(
                        result,
                        attempts_started,
                        diagnostic_code,
                    )

                await self._sleeper(decision.delay_seconds)
                retry_pending = True
        except BaseException:
            await self._close_after_failure(exclude=task)
            raise
        finally:
            self._active_tasks.discard(task)

    async def close(self) -> None:
        if self._closed and not self._active_tasks:
            return
        self._closed = True
        current = asyncio.current_task()
        peers = tuple(task for task in self._active_tasks if task is not current)
        for task in peers:
            task.cancel()
        if peers:
            await asyncio.gather(*peers, return_exceptions=True)

    def snapshot(self) -> ProviderAttemptSnapshot:
        return ProviderAttemptSnapshot(
            tuple(self._records),
            self._amap_extra_attempts,
            self._qweather_extra_attempts,
            self._task_extra_attempts,
            len(self._active_tasks),
            self._closed,
        )

    async def _run_attempt[T](
        self,
        *,
        provider: Provider,
        call: Callable[[], Awaitable[ProviderResult[T]]],
        timeout_seconds: float,
    ) -> ProviderResult[T]:
        try:
            async with asyncio.timeout(timeout_seconds):
                result = await call()
        except TimeoutError:
            return ProviderResult(
                ProviderResultStatus.UNAVAILABLE,
                provider,
                None,
                None,
                None,
                (),
                ProviderError(ProviderErrorCategory.TIMEOUT),
                (),
            )
        if not isinstance(result, ProviderResult) or result.provider is not provider:
            raise ProviderAttemptRuntimeError(ProviderAttemptRuntimeErrorCode.RESULT_INVALID)
        return result

    async def _close_after_failure(self, *, exclude: asyncio.Task[object]) -> None:
        if self._closed:
            return
        self._closed = True
        peers = tuple(task for task in self._active_tasks if task is not exclude)
        for task in peers:
            task.cancel()
        if peers:
            await asyncio.gather(*peers, return_exceptions=True)

    def _append_record[T](
        self,
        *,
        provider: Provider,
        operation: ProviderOperation,
        attempt_number: int,
        result: ProviderResult[T],
    ) -> None:
        self._records.append(
            ProviderAttemptRecord(
                len(self._records) + 1,
                provider,
                operation,
                attempt_number,
                result.status,
                result.error.code if result.error is not None else None,
            )
        )

    def _provider_extra_attempts(self, provider: Provider) -> int:
        if provider is Provider.AMAP:
            return self._amap_extra_attempts
        if provider is Provider.QWEATHER:
            return self._qweather_extra_attempts
        return 0

    def _reserve_extra_attempt(self, provider: Provider) -> None:
        if provider is Provider.AMAP:
            self._amap_extra_attempts += 1
        elif provider is Provider.QWEATHER:
            self._qweather_extra_attempts += 1
        else:
            raise ProviderAttemptRuntimeError(ProviderAttemptRuntimeErrorCode.RESULT_INVALID)
        self._task_extra_attempts += 1

    def _retry_budget_exhausted(self, provider: Provider, schedule: RetrySchedule) -> bool:
        return (
            self._provider_extra_attempts(provider) >= schedule.provider_extra_attempt_limit
            or self._task_extra_attempts >= schedule.task_extra_attempt_limit
        )

    def _remaining_seconds(self) -> float:
        return max(
            0.0,
            self._task_timeout_seconds - (self._read_clock() - self._started_at),
        )

    def _read_initial_clock(self) -> float:
        value = self._clock()
        if not isinstance(value, int | float) or isinstance(value, bool) or not isfinite(value):
            raise ValueError("provider_attempt_clock_invalid")
        return float(value)

    def _read_clock(self) -> float:
        value = self._clock()
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not isfinite(value)
            or value < self._last_clock
        ):
            raise ProviderAttemptRuntimeError(ProviderAttemptRuntimeErrorCode.CLOCK_INVALID)
        self._last_clock = float(value)
        return self._last_clock


def parse_retry_after_seconds(value: str | None, *, now: datetime) -> float | None:
    """Normalize untrusted Retry-After without retaining the original header."""

    if (
        value is None
        or not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        return None
    if value.isascii() and value.isdecimal():
        delta_seconds = int(value)
        return float(delta_seconds) if 0 <= delta_seconds <= 2 else None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    date_seconds = max(0.0, (parsed - now).total_seconds())
    return date_seconds if date_seconds <= 2 else None


def provider_result_from_attempt_outcome[T](
    outcome: ProviderAttemptOutcome[T],
) -> ProviderResult[T]:
    """Attach only a stable runtime diagnostic to the existing internal error slot."""

    result = outcome.result
    diagnostic = outcome.retry_diagnostic_code
    if result.error is None or diagnostic is None:
        return result
    try:
        reason = ProviderErrorReason(diagnostic.value)
    except ValueError:
        return result
    error = ProviderError(
        result.error.category,
        reason,
        result.error.retry_after_seconds,
    )
    return ProviderResult(
        result.status,
        result.provider,
        result.data,
        result.fetched_at,
        result.valid_until,
        result.warnings,
        error,
        result.source_records,
    )
