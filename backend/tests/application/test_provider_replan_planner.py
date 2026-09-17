"""R3 transport-only offline integration; never imports the production app."""

from __future__ import annotations

import asyncio
import builtins
import copy
import json
import os
import socket
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tests.application.test_replan_facts import (
    NOW,
    baseline,
    commands,
    modified,
    plan_of,
    with_unknown_intercity_cost,
)

from intelligent_travel_assistant.adapters.providers.amap import (
    AMAP_POI_NAMESPACE,
    AmapAdapter,
    AmapAdapterConfig,
)
from intelligent_travel_assistant.adapters.providers.deepseek import (
    DeepSeekAdapter,
    DeepSeekAdapterConfig,
)
from intelligent_travel_assistant.adapters.providers.qweather import (
    QWeatherAdapter,
    QWeatherAdapterConfig,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    ReplanRecord,
    request_fingerprint,
)
from intelligent_travel_assistant.application.services import (
    provider_replan_planner as planner_module,
)
from intelligent_travel_assistant.application.services.offline_planning import RouteLookupStage
from intelligent_travel_assistant.application.services.offline_planning import (
    _lookup_route as original_lookup_route,
)
from intelligent_travel_assistant.application.services.provider_replan_planner import (
    ProviderReplanPlanner,
)
from intelligent_travel_assistant.application.services.provider_replanning import (
    ProviderNeutralReplanExecutor,
)
from intelligent_travel_assistant.application.services.replan_candidate import (
    ActivityReplacement,
    ReplanCandidate,
    build_replan_candidate,
)
from intelligent_travel_assistant.application.services.replan_facts import ReplanFactProjector
from intelligent_travel_assistant.application.tooling import PacedAttemptLimiter
from intelligent_travel_assistant.contracts import (
    ApiError,
    ApiErrorCode,
    Coordinates,
    CoordinateSystem,
    Money,
    PlanningStatus,
    Uncertainty,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DeleteActivity,
    ImpactAnalysis,
    Provider,
    ProviderOperation,
    ReorderActivities,
    ReplanCommand,
    ReplanStatus,
    attempt_pacing_policy_for,
)
from intelligent_travel_assistant.domain import (
    Money as DomainMoney,
)


class Clock:
    def __init__(self) -> None:
        self.seconds = 0.0
        self.utc_step_seconds = 0.0
        self.utc_calls_before_jump: int | None = None
        self.deferred_jump_seconds = 0.0

    def monotonic(self) -> float:
        return self.seconds

    async def sleep(self, seconds: float) -> None:
        self.seconds += seconds

    def utc(self) -> datetime:
        if self.utc_calls_before_jump is not None:
            if self.utc_calls_before_jump == 0:
                self.seconds += self.deferred_jump_seconds
                self.utc_calls_before_jump = None
            else:
                self.utc_calls_before_jump -= 1
        current = NOW + timedelta(seconds=self.seconds)
        self.seconds += self.utc_step_seconds
        return current

    def defer_utc_jump(self, *, after_calls: int, seconds: float) -> None:
        self.utc_calls_before_jump = after_calls
        self.deferred_jump_seconds = seconds


def prepared(v2: bool = False) -> PlanningJob:
    job = baseline(v2)
    plan = plan_of(job)
    locations = tuple(
        loc.model_copy(
            update={
                "coordinates": Coordinates(
                    longitude=Decimal("120.15"),
                    latitude=Decimal("30.27"),
                    coordinate_system=CoordinateSystem.PROVIDER_NATIVE,
                )
            }
        )
        for loc in plan.locations
    )
    return modified(job, plan=plan.model_copy(update={"locations": locations}))


def record(
    job: PlanningJob,
    command: ReplanCommand,
    *,
    evaluated_at: datetime = NOW,
    replan_id: UUID | None = None,
) -> ReplanRecord:
    return ReplanRecord(
        replan_id if replan_id is not None else UUID(int=9001),
        job.job_id,
        UUID(int=9002),
        job.request_fingerprint,
        plan_of(job).plan_id,
        1,
        job.version,
        UUID(int=9003),
        command.operation,
        command,
        ReplanFactProjector().analyze(job, command, evaluated_at=evaluated_at),
        ReplanStatus.REPLANNING,
        1,
        None,
        None,
        None,
        None,
        None,
        evaluated_at,
        evaluated_at,
        evaluated_at + timedelta(minutes=5),
        None,
    )


