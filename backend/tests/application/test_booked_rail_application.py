"""F-004C V4 deterministic application wiring and Agent isolation."""

from __future__ import annotations

import asyncio
import json
from typing import cast

from tests.application.test_multicity_provider_planning import (
    NOW,
    _id,
    _orchestrator,
    _proposal,
    _result,
)
from tests.contracts.test_booked_rail_trip_planning_contracts import money, request_payload

from intelligent_travel_assistant.adapters.fakes import FakeDeepSeekAdapter
from intelligent_travel_assistant.adapters.providers.deepseek import (
    _planning_context_payload,
    _repair_brief_payload,
)
from intelligent_travel_assistant.adapters.repositories import InMemoryPlanningJobRepository
from intelligent_travel_assistant.application.ports import (
    ModelTextOutput,
    PlanningContext,
    PlanRepairBrief,
)
from intelligent_travel_assistant.application.repositories import PlanningJob, PlanningJobResultV4
from intelligent_travel_assistant.application.services import (
    MultiCityPlanningOrchestrator,
    OfflinePlanningOrchestrator,
    ProviderPlanningJobExecutor,
)
from intelligent_travel_assistant.application.tooling import (
    ToolCallGovernor,
    multicity_task_timeout_seconds,
    multicity_tool_call_policies,
)
from intelligent_travel_assistant.contracts import (
    DataFreshness,
    PlanningStatus,
    ProviderName,
    TripPlanRequestV4,
)
from intelligent_travel_assistant.domain import Provider


def request() -> TripPlanRequestV4:
    payload = request_payload()
    stays = cast(list[dict[str, object]], payload["city_stays"])
    for stay in stays:
        accommodation = cast(dict[str, object], stay["accommodation"])
        accommodation["one_night_cost"] = money("500.00")
    return TripPlanRequestV4.model_validate(payload)


def test_v4_orchestrator_rebuilds_booked_rail_outside_the_agent_boundary() -> None:
    orchestrator, amap, qweather, deepseek, _governors = _orchestrator()

    result = asyncio.run(orchestrator.plan(request(), job_id=_id("v4-job"), evaluated_at=NOW))

    assert isinstance(result, PlanningJobResultV4)
    assert result.status is PlanningStatus.PARTIAL
    assert result.plan is not None
    assert result.plan.plan_format_version == "4"
    segment = result.plan.intercity_segments[0]
    assert segment.service_number == "G1234"
    source = next(item for item in result.sources if item.source_id in segment.source_ids)
    assert source.provider is ProviderName.USER
    assert source.freshness is DataFreshness.UNKNOWN_VALIDITY
    assert source.attributions == ("用户提供",)
    assert source.warnings == ("未核验班次、票价、余票或库存",)

    context = deepseek.calls[0].request
    assert isinstance(context, PlanningContext)
    model_payload = _planning_context_payload(context)
    serialized = json.dumps(model_payload, ensure_ascii=False)
    assert "service_number" not in serialized
    assert "G1234" not in serialized
    assert "intercity_segments" not in serialized
    assert len(amap.calls) == 12
    assert len(qweather.calls) == 4
    assert len(deepseek.calls) == 1


def test_provider_executor_persists_v4_without_an_intercity_provider_call() -> None:
    async def execute() -> PlanningJob:
        multicity, amap, qweather, deepseek, _governors = _orchestrator()
        repository = InMemoryPlanningJobRepository(clock=lambda: NOW)
        reservation = await repository.get_or_create(request())
        legacy = OfflinePlanningOrchestrator(
            amap,
            qweather,
            deepseek,
            lambda: ToolCallGovernor(clock=lambda: 0.0),
        )
        executor = ProviderPlanningJobExecutor(
            repository,
            legacy,
            clock=lambda: NOW,
            multicity_orchestrator=multicity,
        )
        await executor.execute(reservation.job.job_id)
        return await repository.get(reservation.job.job_id)

    job = asyncio.run(execute())

    assert job.status is PlanningStatus.PARTIAL
    assert isinstance(job.result, PlanningJobResultV4)
    assert job.result.plan is not None
    assert job.result.plan.plan_format_version == "4"
    assert job.result.plan.intercity_segments[0].service_number == "G1234"


def test_v4_generation_and_repair_payloads_cannot_receive_private_sentinel() -> None:
    _, amap, qweather, _, _ = _orchestrator()
    valid = _proposal(
        _id("poi:0"),
        _id("poi:1"),
        _id("source:poi:0"),
        _id("source:poi:1"),
    )
    deepseek = FakeDeepSeekAdapter(
        generation_results=(_result(Provider.DEEPSEEK, ModelTextOutput("{}"), "invalid-model"),),
        repair_results=(_result(Provider.DEEPSEEK, ModelTextOutput(valid), "repair-model"),),
    )

    def governor_factory(city_count: int, day_count: int) -> ToolCallGovernor:
        return ToolCallGovernor(
            clock=lambda: 0.0,
            policies=multicity_tool_call_policies(
                city_count=city_count,
                day_count=day_count,
            ),
            task_timeout_seconds=multicity_task_timeout_seconds(
                city_count=city_count,
                day_count=day_count,
            ),
        )

    orchestrator = MultiCityPlanningOrchestrator(
        amap,
        qweather,
        deepseek,
        governor_factory,
    )
    result = asyncio.run(
        orchestrator.plan(request(), job_id=_id("v4-private-sentinel"), evaluated_at=NOW)
    )

    assert result.plan is not None
    assert len(deepseek.calls) == 2
    generation = deepseek.calls[0].request
    repair = deepseek.calls[1].request
    assert isinstance(generation, PlanningContext)
    assert isinstance(repair, PlanRepairBrief)
    assert generation.free_text == ""
    assert generation.hard_constraints == ()
    generation_payload = _planning_context_payload(generation)
    repair_payload = _repair_brief_payload(repair)
    serialized = json.dumps(
        {"generation": generation_payload, "repair": repair_payload},
        ensure_ascii=False,
    )
    assert "SYNTHETIC_V4_PRIVATE_SENTINEL" not in serialized
    assert "free_text" not in repair_payload
    assert "hard_constraints" not in repair_payload
