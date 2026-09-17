"""Deterministic pre-call governance with an injected monotonic clock."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from threading import RLock
from types import MappingProxyType
from typing import Any, Final, Literal
from uuid import UUID, uuid4

from intelligent_travel_assistant.application.ports import PlanningToolName
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    Provider,
    ProviderErrorCode,
    ProviderOperation,
    ProviderResultStatus,
)

TASK_TIMEOUT_SECONDS: Final = 90.0
ROUTE_CONCURRENCY_LIMIT: Final = 2
MIN_TRIP_DAYS: Final = 2
MAX_TRIP_DAYS: Final = 7


class ToolCallCapability(StrEnum):
    RESOLVE_CITY = PlanningToolName.RESOLVE_CITY.value
    SEARCH_POIS = PlanningToolName.SEARCH_POIS.value
    GET_WEATHER_FORECAST = PlanningToolName.GET_WEATHER_FORECAST.value
    GET_CURRENT_WEATHER_ALERTS = PlanningToolName.GET_CURRENT_WEATHER_ALERTS.value
    CALCULATE_ROUTES = PlanningToolName.CALCULATE_ROUTES.value
    GENERATE_PLAN_CANDIDATE = "generate_plan_candidate"
    REPAIR_PLAN_CANDIDATE = "repair_plan_candidate"


@dataclass(frozen=True, slots=True)
class ToolCallPolicy:
    max_calls: int
    timeout_seconds: float
    allowed_statuses: frozenset[PlanningStatus]


DEFAULT_TOOL_CALL_POLICIES: Final[Mapping[ToolCallCapability, ToolCallPolicy]] = MappingProxyType(
    {
        ToolCallCapability.RESOLVE_CITY: ToolCallPolicy(
            1,
            6.0,
            frozenset({PlanningStatus.COLLECTING}),
        ),
        ToolCallCapability.SEARCH_POIS: ToolCallPolicy(
            3,
            6.0,
            frozenset({PlanningStatus.COLLECTING}),
        ),
        ToolCallCapability.GET_WEATHER_FORECAST: ToolCallPolicy(
            1,
            6.0,
            frozenset({PlanningStatus.COLLECTING}),
        ),
        ToolCallCapability.GET_CURRENT_WEATHER_ALERTS: ToolCallPolicy(
            1,
            6.0,
            frozenset({PlanningStatus.COLLECTING}),
        ),
        ToolCallCapability.CALCULATE_ROUTES: ToolCallPolicy(
            8,
            6.0,
            frozenset({PlanningStatus.ENRICHING_ROUTES}),
        ),
        ToolCallCapability.GENERATE_PLAN_CANDIDATE: ToolCallPolicy(
            1,
            35.0,
            frozenset({PlanningStatus.PLANNING}),
        ),
        ToolCallCapability.REPAIR_PLAN_CANDIDATE: ToolCallPolicy(
            1,
            35.0,
            frozenset({PlanningStatus.PLANNING}),
        ),
    }
)


def multiday_task_timeout_seconds(day_count: int) -> float:
    """Return the frozen total deadline for one 2-7 day planning request."""

    _require_day_count(day_count)
    return float(min(180, 90 + 18 * (day_count - 2)))


def multiday_tool_call_policies(
    day_count: int,
) -> Mapping[ToolCallCapability, ToolCallPolicy]:
    """Copy the legacy policy and scale only its route-call budget."""

    _require_day_count(day_count)
    values = dict(DEFAULT_TOOL_CALL_POLICIES)
    legacy = values[ToolCallCapability.CALCULATE_ROUTES]
    values[ToolCallCapability.CALCULATE_ROUTES] = ToolCallPolicy(
        min(28, 4 * day_count),
        legacy.timeout_seconds,
        legacy.allowed_statuses,
    )
    return MappingProxyType(values)


def multicity_task_timeout_seconds(*, city_count: int, day_count: int) -> float:
    """Return the frozen upper deadline for one V3 multi-city request."""

    _require_city_count(city_count)
    _require_multicity_day_count(day_count, city_count=city_count)
    return 180.0


def multicity_tool_call_policies(
    *,
    city_count: int,
    day_count: int,
) -> Mapping[ToolCallCapability, ToolCallPolicy]:
    """Scale city-scoped facts while keeping model calls global and bounded."""

    _require_city_count(city_count)
    _require_multicity_day_count(day_count, city_count=city_count)
    values = dict(DEFAULT_TOOL_CALL_POLICIES)
    for capability, maximum in (
        (ToolCallCapability.RESOLVE_CITY, city_count),
        (ToolCallCapability.SEARCH_POIS, 3 * city_count),
        (ToolCallCapability.GET_WEATHER_FORECAST, city_count),
        (ToolCallCapability.GET_CURRENT_WEATHER_ALERTS, city_count),
        (ToolCallCapability.CALCULATE_ROUTES, min(28, 4 * day_count)),
    ):
        legacy = values[capability]
        values[capability] = ToolCallPolicy(
            maximum,
            legacy.timeout_seconds,
            legacy.allowed_statuses,
        )
    return MappingProxyType(values)


def _require_day_count(day_count: object) -> None:
    if (
        not isinstance(day_count, int)
        or isinstance(day_count, bool)
        or not MIN_TRIP_DAYS <= day_count <= MAX_TRIP_DAYS
    ):
        raise ValueError("day_count_invalid")


def _require_city_count(city_count: object) -> None:
    if type(city_count) is not int or not 2 <= city_count <= 3:
        raise ValueError("city_count_invalid")


def _require_multicity_day_count(day_count: object, *, city_count: int) -> None:
    minimum = city_count + 1
    if type(day_count) is not int or not minimum <= day_count <= MAX_TRIP_DAYS:
        raise ValueError("day_count_invalid")


class ToolCallGovernanceErrorCode(StrEnum):
    CAPABILITY_NOT_ALLOWED = "capability_not_allowed"
    STAGE_NOT_ALLOWED = "stage_not_allowed"
    CALL_BUDGET_EXHAUSTED = "call_budget_exhausted"
    INSUFFICIENT_TIME_REMAINING = "insufficient_time_remaining"
    CONCURRENCY_LIMIT_REACHED = "concurrency_limit_reached"
    CALL_TIMEOUT = "call_timeout"
    TASK_TIMEOUT = "task_timeout"
    PERMIT_INVALID = "permit_invalid"
    CLOCK_INVALID = "clock_invalid"


class ToolCallGovernanceError(RuntimeError):
    __slots__ = ("capability", "code")

    def __init__(
        self,
        code: ToolCallGovernanceErrorCode,
        capability: ToolCallCapability | None = None,
    ) -> None:
        self.code = code
        self.capability = capability
        suffix = f": {capability.value}" if capability is not None else ""
        super().__init__(f"{code.value}{suffix}")


@dataclass(frozen=True, slots=True)
class ToolCallPermit:
    governor_id: UUID
    permit_id: UUID
    sequence: int
    capability: ToolCallCapability
    started_at: float
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    sequence: int
    capability: ToolCallCapability
    started_at: float
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ToolCallSnapshot:
    records: tuple[ToolCallRecord, ...]
    active_route_calls: int

    def count_for(self, capability: ToolCallCapability) -> int:
        return sum(record.capability is capability for record in self.records)


class ToolCallGovernor:
    __slots__ = (
        "_active_call_started_at",
        "_active_permits",
        "_active_route_attempts",
        "_active_route_calls",
        "_clock",
        "_governor_id",
        "_last_clock",
        "_policies",
        "_records",
        "_started_at",
        "_task_timeout_seconds",
    )

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        policies: Mapping[ToolCallCapability, ToolCallPolicy] = DEFAULT_TOOL_CALL_POLICIES,
        task_timeout_seconds: float = TASK_TIMEOUT_SECONDS,
    ) -> None:
        if set(policies) != set(ToolCallCapability) or not all(
            isinstance(capability, ToolCallCapability)
            and isinstance(policy, ToolCallPolicy)
            and policy.max_calls > 0
            and isfinite(policy.timeout_seconds)
            and policy.timeout_seconds > 0
            for capability, policy in policies.items()
        ):
            raise ValueError("tool_call_policies_invalid")
        if (
            not isinstance(task_timeout_seconds, int | float)
            or isinstance(task_timeout_seconds, bool)
            or not isfinite(task_timeout_seconds)
            or task_timeout_seconds <= 0
        ):
            raise ValueError("task_timeout_invalid")
        self._policies = MappingProxyType(dict(policies))
        self._task_timeout_seconds = float(task_timeout_seconds)
        self._clock = clock
        first_reading = clock()
        if (
            not isinstance(first_reading, int | float)
            or isinstance(first_reading, bool)
            or not isfinite(first_reading)
        ):
            raise ToolCallGovernanceError(ToolCallGovernanceErrorCode.CLOCK_INVALID)
        self._last_clock = float(first_reading)
        self._started_at = self._last_clock
        self._governor_id = uuid4()
        self._records: list[ToolCallRecord] = []
        self._active_permits: set[UUID] = set()
        self._active_call_started_at: dict[UUID, float | None] = {}
        self._active_route_attempts: set[UUID] = set()
        self._active_route_calls = 0

    def reserve(
        self,
        capability: ToolCallCapability,
        status: PlanningStatus,
    ) -> ToolCallPermit:
        if not isinstance(capability, ToolCallCapability):
            raise ToolCallGovernanceError(ToolCallGovernanceErrorCode.CAPABILITY_NOT_ALLOWED)
        policy = self._policies[capability]
        if status not in policy.allowed_statuses:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.STAGE_NOT_ALLOWED,
                capability,
            )
        if self.snapshot().count_for(capability) >= policy.max_calls:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED,
                capability,
            )
        now = self._read_clock()
        remaining = self._task_timeout_seconds - (now - self._started_at)
        if remaining < policy.timeout_seconds:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING,
                capability,
            )
        if (
            capability is ToolCallCapability.CALCULATE_ROUTES
            and self._active_route_calls >= ROUTE_CONCURRENCY_LIMIT
        ):
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.CONCURRENCY_LIMIT_REACHED,
                capability,
            )

        sequence = len(self._records) + 1
        permit = ToolCallPermit(
            governor_id=self._governor_id,
            permit_id=uuid4(),
            sequence=sequence,
            capability=capability,
            started_at=now,
            timeout_seconds=policy.timeout_seconds,
        )
        self._records.append(ToolCallRecord(sequence, capability, now, policy.timeout_seconds))
        self._active_permits.add(permit.permit_id)
        self._active_call_started_at[permit.permit_id] = now
        if capability is ToolCallCapability.CALCULATE_ROUTES:
            self._active_route_calls += 1
        return permit

    def defer_route_attempt_timeout_until_start(self, permit: ToolCallPermit) -> None:
        """Exclude initial external admission wait from the first route-attempt timeout."""

        capability = permit.capability if isinstance(permit, ToolCallPermit) else None
        if not isinstance(permit, ToolCallPermit) or (
            permit.governor_id != self._governor_id
            or permit.permit_id not in self._active_permits
            or permit.capability is not ToolCallCapability.CALCULATE_ROUTES
            or permit.permit_id in self._active_route_attempts
            or self._active_call_started_at[permit.permit_id] is None
        ):
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.PERMIT_INVALID,
                capability,
            )
        self._active_call_started_at[permit.permit_id] = None

    def start_route_attempt_timeout_after_wait(self, permit: ToolCallPermit) -> None:
        """Start each route HTTP-attempt timeout after its external admission wait."""

        capability = permit.capability if isinstance(permit, ToolCallPermit) else None
        if not isinstance(permit, ToolCallPermit) or (
            permit.governor_id != self._governor_id
            or permit.permit_id not in self._active_permits
            or permit.capability is not ToolCallCapability.CALCULATE_ROUTES
            or permit.permit_id in self._active_route_attempts
        ):
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.PERMIT_INVALID,
                capability,
            )
        self._active_call_started_at[permit.permit_id] = self._read_clock()
        self._active_route_attempts.add(permit.permit_id)

    def finish_route_attempt(self, permit: ToolCallPermit) -> bool:
        """End a paced route attempt before any retry admission wait begins."""

        capability = permit.capability if isinstance(permit, ToolCallPermit) else None
        if not isinstance(permit, ToolCallPermit) or (
            permit.governor_id != self._governor_id
            or permit.permit_id not in self._active_permits
            or permit.capability is not ToolCallCapability.CALCULATE_ROUTES
            or permit.permit_id not in self._active_route_attempts
        ):
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.PERMIT_INVALID,
                capability,
            )
        started_at = self._active_call_started_at[permit.permit_id]
        assert started_at is not None
        finished_at = self._read_clock()
        self._active_route_attempts.remove(permit.permit_id)
        self._active_call_started_at[permit.permit_id] = None
        return finished_at - started_at <= permit.timeout_seconds

    def complete(self, permit: ToolCallPermit) -> None:
        capability = permit.capability if isinstance(permit, ToolCallPermit) else None
        if not isinstance(permit, ToolCallPermit) or (
            permit.governor_id != self._governor_id or permit.permit_id not in self._active_permits
        ):
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.PERMIT_INVALID,
                capability,
            )
        self._active_permits.remove(permit.permit_id)
        call_started_at = self._active_call_started_at.pop(permit.permit_id)
        self._active_route_attempts.discard(permit.permit_id)
        if permit.capability is ToolCallCapability.CALCULATE_ROUTES:
            self._active_route_calls -= 1

        now = self._read_clock()
        if now - self._started_at > self._task_timeout_seconds:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.TASK_TIMEOUT,
                permit.capability,
            )
        if call_started_at is not None and now - call_started_at > permit.timeout_seconds:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.CALL_TIMEOUT,
                permit.capability,
            )

    def snapshot(self) -> ToolCallSnapshot:
        return ToolCallSnapshot(tuple(self._records), self._active_route_calls)

    def _read_clock(self) -> float:
        reading = self._clock()
        if (
            not isinstance(reading, int | float)
            or isinstance(reading, bool)
            or not isfinite(reading)
            or reading < self._last_clock
        ):
            raise ToolCallGovernanceError(ToolCallGovernanceErrorCode.CLOCK_INVALID)
        self._last_clock = float(reading)
        return self._last_clock


class RunCallBudget:
    """Explicit, in-memory run allowance. No environment, payloads or global state."""

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        logical_limits: tuple[int, int, int] = (60, 10, 10),
        http_limits: tuple[int, int, int] = (75, 15, 10),
        execution_limits: tuple[int, int] = (1, 4),
        deadline_seconds: float = 1200,
    ) -> None:
        if any(
            type(n) is not int or not 0 <= n <= 10000
            for n in (*logical_limits, *http_limits, *execution_limits)
        ):
            raise ValueError("run_limits_invalid")
        if len(logical_limits) != 3 or len(http_limits) != 3 or len(execution_limits) != 2:
            raise ValueError("run_limits_invalid")
        if not isfinite(deadline_seconds) or deadline_seconds <= 0:
            raise ValueError("run_deadline_invalid")
        self._clock = clock
        self._last = float(clock())
        if not isfinite(self._last):
            raise ValueError("run_clock_invalid")
        self._started = self._last
        self._deadline = self._last + deadline_seconds
        self._lock = RLock()
        self._providers = (Provider.AMAP, Provider.QWEATHER, Provider.DEEPSEEK)
        self._limits = {"logical": logical_limits, "http": http_limits}
        self._counts = {"logical": [0, 0, 0], "http": [0, 0, 0]}
        self._execution_limits = dict(zip(("planning", "replan"), execution_limits, strict=True))
        self._executions: dict[UUID, dict[str, Any]] = {}
        self._records: list[dict[str, Any]] = []
        self.stopped = False
        self.reason = "none"

    def _remaining(self) -> float:
        now = float(self._clock())
        if not isfinite(now) or now < self._last:
            self.stop("clock_invalid")
            return 0
        self._last = now
        remaining = max(0.0, self._deadline - now)
        if remaining == 0:
            self.stop("deadline")
        return remaining

    def remaining(self) -> float:
        with self._lock:
            return self._remaining()

    def stop(
        self,
        reason: Literal[
            "stopped", "deadline", "budget", "clock_invalid", "business_failure"
        ] = "stopped",
    ) -> None:
        with self._lock:
            if not self.stopped:
                self.reason = reason
            self.stopped = True

    def _admit(self) -> None:
        if self._remaining() <= 0:
            self.stop("deadline")
        if self.stopped:
            code = (
                ToolCallGovernanceErrorCode.TASK_TIMEOUT
                if self.reason == "deadline"
                else ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED
            )
            raise ToolCallGovernanceError(code)

    def open_execution(self, kind: Literal["planning", "replan"], request_id: UUID) -> UUID:
        with self._lock:
            self._admit()
            if kind not in self._execution_limits or not isinstance(request_id, UUID):
                raise ValueError("run_identity_invalid")
            matching = [v for v in self._executions.values() if v["kind"] == kind]
            if len(matching) >= self._execution_limits[kind] or any(
                v["request_id"] == str(request_id) for v in matching
            ):
                self.stop("budget")
                self._admit()
            identity = uuid4()
            self._executions[identity] = {
                "kind": kind,
                "request_id": str(request_id),
                "state": "active",
                "started_seconds": self._last - self._started,
            }
            return identity

    def reserve(
        self,
        kind: Literal["logical", "http"],
        execution: UUID,
        provider: Provider,
        operation: ProviderOperation,
        attempt: int = 1,
    ) -> int:
        with self._lock:
            self._admit()
            if (
                kind not in self._limits
                or execution not in self._executions
                or self._executions[execution]["state"] != "active"
                or not isinstance(provider, Provider)
                or provider not in self._providers
                or not isinstance(operation, ProviderOperation)
                or type(attempt) is not int
                or attempt < 1
            ):
                raise ValueError("run_record_invalid")
            index = self._providers.index(provider)
            if self._counts[kind][index] >= self._limits[kind][index]:
                self.stop("budget")
                self._admit()
            self._counts[kind][index] += 1
            self._records.append(
                {
                    "kind": kind,
                    "execution_id": str(execution),
                    "provider": provider.value,
                    "operation": operation.value,
                    "attempt": attempt,
                    "state": "started",
                    "status": None,
                    "error_code": None,
                }
            )
            return len(self._records) - 1

    def finish_attempt(
        self, index: int, status: ProviderResultStatus | None, error: ProviderErrorCode | None
    ) -> None:
        with self._lock:
            if status is not None and not isinstance(status, ProviderResultStatus):
                raise ValueError("run_status_invalid")
            if error is not None and not isinstance(error, ProviderErrorCode):
                raise ValueError("run_error_invalid")
            row = self._records[index]
            row.update(
                state="interrupted" if status is None else "returned",
                status=status.value if status is not None else None,
                error_code=error.value if error is not None else None,
            )

    def finish_execution(
        self, execution: UUID, state: Literal["returned", "cancelled", "failed"]
    ) -> None:
        with self._lock:
            self._remaining()
            self._executions[execution]["state"] = state
            self._executions[execution]["duration_seconds"] = max(
                0.0, self._last - self._started - self._executions[execution]["started_seconds"]
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "stopped": self.stopped,
                "reason": self.reason,
                **{
                    k: {p.value: n for p, n in zip(self._providers, values, strict=True)}
                    for k, values in self._counts.items()
                },
                "executions": [{"execution_id": str(k), **v} for k, v in self._executions.items()],
                "records": [dict(r) for r in self._records],
            }