class Transport:
    def __init__(
        self,
        clock: Clock,
        job: PlanningJob,
        index: int = 0,
        repair: bool = False,
        fault: str = "",
        endpoint: str = "",
    ) -> None:
        self.clock = clock
        self.calls: list[tuple[str, float]] = []
        self.model_scopes: list[dict[str, Any]] = []
        self.job, self.index, self.repair = job, index, repair
        self.fault, self.endpoint = fault, endpoint

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls.append((path, self.clock.seconds))
        if self.endpoint in path and self.fault:
            if self.fault in {"model_invalid", "partial", "stale", "scope_escape"}:
                pass
            elif self.fault == "cancel":
                raise asyncio.CancelledError()
            elif self.fault == "deadline":
                self.clock.seconds += 91
                raise httpx2.ReadTimeout("synthetic")
            elif self.fault == "timeout":
                raise httpx2.ReadTimeout("synthetic")
            elif self.fault == "empty":
                if path == "/v3/geocode/geo":
                    return httpx2.Response(
                        200,
                        json={
                            "status": "1",
                            "info": "OK",
                            "infocode": "10000",
                            "count": "0",
                            "geocodes": [],
                        },
                    )
                if "direction" in path:
                    key = "transits" if "transit" in path else "paths"
                    return httpx2.Response(
                        200,
                        json={
                            "status": "1",
                            "info": "OK",
                            "infocode": "10000",
                            "count": "0",
                            "route": {key: []},
                        },
                    )
                if path == "/chat/completions":
                    return httpx2.Response(
                        200,
                        json={
                            "object": "chat.completion",
                            "model": "deepseek-v4-flash",
                            "choices": [],
                        },
                    )
                return httpx2.Response(
                    200,
                    json={
                        "status": "1",
                        "info": "OK",
                        "infocode": "10000",
                        "count": "0",
                        "pois": [],
                    },
                )
            elif self.fault == "schema":
                return httpx2.Response(200, json={"invalid": True})
            elif self.fault == "retry" and sum(p == path for p, _ in self.calls) > 1:
                pass
            elif self.fault != "model_invalid":
                return httpx2.Response(503 if self.fault == "retry" else int(self.fault))
        if path.startswith("/weather/v1/daily/"):
            days: list[dict[str, Any]] = [
                {
                    "forecastStartTime": f"{d.local_date}T00:00+08:00",
                    "forecastEndTime": f"{d.local_date + timedelta(days=1)}T00:00+08:00",
                    "temperatureMin": {"value": 20, "unit": "°C"},
                    "temperatureMax": {"value": 30, "unit": "°C"},
                    "daytime": {"condition": {"text": "多云", "code": "101"}},
                    "nighttime": {"condition": {"text": "多云", "code": "101"}},
                }
                for d in plan_of(self.job).days
            ]
            if self.endpoint in path and self.fault == "partial":
                days.append({"forecastStartTime": "invalid"})
            return httpx2.Response(
                200,
                json={
                    "metadata": {"tag": "synthetic", "attributions": ["https://dev.qweather.com/"]},
                    "days": days,
                },
            )
        if path.startswith("/weatheralert/"):
            if self.endpoint in path and self.fault == "stale":
                self.clock.defer_utc_jump(after_calls=1, seconds=120)
                return httpx2.Response(
                    200,
                    json={
                        "metadata": {
                            "tag": "synthetic",
                            "zeroResult": False,
                            "attributions": ["https://dev.qweather.com/"],
                        },
                        "alerts": [
                            {
                                "id": "SYNTHETIC-ALERT",
                                "issuedTime": (NOW - timedelta(minutes=1)).isoformat(),
                                "expireTime": (NOW + timedelta(minutes=1)).isoformat(),
                                "severity": "moderate",
                                "headline": "合成预警",
                                "description": "仅用于离线测试。",
                            }
                        ],
                    },
                )
            return httpx2.Response(
                200,
                json={
                    "metadata": {
                        "tag": "synthetic",
                        "zeroResult": True,
                        "attributions": ["https://dev.qweather.com/"],
                    },
                    "alerts": [],
                },
            )
        if path == "/v5/place/text":
            pois: list[dict[str, Any]] = [
                {
                    "id": "SYNTHETIC-R3-ALT",
                    "name": "合成候选展馆",
                    "type": "科教文化服务;博物馆",
                    "typecode": "140100",
                    "adcode": "330100",
                    "address": "合成地址二",
                    "location": "120.17,30.29",
                },
                {
                    "id": "SYNTHETIC-R3",
                    "name": "合成博物馆",
                    "type": "科教文化服务;博物馆",
                    "typecode": "140100",
                    "adcode": "330100",
                    "address": "合成地址",
                    "location": "120.16,30.28",
                },
            ]
            if self.endpoint in path and self.fault == "partial":
                pois.append(
                    {
                        "id": "SYNTHETIC-BAD",
                        "name": "合成坏记录",
                        "type": "科教文化服务;博物馆",
                        "typecode": "140100",
                        "adcode": "330100",
                        "address": "合成地址",
                        "location": "invalid",
                    }
                )
            return httpx2.Response(
                200,
                json={
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "count": str(len(pois)),
                    "pois": pois,
                },
            )
        if path == "/chat/completions":
            # Only synthetic outgoing typed context is decoded; never credentials or
            # raw live data. Record both generation and repair before choosing the
            # deliberately invalid or valid synthetic response.
            body: dict[str, Any] = json.loads(request.content)
            request_context: dict[str, Any] = json.loads(body["messages"][-1]["content"])
            values = request_context.get("repair_brief", request_context)
            scope = values["replan_selection_scope"]
            self.model_scopes.append(scope)
            if self.fault == "model_invalid":
                content = "not-json"
            elif self.repair and sum(p == path for p, _ in self.calls) == 1:
                content = "not-json"
            else:
                source_ids = values.get("activity_source_ids", [])
                dates = values.get("expected_dates")
                if not dates:
                    first = datetime.fromisoformat(values["start_date"]).date()
                    last = datetime.fromisoformat(values["end_date"]).date()
                    dates = [
                        str(first + timedelta(days=offset))
                        for offset in range((last - first).days + 1)
                    ]
                planned = [list(day) for day in scope["baseline_location_ids_by_day"]]
                target_day = dates.index(scope["target_local_date"])
                target_index = scope["target_selection_index"]
                selected = scope["allowed_candidate_location_ids"][-1]
                if self.fault == "scope_escape":
                    selected = planned[target_day][target_index]
                planned[target_day][target_index] = selected
                days = [
                    {
                        "local_date": local_date,
                        "selections": [
                            {
                                "location_id": location_id,
                                "local_date": local_date,
                                "title": "合成活动",
                                "priority_rank": rank,
                                "selection_kind": "required",
                                "duration_class": "standard",
                                "source_ids": source_ids,
                            }
                            for rank, location_id in enumerate(location_ids, 1)
                        ],
                    }
                    for local_date, location_ids in zip(dates, planned, strict=True)
                ]
                content = json.dumps(
                    {
                        "intent_summary": "合成局部计划",
                        "days": days,
                        "explanation": "合成解释",
                        "warnings": [],
                    },
                    ensure_ascii=False,
                )
            return httpx2.Response(
                200,
                json={
                    "object": "chat.completion",
                    "model": "deepseek-v4-flash",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                },
            )
        if path == "/v3/geocode/geo":
            return httpx2.Response(
                200,
                json={
                    "status": "1",
                    "infocode": "10000",
                    "info": "OK",
                    "count": "1",
                    "geocodes": [
                        {
                            "country": "中国",
                            "province": "浙江省",
                            "city": "杭州市",
                            "citycode": "0571",
                            "adcode": "330100",
                            "level": "市",
                            "formatted_address": "浙江省杭州市",
                            "location": "120.15,30.27",
                        }
                    ],
                },
            )
        assert path in {"/v5/direction/walking", "/v5/direction/transit/integrated"}
        route: dict[str, Any] = {
            "origin": request.url.params["origin"],
            "destination": request.url.params["destination"],
        }
        route["transits" if "transit" in path else "paths"] = [
            {
                "distance": "100",
                "cost": {"duration": "60", "transit_fee": "1"},
                "steps": [],
                "segments": [],
            }
        ]
        return httpx2.Response(
            200,
            json={"status": "1", "infocode": "10000", "info": "OK", "count": "1", "route": route},
        )


