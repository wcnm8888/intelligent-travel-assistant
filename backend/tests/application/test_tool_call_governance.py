"""Application-level authorization, call budget, and deadline policies."""

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from intelligent_travel_assistant.application.ports import PlanningToolName
from intelligent_travel_assistant.application.tooling import (
    DEFAULT_TOOL_CALL_POLICIES,
    ROUTE_CONCURRENCY_LIMIT,
    TASK_TIMEOUT_SECONDS,
    ToolCallCapability,
    ToolCallGovernanceError,
    ToolCallGovernanceErrorCode,
    ToolCallGovernor,
    multiday_task_timeout_seconds,
    multiday_tool_call_policies,
)
from intelligent_travel_assistant.contracts import PlanningStatus

TOOLING_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "intelligent_travel_assistant"
    / "application"
    / "tooling"
)


class ManualClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_capability_whitelist_is_exactly_five_tools_plus_two_deepseek_operations() -> None:
    tool_capabilities = {ToolCallCapability(item.value) for item in PlanningToolName}

    assert tool_capabilities == set(ToolCallCapability) - {
        ToolCallCapability.GENERATE_PLAN_CANDIDATE,
        ToolCallCapability.REPAIR_PLAN_CANDIDATE,
    }
    assert len(DEFAULT_TOOL_CALL_POLICIES) == 7
    assert set(DEFAULT_TOOL_CALL_POLICIES) == set(ToolCallCapability)


@pytest.mark.parametrize(
    ("capability", "max_calls", "timeout", "status"),
    [
        (ToolCallCapability.RESOLVE_CITY, 1, 6.0, PlanningStatus.COLLECTING),
        (ToolCallCapability.SEARCH_POIS, 3, 6.0, PlanningStatus.COLLECTING),
        (ToolCallCapability.GET_WEATHER_FORECAST, 1, 6.0, PlanningStatus.COLLECTING),
        (
            ToolCallCapability.GET_CURRENT_WEATHER_ALERTS,
            1,
            6.0,
            PlanningStatus.COLLECTING,
        ),
        (ToolCallCapability.CALCULATE_ROUTES, 8, 6.0, PlanningStatus.ENRICHING_ROUTES),
        (
            ToolCallCapability.GENERATE_PLAN_CANDIDATE,
            1,
            35.0,
            PlanningStatus.PLANNING,
        ),
        (
            ToolCallCapability.REPAIR_PLAN_CANDIDATE,
            1,
            35.0,
            PlanningStatus.PLANNING,
        ),
    ],
)
def test_approved_policy_values_are_frozen(
    capability: ToolCallCapability,
    max_calls: int,
    timeout: float,
    status: PlanningStatus,
) -> None:
    policy = DEFAULT_TOOL_CALL_POLICIES[capability]

    assert policy.max_calls == max_calls
    assert policy.timeout_seconds == timeout
    assert policy.allowed_statuses == frozenset({status})
    with pytest.raises(FrozenInstanceError):
        policy.max_calls = 999  # type: ignore[misc]


def test_total_timeout_and_route_concurrency_are_frozen_approved_values() -> None:
    assert TASK_TIMEOUT_SECONDS == 90.0
    assert ROUTE_CONCURRENCY_LIMIT == 2


@pytest.mark.parametrize(
    ("day_count", "route_calls", "task_timeout"),
    ((2, 8, 90.0), (3, 12, 108.0), (7, 28, 180.0)),
)
def test_multiday_policy_scales_only_route_budget_and_total_deadline(
    day_count: int,
    route_calls: int,
    task_timeout: float,
) -> None:
    policies = multiday_tool_call_policies(day_count)

    assert policies[ToolCallCapability.CALCULATE_ROUTES].max_calls == route_calls
    assert multiday_task_timeout_seconds(day_count) == task_timeout
    assert {
        capability: policy
        for capability, policy in policies.items()
        if capability is not ToolCallCapability.CALCULATE_ROUTES
    } == {
        capability: policy
        for capability, policy in DEFAULT_TOOL_CALL_POLICIES.items()
        if capability is not ToolCallCapability.CALCULATE_ROUTES
    }


def test_configured_multiday_governor_enforces_its_own_limits() -> None:
    governor = ToolCallGovernor(
        clock=ManualClock(),
        policies=multiday_tool_call_policies(3),
        task_timeout_seconds=multiday_task_timeout_seconds(3),
    )

    for _ in range(12):
        permit = governor.reserve(
            ToolCallCapability.CALCULATE_ROUTES,
            PlanningStatus.ENRICHING_ROUTES,
        )
        governor.complete(permit)

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(
            ToolCallCapability.CALCULATE_ROUTES,
            PlanningStatus.ENRICHING_ROUTES,
        )
    assert raised.value.code is ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED


