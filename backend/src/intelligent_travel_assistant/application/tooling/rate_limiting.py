"""In-process paced-slot admission for narrowly scoped provider HTTP attempts."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from intelligent_travel_assistant.domain import (
    AttemptPacingPolicy,
    Provider,
    ProviderOperation,
    attempt_pacing_policy_for,
)


class PacedAttemptLimiterErrorCode(StrEnum):
    CLOCK_INVALID = "paced_attempt_limiter_clock_invalid"


class PacedAttemptLimiterError(RuntimeError):
    __slots__ = ("code",)

    def __init__(self, code: PacedAttemptLimiterErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class AttemptSlotOutcome:
    granted: bool
    paced: bool
    started_at: float | None


class PacedAttemptLimiter:
    """Serialize one provider-operation scope without accumulating burst tokens."""

    __slots__ = (
        "_clock",
        "_last_clock",
        "_lock",
        "_next_start_at",
        "_operation",
        "_policy",
        "_provider",
        "_sleeper",
    )

    def __init__(
        self,
        *,
        provider: Provider,
        operation: ProviderOperation,
        policy: AttemptPacingPolicy,
        clock: Callable[[], float],
        sleeper: Callable[[float], Awaitable[None]],
    ) -> None:
        if not isinstance(provider, Provider):
            raise ValueError("paced_attempt_limiter_provider_invalid")
        if not isinstance(operation, ProviderOperation):
            raise ValueError("paced_attempt_limiter_operation_invalid")
        if not isinstance(policy, AttemptPacingPolicy) or (
            attempt_pacing_policy_for(provider, operation) != policy
        ):
            raise ValueError("paced_attempt_limiter_policy_invalid")
        if not callable(clock):
            raise ValueError("paced_attempt_limiter_clock_invalid")
        if not callable(sleeper):
            raise ValueError("paced_attempt_limiter_sleeper_invalid")
        self._provider = provider
        self._operation = operation
        self._policy = policy
        self._clock = clock
        self._sleeper = sleeper
        self._last_clock = self._read_initial_clock()
        self._next_start_at = self._last_clock
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        *,
        provider: Provider,
        operation: ProviderOperation,
        latest_start_at: float,
    ) -> AttemptSlotOutcome:
        if provider is not self._provider or operation is not self._operation:
            return AttemptSlotOutcome(True, False, None)
        if (
            not isinstance(latest_start_at, int | float)
            or isinstance(latest_start_at, bool)
            or not isfinite(latest_start_at)
        ):
            raise ValueError("paced_attempt_limiter_deadline_invalid")

        async with self._lock:
            now = self._read_clock()
            slot_at = max(now, self._next_start_at)
            if slot_at > float(latest_start_at):
                return AttemptSlotOutcome(False, True, None)

            while now < slot_at:
                await self._sleeper(slot_at - now)
                now = self._read_clock()
                if now > float(latest_start_at):
                    return AttemptSlotOutcome(False, True, None)

            if now > float(latest_start_at):
                return AttemptSlotOutcome(False, True, None)
            self._next_start_at = now + self._policy.interval_seconds
            return AttemptSlotOutcome(True, True, now)

    def _read_initial_clock(self) -> float:
        value = self._clock()
        if not isinstance(value, int | float) or isinstance(value, bool) or not isfinite(value):
            raise ValueError("paced_attempt_limiter_clock_invalid")
        return float(value)

    def _read_clock(self) -> float:
        value = self._clock()
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not isfinite(value)
            or value < self._last_clock
        ):
            raise PacedAttemptLimiterError(PacedAttemptLimiterErrorCode.CLOCK_INVALID)
        self._last_clock = float(value)
        return self._last_clock