def setup(
    v2: bool = False,
    index: int = 0,
    repair: bool = False,
    fault: str = "",
    endpoint: str = "",
    weather: bool = False,
    job: PlanningJob | None = None,
    source_id_start: int = 10000,
) -> tuple[PlanningJob, ReplanCommand, ProviderNeutralReplanExecutor, Transport, Clock]:
    job = prepared(v2) if job is None else job
    if weather:
        plan = plan_of(job)
        days = (plan.days[0].model_copy(update={"weather": None}), plan.days[1])
        job = modified(job, plan=plan.model_copy(update={"days": days}))
    command = commands(job)[index]
    clock = Clock()
    transport = Transport(clock, job, index, repair, fault, endpoint)
    ids = count(source_id_start)
    adapter = AmapAdapter(
        AmapAdapterConfig(web_service_key="synthetic-r3-only"),
        transport=httpx2.MockTransport(transport),
        clock=clock.utc,
        source_id_factory=lambda: UUID(int=next(ids)),
    )
    policy = attempt_pacing_policy_for(Provider.AMAP, ProviderOperation.CALCULATE_ROUTES)
    assert policy is not None
    limiter = PacedAttemptLimiter(
        provider=Provider.AMAP,
        operation=ProviderOperation.CALCULATE_ROUTES,
        policy=policy,
        clock=clock.monotonic,
        sleeper=clock.sleep,
    )
    planner = ProviderReplanPlanner(
        amap=adapter,
        route_limiter=limiter,
        qweather=QWeatherAdapter(
            QWeatherAdapterConfig(
                api_host="synthetic.qweatherapi.com",
                project_id="SYNTHETIC",
                credential_id="SYNTHETIC",
                private_key_pem=Ed25519PrivateKey.from_private_bytes(b"\x01" * 32).private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            ),
            transport=httpx2.MockTransport(transport),
            clock=clock.utc,
            source_id_factory=lambda: UUID(int=next(ids)),
        )
        if weather
        else None,
        deepseek=DeepSeekAdapter(
            DeepSeekAdapterConfig(api_key="synthetic-r3-only"),
            transport=httpx2.MockTransport(transport),
            clock=clock.utc,
            source_id_factory=lambda: UUID(int=next(ids)),
        ),
        clock=clock.utc,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
        jitter=lambda: 0.0,
    )
    facts = ReplanFactProjector()
    executor = ProviderNeutralReplanExecutor(
        cast(Any, None),
        cast(Any, None),
        planner,
        cast(Any, None),
        facts=facts,
        clock=clock.utc,
    )
    return job, command, executor, transport, clock


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("weather", (False, True))
def test_four_commands_through_actual_adapters_and_executor(
    v2: bool, index: int, weather: bool
) -> None:
    job, command, executor, transport, clock = setup(v2, index, weather=weather)
    original = copy.deepcopy(job)
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    assert job == original
    day = result.commit.result.plan.days[0]
    if index == 0:
        assert len(day.activities) == 1
    elif index == 1:
        assert day.activities[0].location_id == uuid5(AMAP_POI_NAMESPACE, "SYNTHETIC-R3")
        assert day.activities[0].title == "合成博物馆"
    elif index == 2:
        assert isinstance(command, AdjustActivityTime)
        assert day.activities[0].start_time == command.start_time
    else:
        assert isinstance(command, ReorderActivities)
        assert tuple(a.item_id for a in day.activities) == command.ordered_activity_ids
    if index != 2:
        assert any("direction" in path for path, _ in transport.calls)