def test_unknown_string_is_rejected_before_it_can_be_treated_as_a_tool() -> None:
    governor = ToolCallGovernor(clock=ManualClock())

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve("arbitrary_http", PlanningStatus.COLLECTING)  # type: ignore[arg-type]

    assert raised.value.code is ToolCallGovernanceErrorCode.CAPABILITY_NOT_ALLOWED
    assert governor.snapshot().records == ()


@pytest.mark.parametrize(
    ("capability", "wrong_status"),
    [
        (ToolCallCapability.RESOLVE_CITY, PlanningStatus.PLANNING),
        (ToolCallCapability.SEARCH_POIS, PlanningStatus.ENRICHING_ROUTES),
        (ToolCallCapability.GET_WEATHER_FORECAST, PlanningStatus.VALIDATING),
        (ToolCallCapability.GET_CURRENT_WEATHER_ALERTS, PlanningStatus.DRAFT),
        (ToolCallCapability.CALCULATE_ROUTES, PlanningStatus.COLLECTING),
        (ToolCallCapability.GENERATE_PLAN_CANDIDATE, PlanningStatus.COLLECTING),
        (ToolCallCapability.REPAIR_PLAN_CANDIDATE, PlanningStatus.COLLECTING),
    ],
)
def test_stage_authorization_is_checked_before_budget_is_consumed(
    capability: ToolCallCapability,
    wrong_status: PlanningStatus,
) -> None:
    governor = ToolCallGovernor(clock=ManualClock())

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(capability, wrong_status)

    assert raised.value.code is ToolCallGovernanceErrorCode.STAGE_NOT_ALLOWED
    assert governor.snapshot().count_for(capability) == 0


@pytest.mark.parametrize(
    "capability",
    tuple(ToolCallCapability),
)
def test_each_capability_accepts_exact_budget_then_rejects_without_new_record(
    capability: ToolCallCapability,
) -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    policy = DEFAULT_TOOL_CALL_POLICIES[capability]
    status = next(iter(policy.allowed_statuses))

    for _ in range(policy.max_calls):
        permit = governor.reserve(capability, status)
        governor.complete(permit)

    before = governor.snapshot()
    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(capability, status)

    assert raised.value.code is ToolCallGovernanceErrorCode.CALL_BUDGET_EXHAUSTED
    assert governor.snapshot() == before


def test_remaining_total_time_must_cover_the_full_per_call_timeout() -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    clock.advance(84.0)

    permit = governor.reserve(ToolCallCapability.RESOLVE_CITY, PlanningStatus.COLLECTING)
    governor.complete(permit)
    clock.advance(0.001)

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(ToolCallCapability.SEARCH_POIS, PlanningStatus.COLLECTING)

    assert raised.value.code is ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING
    assert governor.snapshot().count_for(ToolCallCapability.SEARCH_POIS) == 0


def test_deepseek_requires_its_full_35_second_window_before_start() -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    clock.advance(55.001)

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(
            ToolCallCapability.GENERATE_PLAN_CANDIDATE,
            PlanningStatus.PLANNING,
        )

    assert raised.value.code is ToolCallGovernanceErrorCode.INSUFFICIENT_TIME_REMAINING


def test_exact_deadline_boundaries_are_inclusive() -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    clock.advance(84.0)
    permit = governor.reserve(
        ToolCallCapability.RESOLVE_CITY,
        PlanningStatus.COLLECTING,
    )
    clock.advance(6.0)

    governor.complete(permit)

    assert governor.snapshot().count_for(ToolCallCapability.RESOLVE_CITY) == 1


def test_completion_reports_per_call_timeout_and_releases_route_slot() -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    permit = governor.reserve(
        ToolCallCapability.CALCULATE_ROUTES,
        PlanningStatus.ENRICHING_ROUTES,
    )
    clock.advance(6.001)

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.complete(permit)

    assert raised.value.code is ToolCallGovernanceErrorCode.CALL_TIMEOUT
    assert governor.snapshot().active_route_calls == 0


