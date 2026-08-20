"""Deterministic pre-call governance with an injected monotonic clock."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Final
from uuid import UUID, uuid4

from intelligent_travel_assistant.application.ports import PlanningToolName
from intelligent_travel_assistant.contracts import PlanningStatus

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
        "_active_permits",
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
        if capability is ToolCallCapability.CALCULATE_ROUTES:
            self._active_route_calls += 1
        return permit

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
        if permit.capability is ToolCallCapability.CALCULATE_ROUTES:
            self._active_route_calls -= 1

        now = self._read_clock()
        if now - self._started_at > self._task_timeout_seconds:
            raise ToolCallGovernanceError(
                ToolCallGovernanceErrorCode.TASK_TIMEOUT,
                permit.capability,
            )
        if now - permit.started_at > permit.timeout_seconds:
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