def test_route_lookup_contract_includes_stage_and_stable_requirement_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[object, object]] = []

    async def observe(requirement: Any, **kwargs: Any) -> Any:
        observed.append((kwargs.get("stage"), kwargs.get("requirement_index")))
        return await original_lookup_route(requirement, **kwargs)

    monkeypatch.setattr(planner_module, "_lookup_route", observe)
    job, command, executor, _, _ = setup(index=1)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert observed
    assert all(stage is RouteLookupStage.PRIMARY for stage, _ in observed)
    assert [index for _, index in observed] == list(range(1, len(observed) + 1))


@pytest.mark.parametrize("v2", (False, True))
def test_actual_generation_then_single_repair(v2: bool) -> None:
    job, command, executor, transport, _ = setup(v2, 1, repair=True)
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is not None, result.outcome
    assert sum(p == "/chat/completions" for p, _ in transport.calls) == 2
    assert any(s.source_type == "model_plan_proposal_repair" for s in result.commit.result.sources)
    assert len(transport.model_scopes) == 2
    assert transport.model_scopes[0] == transport.model_scopes[1]


def test_replace_candidate_validation_uses_time_after_provider_fetch() -> None:
    job, command, executor, _, clock = setup(index=1)
    clock.utc_step_seconds = 0.000001
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is not None, result.outcome


def test_replace_preserves_unrelated_historical_unknown_cost() -> None:
    job = with_unknown_intercity_cost(prepared())
    job, command, executor, _, _ = setup(index=1, job=job)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    intercity = next(
        cost
        for cost in result.commit.result.plan.budget_summary.cost_items
        if cost.category.value == "intercity_transport"
    )
    assert intercity.confidence.value == "unknown"
    assert intercity.amount is None
    assert job.result is not None
    additions = result.commit.result.uncertainties[len(job.result.uncertainties) :]
    assert any(item.code == "budget_indeterminate" for item in additions)
    assert all(intercity.cost_id not in item.affected_refs for item in additions)


def test_replace_model_transport_uses_only_serialized_scope_and_can_choose_any_candidate() -> None:
    job, command, executor, transport, _ = setup(index=1)
    transport.job = cast(Any, None)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    selected = result.commit.result.plan.days[0].activities[0]
    assert selected.location_id == uuid5(AMAP_POI_NAMESPACE, "SYNTHETIC-R3")
    assert selected.title == "合成博物馆"
    assert len(transport.model_scopes) == 1
    assert len(transport.model_scopes[0]["allowed_candidate_location_ids"]) == 2


def test_replace_model_scope_escape_repairs_once_then_fails_without_routes() -> None:
    job, command, executor, transport, _ = setup(index=1, fault="scope_escape", endpoint="chat")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.status is ReplanStatus.FAILED
    assert result.outcome.error_code == "model_output_invalid"
    assert len(transport.model_scopes) == 2
    assert transport.model_scopes[0] == transport.model_scopes[1]
    assert not any("direction" in path for path, _ in transport.calls)