def test_task_timeout_is_distinct_when_total_deadline_is_exceeded() -> None:
    clock = ManualClock()
    governor = ToolCallGovernor(clock=clock)
    permit = governor.reserve(
        ToolCallCapability.GENERATE_PLAN_CANDIDATE,
        PlanningStatus.PLANNING,
    )
    clock.advance(90.001)

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.complete(permit)

    assert raised.value.code is ToolCallGovernanceErrorCode.TASK_TIMEOUT


def test_route_concurrency_limit_rejects_third_active_call_and_recovers() -> None:
    governor = ToolCallGovernor(clock=ManualClock())
    first = governor.reserve(
        ToolCallCapability.CALCULATE_ROUTES,
        PlanningStatus.ENRICHING_ROUTES,
    )
    second = governor.reserve(
        ToolCallCapability.CALCULATE_ROUTES,
        PlanningStatus.ENRICHING_ROUTES,
    )

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(
            ToolCallCapability.CALCULATE_ROUTES,
            PlanningStatus.ENRICHING_ROUTES,
        )
    assert raised.value.code is ToolCallGovernanceErrorCode.CONCURRENCY_LIMIT_REACHED
    assert governor.snapshot().active_route_calls == 2

    governor.complete(first)
    third = governor.reserve(
        ToolCallCapability.CALCULATE_ROUTES,
        PlanningStatus.ENRICHING_ROUTES,
    )
    governor.complete(second)
    governor.complete(third)
    assert governor.snapshot().active_route_calls == 0


def test_permit_cannot_be_completed_twice_or_by_another_governor() -> None:
    clock = ManualClock()
    first_governor = ToolCallGovernor(clock=clock)
    second_governor = ToolCallGovernor(clock=clock)
    permit = first_governor.reserve(
        ToolCallCapability.RESOLVE_CITY,
        PlanningStatus.COLLECTING,
    )

    with pytest.raises(ToolCallGovernanceError) as foreign:
        second_governor.complete(permit)
    first_governor.complete(permit)
    with pytest.raises(ToolCallGovernanceError) as duplicate:
        first_governor.complete(permit)

    assert foreign.value.code is ToolCallGovernanceErrorCode.PERMIT_INVALID
    assert duplicate.value.code is ToolCallGovernanceErrorCode.PERMIT_INVALID


def test_snapshot_and_records_are_immutable_safe_values() -> None:
    governor = ToolCallGovernor(clock=ManualClock())
    permit = governor.reserve(
        ToolCallCapability.RESOLVE_CITY,
        PlanningStatus.COLLECTING,
    )
    governor.complete(permit)
    snapshot = governor.snapshot()

    assert snapshot.records[0].capability is ToolCallCapability.RESOLVE_CITY
    assert snapshot.records[0].timeout_seconds == 6.0
    with pytest.raises(FrozenInstanceError):
        snapshot.records[0].timeout_seconds = 1.0  # type: ignore[misc]


@pytest.mark.parametrize("invalid", (True, float("nan"), float("inf"), float("-inf")))
def test_invalid_clock_is_rejected(invalid: float) -> None:
    with pytest.raises(ToolCallGovernanceError) as raised:
        ToolCallGovernor(clock=lambda: invalid)

    assert raised.value.code is ToolCallGovernanceErrorCode.CLOCK_INVALID


def test_wrong_permit_type_returns_stable_error() -> None:
    governor = ToolCallGovernor(clock=ManualClock())

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.complete(object())  # type: ignore[arg-type]

    assert raised.value.code is ToolCallGovernanceErrorCode.PERMIT_INVALID


def test_clock_regression_is_rejected_instead_of_extending_deadline() -> None:
    readings = iter((10.0, 9.0))
    governor = ToolCallGovernor(clock=lambda: next(readings))

    with pytest.raises(ToolCallGovernanceError) as raised:
        governor.reserve(ToolCallCapability.RESOLVE_CITY, PlanningStatus.COLLECTING)

    assert raised.value.code is ToolCallGovernanceErrorCode.CLOCK_INVALID
    assert governor.snapshot().records == ()


def test_governance_module_has_no_network_environment_sleep_or_async_runtime_dependency() -> None:
    forbidden_roots = {
        "asyncio",
        "fastapi",
        "httpx",
        "openai",
        "os",
        "requests",
        "socket",
        "time",
        "urllib",
    }
    observed_imports: list[str] = []
    observed_calls: list[str] = []
    for path in (TOOLING_ROOT / "governance.py",):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
                if "sleep" in rendered or "getenv" in rendered or "environ" in rendered:
                    observed_calls.append(rendered)

    assert observed_imports == []
    assert observed_calls == []