@pytest.mark.parametrize(
    ("fault", "expected_status", "expected_code"),
    (
        ("401", ReplanStatus.FAILED, "provider_unauthorized"),
        ("429", ReplanStatus.FAILED, "provider_rate_limited"),
        ("503", ReplanStatus.FAILED, "provider_unavailable"),
        ("schema", ReplanStatus.FAILED, "provider_schema_invalid"),
        ("empty", ReplanStatus.NEEDS_INPUT, "data_missing"),
        ("timeout", ReplanStatus.FAILED, "provider_timeout"),
        ("deadline", ReplanStatus.FAILED, "provider_timeout"),
        ("cancel", None, None),
    ),
)
@pytest.mark.parametrize("endpoint", ("geocode", "direction", "place", "chat"))
def test_required_failure_preserves_plan_and_bounded_attempts(
    fault: str,
    endpoint: str,
    expected_status: ReplanStatus | None,
    expected_code: str | None,
) -> None:
    job, command, executor, transport, _ = setup(index=1, fault=fault, endpoint=endpoint)
    original = copy.deepcopy(job)
    if fault == "cancel":
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(executor.execute(job, record(job, command)))
    else:
        result = asyncio.run(executor.execute(job, record(job, command)))
        assert result.commit is None
        assert result.outcome is not None
        if fault == "empty" and endpoint == "chat":
            expected_status = ReplanStatus.FAILED
            expected_code = "provider_schema_invalid"
        assert result.outcome.status is expected_status
        assert result.outcome.error_code == expected_code
    assert job == original
    count_calls = sum(endpoint in p for p, _ in transport.calls)
    assert 1 <= count_calls <= (1 if endpoint == "chat" else 2)
    assert endpoint in transport.calls[-1][0]


def test_model_invalid_after_single_repair_stops_without_later_calls() -> None:
    job, command, executor, transport, _ = setup(index=1, fault="model_invalid", endpoint="chat")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.status is ReplanStatus.FAILED
    assert result.outcome.error_code == "model_output_invalid"
    assert sum(path == "/chat/completions" for path, _ in transport.calls) == 2
    assert not any("direction" in path for path, _ in transport.calls)


@pytest.mark.parametrize("endpoint", ("geocode", "place", "direction"))
def test_retriable_amap_failure_uses_one_extra_attempt_then_succeeds(endpoint: str) -> None:
    job, command, executor, transport, _ = setup(index=1, fault="retry", endpoint=endpoint)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    matching = tuple(path for path, _ in transport.calls if endpoint in path)
    assert matching
    if endpoint == "direction":
        clean_job, clean_command, clean_executor, clean_transport, _ = setup(index=1)
        clean_result = asyncio.run(
            clean_executor.execute(clean_job, record(clean_job, clean_command))
        )
        assert clean_result.commit is not None, clean_result.outcome
        clean_count = sum(endpoint in path for path, _ in clean_transport.calls)
        assert len(matching) == clean_count + 1
    else:
        assert len(matching) == 2


def test_deepseek_has_no_http_retry_and_stops_before_routes() -> None:
    job, command, executor, transport, _ = setup(index=1, fault="retry", endpoint="chat")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.status is ReplanStatus.FAILED
    assert result.outcome.error_code == "provider_unavailable"
    assert sum(path == "/chat/completions" for path, _ in transport.calls) == 1
    assert not any("direction" in path for path, _ in transport.calls)


@pytest.mark.parametrize("endpoint", ("weather/v1", "weatheralert"))
def test_retriable_optional_weather_failure_uses_one_extra_attempt(endpoint: str) -> None:
    job, command, executor, transport, _ = setup(
        index=2, weather=True, fault="retry", endpoint=endpoint
    )

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    matching = tuple(path for path, _ in transport.calls if endpoint in path)
    assert len(matching) == 2
    assert len(set(matching)) == 1


def test_success_path_stays_within_logical_provider_call_caps() -> None:
    job, command, executor, transport, _ = setup(index=1, weather=True)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    paths = tuple(path for path, _ in transport.calls)
    assert sum(path == "/v3/geocode/geo" for path in paths) <= 1
    assert sum(path == "/v5/place/text" for path in paths) <= 1
    assert sum(path == "/chat/completions" for path in paths) <= 2
    assert sum("direction" in path for path in paths) <= 8
    assert sum(path.startswith("/weather/v1/daily/") for path in paths) <= 1
    assert sum(path.startswith("/weatheralert/") for path in paths) <= 1
    assert len(paths) <= 14


def test_required_partial_poi_is_used_with_exact_degradation_evidence() -> None:
    job, command, executor, _, _ = setup(index=1, fault="partial", endpoint="place")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    committed = result.commit.result
    assert committed.plan is not None
    assert committed.plan.days[0].activities[0].location_id == uuid5(
        AMAP_POI_NAMESPACE, "SYNTHETIC-R3"
    )
    assert any(
        error.code is ApiErrorCode.PROVIDER_SCHEMA_INVALID and error.provider == "amap"
        for error in committed.errors
    )
    assert any(
        uncertainty.code == "provider_degraded" and uncertainty.source_ids
        for uncertainty in committed.uncertainties
    )


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("fault", ("401", "429", "503", "schema", "timeout"))
def test_optional_weather_omission_is_evidenced(index: int, fault: str) -> None:
    job, command, executor, transport, _ = setup(
        index=index, weather=True, fault=fault, endpoint="weather/v1"
    )
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    assert result.commit.result.plan.days[0].weather is None
    assert any(u.code == "weather_incomplete" for u in result.commit.result.uncertainties)


def test_available_weather_uses_distinct_forecast_and_alert_adapters() -> None:
    job, command, executor, transport, _ = setup(index=2, weather=True)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    calls = tuple(path for path, _ in transport.calls)
    assert sum(path.startswith("/weather/v1/daily/") for path in calls) == 1
    assert sum(path.startswith("/weatheralert/") for path in calls) == 1
    assert result.commit.result.plan is not None
    assert result.commit.result.plan.days[0].weather is not None
    source_types = {source.source_type for source in result.commit.result.sources}
    assert "qweather_daily_forecast" in source_types
    assert "qweather_current_alerts" in source_types
    assert not any(
        uncertainty.code == "weather_incomplete"
        for uncertainty in result.commit.result.uncertainties
    )


def test_partial_weather_keeps_usable_forecast_and_exact_degradation_evidence() -> None:
    job, command, executor, _, _ = setup(
        index=2, weather=True, fault="partial", endpoint="weather/v1"
    )

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    committed = result.commit.result
    assert committed.plan is not None
    assert committed.plan.days[0].weather is not None
    assert any(
        error.code is ApiErrorCode.PROVIDER_SCHEMA_INVALID and error.provider == "qweather"
        for error in committed.errors
    )
    degraded = tuple(
        uncertainty
        for uncertainty in committed.uncertainties
        if uncertainty.code == "provider_degraded"
    )
    assert len(degraded) == 1
    assert degraded[0].source_ids
    assert "部分外部服务只返回了不完整数据。" in committed.warnings


def test_stale_optional_alert_is_omitted_and_precisely_diagnosed() -> None:
    job, command, executor, _, _ = setup(
        index=2, weather=True, fault="stale", endpoint="weatheralert"
    )

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    committed = result.commit.result
    assert committed.plan is not None
    assert committed.plan.days[0].weather is not None
    assert committed.plan.days[0].weather.alerts == ()
    assert any(
        error.code is ApiErrorCode.DATA_STALE
        and error.provider == "qweather"
        and error.diagnostic_code == "weather_alert_stale"
        and not error.retryable
        for error in committed.errors
    )
    assert any(uncertainty.code == "weather_incomplete" for uncertainty in committed.uncertainties)


def test_historical_diagnostics_remain_an_exact_prefix_with_safe_new_additions() -> None:
    job = prepared()
    activity = plan_of(job).days[0].activities[0]
    assert job.result is not None
    source_id = job.result.sources[0].source_id
    historical_error = ApiError(
        code=ApiErrorCode.DATA_STALE,
        message="历史合成诊断。",
        provider="amap",
        diagnostic_code="historical_synthetic",
        retryable=False,
    )
    historical_uncertainty = Uncertainty(
        code="historical_synthetic",
        message="历史合成不确定性。",
        affected_refs=(activity.item_id,),
        source_ids=(source_id,),
    )
    historical_errors = (historical_error, historical_error)
    historical_warnings = ("历史合成警告。", "历史合成警告。")
    historical_uncertainties = (historical_uncertainty, historical_uncertainty)
    job = modified(
        job,
        status=PlanningStatus.PARTIAL,
        errors=historical_errors,
        warnings=historical_warnings,
        uncertainties=historical_uncertainties,
    )
    job, command, executor, _, _ = setup(index=3, job=job)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    committed = result.commit.result
    assert committed.errors[: len(historical_errors)] == historical_errors
    assert committed.warnings[: len(historical_warnings)] == historical_warnings
    assert committed.uncertainties[: len(historical_uncertainties)] == historical_uncertainties
    for values, prefix in (
        (committed.errors, historical_errors),
        (committed.warnings, historical_warnings),
        (committed.uncertainties, historical_uncertainties),
    ):
        additions = values[len(prefix) :]
        assert len(additions) == len(tuple(dict.fromkeys(additions)))


def test_replace_then_delete_normalizes_history_and_allows_adjust() -> None:
    job = with_unknown_intercity_cost(prepared())
    job, command, executor, _, first_clock = setup(index=1, job=job)
    replaced = asyncio.run(executor.execute(job, record(job, command)))
    assert replaced.commit is not None, replaced.outcome
    original_replace_result = copy.deepcopy(replaced.commit.result)
    replaced_job = replace(
        job,
        status=replaced.commit.result.status,
        version=job.version + 1,
        updated_at=NOW + timedelta(seconds=first_clock.seconds),
        result=replaced.commit.result,
    )
    before_delete = copy.deepcopy(plan_of(replaced_job))
    historical = replaced.commit.result.uncertainties

    replaced_job, delete, delete_executor, delete_transport, second_clock = setup(
        index=0, job=replaced_job, source_id_start=20000
    )
    assert isinstance(delete, DeleteActivity)
    second_clock.seconds = first_clock.seconds
    delete_at = second_clock.utc()
    delete_impact = ReplanFactProjector().analyze(replaced_job, delete, evaluated_at=delete_at)
    historical_route_refs = {
        ref
        for uncertainty in historical
        for ref in uncertainty.affected_refs
        if ref in {route.route_id for route in before_delete.days[0].routes}
    }
    assert historical_route_refs & set(delete_impact.route_refs)

    deleted = asyncio.run(
        delete_executor.execute(
            replaced_job,
            record(
                replaced_job,
                delete,
                evaluated_at=delete_at,
                replan_id=UUID(int=9101),
            ),
        )
    )

    assert deleted.commit is not None, deleted.outcome
    after_delete = deleted.commit.result
    assert after_delete.plan is not None
    removed_refs = set(deleted.commit.change_set.removed_refs)
    expected_history = tuple(
        uncertainty
        if retained_refs == uncertainty.affected_refs
        else uncertainty.model_copy(update={"affected_refs": retained_refs})
        for uncertainty in historical
        if (
            retained_refs := tuple(
                ref for ref in uncertainty.affected_refs if ref not in removed_refs
            )
        )
        or not uncertainty.affected_refs
    )
    assert after_delete.uncertainties[: len(expected_history)] == expected_history
    assert all(
        set(uncertainty.affected_refs)
        <= ReplanFactProjector().project(after_delete, evaluated_at=delete_at).reference_ids
        for uncertainty in after_delete.uncertainties
    )
    assert after_delete.plan.days[0].activities == before_delete.days[0].activities[1:]
    assert after_delete.plan.days[1] == before_delete.days[1]
    assert delete.target_activity_id in deleted.commit.change_set.removed_refs
    assert historical_route_refs <= set(deleted.commit.change_set.removed_refs)
    delete_paths = [path for path, _ in delete_transport.calls]
    assert delete_paths.count("/v3/geocode/geo") == 1
    assert sum("direction" in path for path in delete_paths) == 1
    assert not any(path in {"/chat/completions", "/v5/place/text"} for path in delete_paths)
    assert replaced.commit.result == original_replace_result

    deleted_job = replace(
        replaced_job,
        status=after_delete.status,
        version=replaced_job.version + 1,
        updated_at=NOW + timedelta(seconds=second_clock.seconds),
        result=after_delete,
    )
    deleted_job, adjust, adjust_executor, adjust_transport, third_clock = setup(
        index=2, job=deleted_job, source_id_start=30000
    )
    third_clock.seconds = second_clock.seconds
    adjust_at = third_clock.utc()
    adjusted = asyncio.run(
        adjust_executor.execute(
            deleted_job,
            record(
                deleted_job,
                adjust,
                evaluated_at=adjust_at,
                replan_id=UUID(int=9201),
            ),
        )
    )

    assert adjusted.commit is not None, adjusted.outcome
    assert adjusted.commit.change_set.changed_refs
    assert replaced.commit.result == original_replace_result
    assert adjust_transport.calls == []
    assert adjusted.commit.result.plan is not None
    intercity = next(
        cost
        for cost in adjusted.commit.result.plan.budget_summary.cost_items
        if cost.category.value == "intercity_transport"
    )
    assert intercity.confidence.value == "unknown"
    assert intercity.amount is None


def test_hard_constraints_add_typed_unverified_evidence() -> None:
    job = prepared()
    request = job.request.model_copy(
        update={
            "preferences": job.request.preferences.model_copy(
                update={"hard_constraints": ("synthetic constraint",)}
            )
        }
    )
    job = replace(
        job,
        request=request,
        request_fingerprint=request_fingerprint(request),
    )
    job, command, executor, _, _ = setup(index=2, job=job)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert any(
        uncertainty.code == "hard_constraint_unverified"
        for uncertainty in result.commit.result.uncertainties
    )


def test_empty_transit_falls_back_only_to_approved_walking() -> None:
    job, command, executor, transport, _ = setup(fault="empty", endpoint="transit")
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is not None, result.outcome
    assert any("walking" in p for p, _ in transport.calls)
    starts = [t for p, t in transport.calls if "direction" in p]
    assert all(b - a >= 0.5 for a, b in zip(starts, starts[1:], strict=False))


def test_adapter_rejects_structurally_invalid_transit_without_fallback() -> None:
    job, command, executor, transport, _ = setup(fault="schema", endpoint="transit")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.error_code == "provider_schema_invalid"
    paths = tuple(path for path, _ in transport.calls)
    assert "/v5/direction/transit/integrated" in paths
    assert "/v5/direction/walking" not in paths


def test_provider_unavailable_transit_never_falls_back() -> None:
    job, command, executor, transport, _ = setup(fault="503", endpoint="transit")

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.error_code == "provider_unavailable"
    assert not any("walking" in path for path, _ in transport.calls)


def test_final_budget_is_recomputed_from_candidate_cost_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = build_replan_candidate

    def poisoned_analysis(
        job: PlanningJob,
        command: ReplanCommand,
        impact: ImpactAnalysis,
        *,
        evaluated_at: datetime,
        replacement: ActivityReplacement | None = None,
    ) -> ReplanCandidate:
        draft = original(
            job,
            command,
            impact,
            evaluated_at=evaluated_at,
            replacement=replacement,
        )
        poisoned = replace(
            draft.budget_analysis.after,
            known_total=DomainMoney(Decimal("0.00")),
        )
        return replace(
            draft,
            budget_analysis=replace(draft.budget_analysis, after=poisoned),
        )

    monkeypatch.setattr(planner_module, "build_replan_candidate", poisoned_analysis)
    job, command, executor, _, _ = setup(index=2)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    summary = result.commit.result.plan.budget_summary
    assert summary.known_total.amount == Decimal("2140.00")
    assert summary.unknown_count == 0
    assert type(summary.assessment) is type(plan_of(job).budget_summary.assessment)
    assert summary.assessment == "within_budget"


def test_known_over_budget_candidate_is_rejected_without_http_calls() -> None:
    job = prepared()
    low_budget = Money(amount=Decimal("1000.00"))
    request = job.request.model_copy(update={"total_budget": low_budget})
    plan = plan_of(job)
    budget = plan.budget_summary.model_copy(
        update={
            "budget": low_budget,
            "assessment": type(plan.budget_summary.assessment)("over_budget"),
        }
    )
    job = replace(
        modified(job, plan=plan.model_copy(update={"budget_summary": budget})),
        request=request,
        request_fingerprint=request_fingerprint(request),
    )
    job, command, executor, transport, _ = setup(index=2, job=job)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is None
    assert result.outcome is not None
    assert result.outcome.status is ReplanStatus.CONFLICT
    assert result.outcome.error_code == "replan_change_scope_conflict"
    assert transport.calls == []


@pytest.mark.parametrize(("index", "unknown_count"), ((0, 2), (3, 1)))
def test_candidate_unknown_costs_remain_unknown_and_are_not_zero(
    index: int, unknown_count: int
) -> None:
    job, command, executor, _, _ = setup(index=index)

    result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert result.commit.result.plan is not None
    summary = result.commit.result.plan.budget_summary
    unknown = [item for item in summary.cost_items if item.confidence.value == "unknown"]
    assert len(unknown) == unknown_count
    assert all(item.amount is None for item in unknown)
    assert summary.unknown_count == unknown_count
    assert type(summary.assessment) is type(plan_of(job).budget_summary.assessment)
    assert summary.assessment == "budget_indeterminate"


def test_execution_has_no_file_environment_database_network_or_process_side_effects() -> None:
    # Other collected API tests legitimately import the app. Preserve the original
    # import and side-effect assertions in a fresh interpreter instead of relaxing them.
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import pytest; from tests.application.test_provider_replan_planner import "
            "_assert_execution_has_no_external_side_effects as check; "
            "guard = pytest.MonkeyPatch(); check(guard); guard.undo()",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "APP_ENV": "test", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _assert_execution_has_no_external_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    job, command, executor, transport, _ = setup(index=1, weather=True)
    forbidden_modules = {
        "intelligent_travel_assistant.app",
        "intelligent_travel_assistant.bootstrap",
        "intelligent_travel_assistant.main",
    }
    assert forbidden_modules.isdisjoint(sys.modules)

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected external side effect")

    with monkeypatch.context() as guard:
        for target, name in (
            (builtins, "open"),
            (Path, "write_text"),
            (Path, "write_bytes"),
            (Path, "mkdir"),
            (Path, "touch"),
            (os, "putenv"),
            (os, "unsetenv"),
            (socket, "create_connection"),
            (socket, "getaddrinfo"),
            (sqlite3, "connect"),
            (subprocess, "Popen"),
        ):
            guard.setattr(target, name, denied)
        result = asyncio.run(executor.execute(job, record(job, command)))

    assert result.commit is not None, result.outcome
    assert transport.calls
    assert forbidden_modules.isdisjoint(sys.modules)


def test_run_late_replan_result_is_rejected_before_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    from intelligent_travel_assistant.application.tooling.governance import RunCallBudget
    from intelligent_travel_assistant.application.tooling.resilience import ProviderRunSession

    job, command, executor, _transport, _ = setup(index=1)
    before = copy.deepcopy(job)
    readings = [0.0]
    session = ProviderRunSession(RunCallBudget(clock=lambda: readings[0], deadline_seconds=1))
    planner = executor._planner
    assert isinstance(planner, ProviderReplanPlanner)
    planner.run_session = session
    original = planner._execute_with_runtime

    async def late_result(*args: Any, **kwargs: Any) -> Any:
        result = await original(*args, **kwargs)
        readings[0] = 2.0
        return result

    monkeypatch.setattr(planner, "_execute_with_runtime", late_result)
    result = asyncio.run(executor.execute(job, record(job, command)))
    assert result.commit is None
    assert result.outcome is not None and result.outcome.status is ReplanStatus.FAILED
    assert job == before
    assert session.snapshot()["reason"] == "deadline"
