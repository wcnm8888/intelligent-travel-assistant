"""D-028 fact projection: synthetic typed inputs, no application or external I/O."""

from __future__ import annotations

import builtins
import copy
import json
import os
import socket
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

import intelligent_travel_assistant.application.services.replan_facts as replan_facts_module
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    request_fingerprint,
)
from intelligent_travel_assistant.application.services.offline_planning import RouteLookupStage
from intelligent_travel_assistant.application.services.offline_planning import (
    _lookup_allows_fallback as original_lookup_allows_fallback,
)
from intelligent_travel_assistant.application.services.replan_facts import ReplanFactProjector
from intelligent_travel_assistant.contracts import (
    Money,
    PlanningStatus,
    TripPlan,
    TripPlanRequest,
    TripPlanRequestV2,
    TripPlanResponse,
    TripPlanV2,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    BudgetCostItem,
    ChangeEntityKind,
    CostCategory,
    CostConfidence,
    DeleteActivity,
    DomainInvariantError,
    ReorderActivities,
    ReplaceActivity,
    ReplanCommand,
    SourceAction,
    summarize_budget,
)
from intelligent_travel_assistant.domain import (
    Money as DomainMoney,
)

ROOT = Path(__file__).resolve().parents[1] / "fixtures"
# All synthetic fetched_at values must precede the explicit evaluation instant.
NOW = datetime.fromisoformat("2026-08-13T10:01:00+08:00")
PROJECTOR = ReplanFactProjector()


def baseline(v2: bool = False) -> PlanningJob:
    payload = json.loads((ROOT / "synthetic_hangzhou_ready.json").read_text("utf-8"))["response"]
    request_data = json.loads((ROOT / "synthetic_hangzhou_request.json").read_text("utf-8"))[
        "request"
    ]
    day = payload["plan"]["days"][0]
    extra = copy.deepcopy(payload["plan"]["days"][1]["activities"][0])
    extra.update(item_id=str(UUID(int=101)), start_time="14:00:00", end_time="15:00:00")
    day["activities"].append(extra)
    nodes = [
        day["accommodation_location_id"],
        *(a["location_id"] for a in day["activities"]),
        day["accommodation_location_id"],
    ]
    day["routes"] = [
        dict(
            day["routes"][0],
            route_id=str(UUID(int=201 + i)),
            origin_location_id=a,
            destination_location_id=b,
        )
        for i, (a, b) in enumerate(zip(nodes, nodes[1:], strict=False))
    ]
    response = TripPlanResponse.model_validate(payload)
    assert response.plan is not None
    request: TripPlanRequest = TripPlanRequest.model_validate(request_data)
    plan: TripPlan = response.plan
    if v2:
        request = TripPlanRequestV2.model_validate(
            dict(request_data, request_version="2", end_date="2026-08-16")
        )
        plan = TripPlanV2.model_validate(dict(plan.model_dump(), plan_format_version="2"))
    result = PlanningJobResult(
        response.status,
        response.resolved_destination,
        plan,
        response.violations,
        response.warnings,
        response.uncertainties,
        response.sources,
        response.errors,
        False,
    )
    return PlanningJob(
        response.job_id,
        response.trace_id,
        request.client_request_id,
        request_fingerprint(request),
        request,
        response.status,
        1,
        5,
        False,
        NOW,
        NOW,
        result,
    )


def plan_of(job: PlanningJob) -> TripPlan:
    assert isinstance(job.result, PlanningJobResult) and isinstance(job.result.plan, TripPlan)
    return job.result.plan


def modified(job: PlanningJob, **fields: Any) -> PlanningJob:
    """Simulate a corrupted/deserialized typed object without trusting model_copy."""
    changed = copy.deepcopy(job)
    assert changed.result is not None
    for name, value in fields.items():
        object.__setattr__(changed.result, name, value)
    return changed


def commands(job: PlanningJob) -> tuple[ReplanCommand, ...]:
    day = plan_of(job).days[0]
    target = day.activities[0].item_id
    return (
        DeleteActivity(target),
        ReplaceActivity(target, ("museum",)),
        AdjustActivityTime(target, time(10, 15), time(12, 15)),
        ReorderActivities(day.local_date, tuple(a.item_id for a in reversed(day.activities))),
    )


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
def test_four_commands_are_deterministic_and_preserve_inputs(v2: bool, index: int) -> None:
    job = baseline(v2)
    original = copy.deepcopy(job)
    command = commands(job)[index]
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    assert impact == PROJECTOR.analyze(job, command, evaluated_at=NOW)
    assert facts.snapshots == PROJECTOR.project(job.result, evaluated_at=NOW).snapshots
    assert set(s.kind for s in facts.snapshots) == set(ChangeEntityKind)
    assert impact.affected_dates == (plan_of(job).start_date,)
    assert set(impact.route_refs) <= {r.route_id for r in plan_of(job).days[0].routes}
    assert job == original


@pytest.mark.parametrize("index", range(4))
def test_plan_level_unknown_and_aggregate_costs_are_not_zero(index: int) -> None:
    job = baseline()
    plan = plan_of(job)
    costs = tuple(
        c.model_copy(update={"confidence": "unknown", "amount": None})
        if c.category.value == "ticket"
        else c
        for c in plan.budget_summary.cost_items
    )
    summary = plan.budget_summary.model_copy(
        update={"cost_items": costs, "unknown_count": 1, "assessment": "budget_indeterminate"}
    )
    job = modified(job, plan=plan.model_copy(update={"budget_summary": summary}))
    # Synthetic fixture's ticket is zero; native production also has one aggregate unknown.
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    budget = facts.budget_effect(commands(job)[index])
    assert budget.before.unknown_count == 1
    assert budget.after.unknown_count >= 1
    assert all(c.amount is None for c in budget.after.cost_items if c.confidence.value == "unknown")
    assert PROJECTOR.analyze(job, commands(job)[index], evaluated_at=NOW).confirmation_required


@pytest.mark.parametrize(
    "change",
    (
        "source",
        "location",
        "route",
        "cost",
        "date",
        "city",
        "owner",
        "summary",
        "other",
        "duplicate",
    ),
)
def test_unprovable_or_corrupt_references_fail_closed(change: str) -> None:
    job = baseline()
    plan = plan_of(job)
    day = plan.days[0]
    if change == "source":
        job = modified(job, sources=())
    elif change == "location":
        plan = plan.model_copy(update={"locations": plan.locations[1:]})
    elif change == "route":
        day = day.model_copy(update={"routes": tuple(reversed(day.routes))})
    elif change == "cost":
        activity = day.activities[0].model_copy(
            update={
                "cost_items": (
                    plan.budget_summary.cost_items[0].model_copy(update={"cost_id": UUID(int=999)}),
                )
            }
        )
        day = day.model_copy(update={"activities": (activity, *day.activities[1:])})
    elif change == "owner":
        day = day.model_copy(
            update={
                "activities": tuple(
                    a.model_copy(update={"cost_items": (plan.budget_summary.cost_items[0],)})
                    for a in day.activities
                )
            }
        )
    elif change == "date":
        day = day.model_copy(update={"local_date": plan.end_date})
    elif change == "city":
        plan = plan.model_copy(
            update={
                "locations": (
                    plan.locations[0].model_copy(update={"city_adcode": "110100"}),
                    *plan.locations[1:],
                )
            }
        )
    elif change in {"summary", "other", "duplicate"}:
        budget = plan.budget_summary
        updates = (
            {"unknown_count": 3}
            if change == "summary"
            else {"cost_items": (*budget.cost_items, budget.cost_items[0])}
            if change == "duplicate"
            else {
                "cost_items": (
                    budget.cost_items[0].model_copy(update={"category": "other"}),
                    *budget.cost_items[1:],
                )
            }
        )
        plan = plan.model_copy(update={"budget_summary": budget.model_copy(update=updates)})
    if change != "source":
        job = modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    with pytest.raises(DomainInvariantError):
        PROJECTOR.analyze(job, commands(baseline())[0], evaluated_at=NOW)


@pytest.mark.parametrize("validity", ("fresh", "unknown", "stale", "future", "reversed", "naive"))
def test_freshness_uses_explicit_time_not_cached_label(validity: str) -> None:
    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    source = job.result.sources[0]
    updates: dict[str, Any] = {"freshness": "stale", "valid_until": NOW + timedelta(hours=1)}
    if validity == "unknown":
        updates["valid_until"] = None
    if validity == "stale":
        updates.update(fetched_at=NOW - timedelta(days=2), valid_until=NOW - timedelta(days=1))
    if validity == "future":
        updates["fetched_at"] = NOW + timedelta(minutes=1)
    if validity == "reversed":
        updates["valid_until"] = NOW - timedelta(days=1)
    if validity == "naive":
        updates["fetched_at"] = NOW.replace(tzinfo=None)
    job = modified(job, sources=(source.model_copy(update=updates), *job.result.sources[1:]))
    if validity in {"future", "reversed", "naive"}:
        with pytest.raises(DomainInvariantError):
            PROJECTOR.project(job.result, evaluated_at=NOW)
    else:
        facts = PROJECTOR.project(job.result, evaluated_at=NOW)
        state = next(s for s in facts.context.sources if s.source_id == source.source_id)
        assert state.freshness.value == {"unknown": "unknown_validity"}.get(validity, validity)


def test_shared_sources_are_not_dropped_and_schedule_ids_survive_plan_revision() -> None:
    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    impact = PROJECTOR.analyze(job, commands(job)[0], evaluated_at=NOW)
    assert all(action.action is not SourceAction.DROP for action in impact.source_actions)
    original = PROJECTOR.project(job.result, evaluated_at=NOW)
    result = replace(job.result, plan=plan_of(job).model_copy(update={"plan_id": UUID(int=1000)}))
    assert PROJECTOR.project(result, evaluated_at=NOW).snapshots == original.snapshots


def adjusted(job: PlanningJob) -> PlanningJobResult:
    assert isinstance(job.result, PlanningJobResult)
    plan = plan_of(job)
    day = plan.days[0]
    activity = day.activities[0].model_copy(
        update={"start_time": time(10, 15), "end_time": time(12, 15)}
    )
    return replace(
        job.result,
        status=PlanningStatus.PARTIAL,
        plan=plan.model_copy(
            update={
                "plan_id": UUID(int=1000),
                "days": (
                    day.model_copy(update={"activities": (activity, *day.activities[1:])}),
                    plan.days[1],
                ),
            }
        ),
    )


def test_precise_derived_schedule_scope_accepts_only_command_change() -> None:
    job = baseline()
    command = commands(job)[2]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    changes = PROJECTOR.changes(job, command, impact, adjusted(job), evaluated_at=NOW)
    assert changes.change_codes == ("schedule",)
    assert len(changes.changed_refs) == 1


@pytest.mark.parametrize(
    "field", ("cost", "source", "schedule", "anchor", "city", "date", "location", "errors")
)
def test_candidate_cannot_use_full_plan_scope(field: str) -> None:
    job = baseline()
    result = adjusted(job)
    assert isinstance(result.plan, TripPlan)
    plan = result.plan
    if field == "cost":
        item = plan.budget_summary.cost_items[0].model_copy(update={"description": "changed"})
        plan = plan.model_copy(
            update={
                "budget_summary": plan.budget_summary.model_copy(
                    update={"cost_items": (item, *plan.budget_summary.cost_items[1:])}
                )
            }
        )
    elif field == "source":
        object.__setattr__(
            result,
            "sources",
            (result.sources[0].model_copy(update={"warnings": ("changed",)}), *result.sources[1:]),
        )
    elif field == "location":
        plan = plan.model_copy(
            update={
                "locations": (
                    plan.locations[0].model_copy(update={"name": "changed"}),
                    *plan.locations[1:],
                )
            }
        )
    elif field in {"city", "date"}:
        plan = plan.model_copy(
            update={"city_adcode": "110100"}
            if field == "city"
            else {"end_date": plan.end_date + timedelta(days=1)}
        )
    elif field == "errors":
        object.__setattr__(result, "warnings", ("unproven change",))
    else:
        day = plan.days[1]
        day = (
            day.model_copy(update={"accommodation_location_id": plan.locations[1].location_id})
            if field == "anchor"
            else day.model_copy(
                update={
                    "activities": (day.activities[0].model_copy(update={"end_time": time(13)}),)
                }
            )
        )
        plan = plan.model_copy(update={"days": (plan.days[0], day)})
    object.__setattr__(result, "plan", plan)
    command = commands(job)[2]
    with pytest.raises(DomainInvariantError):
        PROJECTOR.changes(
            job,
            command,
            PROJECTOR.analyze(job, command, evaluated_at=NOW),
            result,
            evaluated_at=NOW,
        )


def test_projection_and_changes_have_zero_io() -> None:
    # Full-suite collection may import the app; the original safety assertions
    # must observe only this module and its operation in a clean interpreter.
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys, pytest; from tests.application.test_replan_facts import "
            "_assert_projection_and_changes_have_zero_io as check; "
            "check(pytest.MonkeyPatch())",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "APP_ENV": "test", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _assert_projection_and_changes_have_zero_io(monkeypatch: pytest.MonkeyPatch) -> None:
    job = baseline()
    original = copy.deepcopy(job)
    candidate = adjusted(job)

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("projection attempted I/O")

    with monkeypatch.context() as guard:
        for target, name in (
            (builtins, "open"),
            (Path, "open"),
            (os, "getenv"),
            (socket, "socket"),
            (sqlite3, "connect"),
        ):
            guard.setattr(target, name, denied)
        command = commands(job)[2]
        impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
        PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
    assert job == original
    assert "intelligent_travel_assistant.app" not in sys.modules


def with_costs(job: PlanningJob, items: tuple[Any, ...]) -> PlanningJob:
    plan = plan_of(job)
    total = summarize_budget(
        DomainMoney(plan.budget_summary.budget.amount),
        tuple(
            BudgetCostItem(
                c.cost_id,
                CostCategory(c.category),
                CostConfidence(c.confidence),
                DomainMoney(c.amount.amount) if c.amount else None,
                c.source_ids,
            )
            for c in items
        ),
    )
    summary = plan.budget_summary.model_copy(
        update={
            "cost_items": items,
            "known_total": Money(amount=total.known_total.amount),
            "unknown_count": total.unknown_count,
            "assessment": total.assessment.value,
        }
    )
    return modified(job, plan=plan.model_copy(update={"budget_summary": summary}))


def with_unknown_intercity_cost(job: PlanningJob) -> PlanningJob:
    request = job.request.model_copy(update={"intercity_transport_cost": None})
    costs = tuple(
        cost.model_copy(update={"confidence": "unknown", "amount": None, "source_ids": ()})
        if cost.category.value == "intercity_transport"
        else cost
        for cost in plan_of(job).budget_summary.cost_items
    )
    return replace(
        with_costs(job, costs),
        request=request,
        request_fingerprint=request_fingerprint(request),
    )


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("unknown", (False, True))
def test_local_cost_ownership_changes_only_proven_items(index: int, unknown: bool) -> None:
    job = baseline()
    plan = plan_of(job)
    ticket = next(c for c in plan.budget_summary.cost_items if c.category.value == "ticket")
    ticket = ticket.model_copy(
        update={
            "amount": None if unknown else Money(amount=Decimal("80")),
            "confidence": "unknown" if unknown else "estimated",
        }
    )
    day = plan.days[0]
    day = day.model_copy(
        update={
            "activities": (
                day.activities[0].model_copy(update={"cost_items": (ticket,)}),
                *day.activities[1:],
            )
        }
    )
    job = with_costs(
        modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])})),
        tuple(ticket if c.cost_id == ticket.cost_id else c for c in plan.budget_summary.cost_items),
    )
    effect = PROJECTOR.project(job.result, evaluated_at=NOW).budget_effect(commands(job)[index])
    before = {c.cost_id: c for c in effect.before.cost_items}
    after = {c.cost_id: c for c in effect.after.cost_items}
    if index == 0:
        assert ticket.cost_id not in after
    elif index == 1:
        assert after[ticket.cost_id].amount is None
    else:
        assert after[ticket.cost_id] == before[ticket.cost_id]
    for c in effect.before.cost_items:
        if c.category in {
            CostCategory.MEAL,
            CostCategory.ACCOMMODATION,
            CostCategory.INTERCITY_TRANSPORT,
        }:
            assert after[c.cost_id] == c


@pytest.mark.parametrize(
    "consumer",
    (
        "activity",
        "cost",
        "location",
        "weather",
        "alert",
        "destination",
        "uncertainty",
        "provenance",
    ),
)
def test_drop_requires_all_consumers_to_disappear(consumer: str) -> None:
    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    plan = plan_of(job)
    sid = UUID(int=3000)
    source = job.result.sources[0].model_copy(update={"source_id": sid})
    day = plan.days[0]
    activity = day.activities[0].model_copy(update={"source_ids": (sid,)})
    day = day.model_copy(update={"activities": (activity, *day.activities[1:])})
    result = replace(job.result, sources=(*job.result.sources, source))
    if consumer == "cost":
        costs = plan.budget_summary.cost_items
        plan = plan.model_copy(
            update={
                "budget_summary": plan.budget_summary.model_copy(
                    update={
                        "cost_items": (
                            costs[0].model_copy(update={"source_ids": (sid,)}),
                            *costs[1:],
                        )
                    }
                )
            }
        )
    elif consumer == "location":
        locs = plan.locations
        plan = plan.model_copy(
            update={"locations": (locs[0].model_copy(update={"source_ids": (sid,)}), *locs[1:])}
        )
    elif consumer in {"weather", "alert"}:
        assert day.weather is not None
        weather = day.weather.model_copy(update={"source_ids": (sid,)})
        if consumer == "alert":
            from intelligent_travel_assistant.contracts.trip_planning import WeatherAlert

            weather = day.weather.model_copy(
                update={
                    "alerts": (
                        WeatherAlert(
                            alert_id="synthetic",
                            title="test",
                            description="synthetic",
                            source_ids=(sid,),
                        ),
                    )
                }
            )
        day = day.model_copy(update={"weather": weather})
    elif consumer == "destination":
        assert result.resolved_destination is not None
        result = replace(
            result,
            resolved_destination=result.resolved_destination.model_copy(
                update={"source_ids": (*result.resolved_destination.source_ids, sid)}
            ),
        )
    elif consumer == "uncertainty":
        from intelligent_travel_assistant.contracts.trip_planning import Uncertainty

        result = replace(
            result,
            uncertainties=(
                *result.uncertainties,
                Uncertainty(code="synthetic", message="test", source_ids=(sid,)),
            ),
        )
    elif consumer == "provenance":
        result = replace(
            result,
            sources=(
                *job.result.sources,
                source.model_copy(update={"provider": "deepseek", "source_type": "model_plan"}),
            ),
        )
    job = replace(
        job, result=replace(result, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    )
    actions = PROJECTOR.analyze(job, commands(job)[0], evaluated_at=NOW).source_actions
    action = next(a.action for a in actions if a.source_id == sid)
    assert (action is SourceAction.DROP) == (consumer == "activity")


def candidate_for(job: PlanningJob, index: int) -> PlanningJobResult:
    """Pure synthetic candidate, never a substitute for R2/production acceptance."""
    assert isinstance(job.result, PlanningJobResult)
    if index == 2:
        return adjusted(job)
    plan = plan_of(job)
    day = plan.days[0]
    activities = (
        day.activities[1:]
        if index == 0
        else (
            (
                day.activities[0].model_copy(
                    update={"item_id": UUID(int=4001), "title": "replacement"}
                ),
                *day.activities[1:],
            )
            if index == 1
            else tuple(reversed(day.activities))
        )
    )
    nodes = [
        day.accommodation_location_id,
        *(a.location_id for a in activities),
        day.accommodation_location_id,
    ]
    routes = tuple(
        day.routes[min(i, len(day.routes) - 1)].model_copy(
            update={
                "route_id": UUID(int=4100 + i),
                "origin_location_id": a,
                "destination_location_id": b,
            }
        )
        for i, (a, b) in enumerate(zip(nodes, nodes[1:], strict=False))
    )
    if index in {0, 1}:
        # Retain the unaffected final route; only the two adjacent legs become a bridge.
        routes = (*routes[:-1], day.routes[-1])
    day = day.model_copy(update={"activities": activities, "routes": routes})
    return replace(
        job.result,
        status=PlanningStatus.PARTIAL,
        plan=plan.model_copy(update={"plan_id": UUID(int=4200), "days": (day, plan.days[1])}),
    )


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
def test_all_command_candidates_have_proven_origins(v2: bool, index: int) -> None:
    job = baseline(v2)
    command = commands(job)[index]
    candidate = candidate_for(job, index)
    saved = copy.deepcopy((job, command, candidate))
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    changes = PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
    assert changes == PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
    assert set(changes.added_refs) == {ref for ref, _ in changes.added_origins}
    assert all(
        origin in {*impact.direct_refs, *impact.route_refs} for _, origin in changes.added_origins
    )
    assert (job, command, candidate) == saved
    if index == 0:
        bridge = candidate.plan.days[0].routes[0].route_id  # type: ignore[union-attr]
        parents = sorted(impact.route_refs, key=str)
        assert dict(changes.added_origins)[bridge] == parents[0]


@pytest.mark.parametrize("kind", tuple(ChangeEntityKind))
def test_each_snapshot_kind_detects_its_full_fields(kind: ChangeEntityKind) -> None:
    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    plan = plan_of(job)
    day = plan.days[0]
    result = job.result
    if kind is ChangeEntityKind.SOURCE:
        result = replace(
            result,
            sources=(
                result.sources[0].model_copy(update={"attributions": ("different",)}),
                *result.sources[1:],
            ),
        )
    elif kind is ChangeEntityKind.COST:
        costs = plan.budget_summary.cost_items
        plan = plan.model_copy(
            update={
                "budget_summary": plan.budget_summary.model_copy(
                    update={
                        "cost_items": (
                            costs[0].model_copy(update={"description": "different"}),
                            *costs[1:],
                        )
                    }
                )
            }
        )
    elif kind is ChangeEntityKind.ROUTE:
        day = day.model_copy(
            update={
                "routes": (
                    day.routes[0].model_copy(
                        update={"distance_meters": day.routes[0].distance_meters + 1}
                    ),
                    *day.routes[1:],
                )
            }
        )
    else:
        field, value = (
            ("title", "different") if kind is ChangeEntityKind.ACTIVITY else ("end_time", time(13))
        )
        day = day.model_copy(
            update={
                "activities": (
                    day.activities[0].model_copy(update={field: value}),
                    *day.activities[1:],
                )
            }
        )
    result = replace(result, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    before = {s.ref_id: s for s in PROJECTOR.project(job.result, evaluated_at=NOW).snapshots}
    after = PROJECTOR.project(result, evaluated_at=NOW).snapshots
    changed = {s.kind for s in after if s != before[s.ref_id]}
    assert kind in changed


@pytest.mark.parametrize(
    "fault",
    (
        "missing_parent",
        "wrong_order",
        "extra_activity",
        "shared_source",
        "collision",
        "wrong_command",
    ),
)
def test_candidate_origin_and_ownership_cannot_be_forged(fault: str) -> None:
    job = baseline()
    command = commands(job)[0]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    result = candidate_for(job, 0)
    assert isinstance(result.plan, TripPlan)
    plan = result.plan
    day = plan.days[0]
    if fault == "missing_parent":
        impact = replace(impact, route_refs=impact.route_refs[:1], transitive_refs=())
    elif fault == "wrong_command":
        command = commands(job)[1]
    elif fault == "wrong_order":
        day = day.model_copy(update={"routes": tuple(reversed(day.routes))})
    elif fault == "extra_activity":
        day = day.model_copy(
            update={
                "activities": (
                    *day.activities,
                    day.activities[0].model_copy(update={"item_id": UUID(int=8000)}),
                )
            }
        )
    elif fault == "collision":
        day = day.model_copy(
            update={
                "routes": (
                    day.routes[0].model_copy(update={"route_id": day.activities[0].item_id}),
                    *day.routes[1:],
                )
            }
        )
    else:
        result = replace(
            result,
            sources=(
                result.sources[0].model_copy(update={"warnings": ("different",)}),
                *result.sources[1:],
            ),
        )
    result = replace(result, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    with pytest.raises(DomainInvariantError):
        PROJECTOR.changes(job, command, impact, result, evaluated_at=NOW)


def proved(case: tuple[Any, ...], events: tuple[Any, ...] | None = None) -> Any:
    from intelligent_travel_assistant.application.services.replan_facts import ReplanEvidence

    job, command, result, impact, event = case
    proof = ReplanEvidence.bind(job, UUID(int=18002), command, result, events or (event,))
    return PROJECTOR.changes(job, command, impact, result, evaluated_at=NOW, evidence=proof)


@pytest.mark.parametrize(
    "fault",
    (
        "provider",
        "endpoint",
        "location",
        "coordinates",
        "date",
        "future",
        "source_fields",
        "weather_forgery",
        "outside_day",
        "refs",
        "old_impact",
        "unknown_operation",
        "raw_warning",
        "prefix_delete",
        "prefix_reorder",
        "prefix_change",
        "capacity",
        "status",
        "retryable",
        "binding_job",
        "binding_command",
        "binding_candidate",
        "binding_version",
        "binding_baseline",
    ),
)
def test_evidence_rejects_forgery_scope_history_and_replay(fault: str) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import ReplanEvidence
    from intelligent_travel_assistant.contracts import PlanningStatus
    from intelligent_travel_assistant.domain import Provider

    job, command, result, impact, event = weather_case()
    job = modified(job, warnings=("old A", "old B", "old A"), status=PlanningStatus.PARTIAL)
    assert isinstance(job.result, PlanningJobResult)
    result = replace(result, warnings=job.result.warnings)
    proof = ReplanEvidence.bind(job, UUID(int=18002), command, result, (event,))
    if fault.startswith("binding_"):
        key = {
            "job": "job_id",
            "command": "command_fingerprint",
            "candidate": "candidate_fingerprint",
            "version": "job_version",
            "baseline": "baseline_plan_id",
        }[fault.removeprefix("binding_")]
        fields: dict[str, Any] = {
            key: 999
            if key == "job_version"
            else "0" * 64
            if "fingerprint" in key
            else UUID(int=999)
        }
        proof = replace(proof, **fields)
    else:
        targets = {
            "provider": (event.result, "provider", Provider.AMAP),
            "endpoint": (event.result.source_records[0], "source_type", "qweather_current_alerts"),
            "location": (event.request, "location_id", UUID(int=999)),
            "coordinates": (event.request, "coordinates", None),
            "date": (event, "local_date", NOW.date()),
            "future": (event.result, "fetched_at", NOW + timedelta(days=1)),
            "source_fields": (result.sources[-1], "attributions", ("forged",)),
            "weather_forgery": (result.plan.days[0].weather, "condition_day", "forged"),
            "outside_day": (result.plan.days[1], "weather", None),
            "refs": (event, "refs", (result.plan.days[1].activities[0].item_id,)),
            "old_impact": (impact, "transitive_refs", ()),
            "unknown_operation": (event, "operation", "arbitrary"),
            "raw_warning": (result, "warnings", (*result.warnings, "https://example.invalid/raw")),
            "prefix_delete": (result, "warnings", result.warnings[1:]),
            "prefix_reorder": (result, "warnings", ("old B", "old A", "old A")),
            "prefix_change": (result, "warnings", ("changed", "old B", "old A")),
            "capacity": (result, "warnings", ("safe",) * 51),
            "status": (result, "status", PlanningStatus.READY),
            "retryable": (result, "retryable", True),
        }
        target, field, value = targets[fault]
        object.__setattr__(target, field, value)
        proof = ReplanEvidence.bind(job, UUID(int=18002), command, result, (event,))
    with pytest.raises((DomainInvariantError, ValueError, TypeError, AttributeError)):
        PROJECTOR.changes(job, command, impact, result, evaluated_at=NOW, evidence=proof)


@pytest.mark.parametrize("forecast_state", ("fresh", "partial", "unavailable"))
@pytest.mark.parametrize(
    "state", ("fresh", "update", "empty", "partial", "unknown", "stale", "unavailable")
)
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("v2", (False, True))
def test_alert_refresh_and_explicit_empty_preserve_forecast(
    state: str, index: int, v2: bool, forecast_state: str
) -> None:
    from dataclasses import asdict

    from intelligent_travel_assistant.application.ports import (
        CurrentWeatherAlertsRequest,
        WeatherAlertsResult,
    )
    from intelligent_travel_assistant.application.ports import (
        WeatherAlert as PortAlert,
    )
    from intelligent_travel_assistant.contracts import SourceRecord, WeatherAlert

    job, command, candidate, impact, forecast = weather_case(v2, index, forecast_state)
    old = plan_of(job).days[0]
    assert old.weather is not None
    old_alert = WeatherAlert(
        alert_id="old", title="old", description="old", source_ids=old.weather.source_ids
    )
    job = modified(
        job,
        plan=plan_of(job).model_copy(
            update={
                "days": (
                    old.model_copy(
                        update={"weather": old.weather.model_copy(update={"alerts": (old_alert,)})}
                    ),
                    plan_of(job).days[1],
                )
            }
        ),
    )
    _, _, template, _, basis = weather_case(
        v2, index, "fresh" if state in {"empty", "update"} else state
    )
    records = tuple(
        replace(s, source_id=UUID(int=18003), source_type="qweather_current_alerts")
        for s in basis.result.source_records
    )
    alerts = (
        ()
        if state in {"empty", "stale", "unavailable"}
        else (PortAlert("old" if state == "update" else "new", "预警", "orange", NOW, "synthetic"),)
    )
    envelope = replace(
        basis.result,
        data=None
        if state == "unavailable"
        else WeatherAlertsResult(forecast.request.location_id, alerts),
        source_records=records,
    )
    event = replace(
        forecast,
        operation="alerts",
        request=CurrentWeatherAlertsRequest(
            forecast.request.location_id, forecast.request.coordinates
        ),
        result=envelope,
    )
    used = forecast_state != "unavailable" and state not in {"empty", "stale", "unavailable"}
    sources = candidate.sources + tuple(
        SourceRecord.model_validate(
            dict(
                asdict(s),
                freshness="unknown_validity" if state == "unknown" else "fresh",
                warnings=envelope.warnings,
            )
        )
        for s in records
        if used
    )
    day = candidate.plan.days[0]
    public_alerts = tuple(WeatherAlert(**asdict(a), source_ids=(UUID(int=18003),)) for a in alerts)
    assert job.result is not None

    def diagnostics(name: str) -> tuple[Any, ...]:
        history = getattr(job.result, name)
        additions = getattr(candidate, name)[len(history) :]
        alert_additions = getattr(template, name)[len(history) :]
        if name != "errors" and not used and state not in {"stale", "unavailable"}:
            alert_additions = ()
        if name == "errors" and state == "stale":
            alert_additions = tuple(
                e.model_copy(update={"diagnostic_code": "weather_alert_stale"})
                for e in alert_additions
            )
        if name == "uncertainties":
            alert_additions = tuple(
                u.model_copy(update={"source_ids": (UUID(int=18003),)})
                if u.source_ids == (UUID(int=18001),)
                else u
                for u in alert_additions
            )
        additions = (*additions, *alert_additions)
        return (*history, *(v for i, v in enumerate(additions) if v not in additions[:i]))

    errors, warnings, uncertainties = (
        diagnostics(n) for n in ("errors", "warnings", "uncertainties")
    )
    candidate = replace(
        candidate,
        sources=sources,
        plan=candidate.plan.model_copy(
            update={
                "days": (
                    day.model_copy(
                        update={
                            "weather": day.weather.model_copy(update={"alerts": public_alerts})
                            if day.weather is not None
                            else None
                        }
                    ),
                    candidate.plan.days[1],
                )
            }
        ),
        errors=errors,
        warnings=warnings,
        uncertainties=uncertainties,
    )
    case = (job, command, candidate, impact, forecast)
    saved = copy.deepcopy(case)
    assert proved(case, (forecast, event)) == proved(case, (event, forecast, event))
    assert case == saved


def test_same_location_does_not_create_cross_day_or_extra_activity_edges() -> None:
    job = baseline()
    plan = plan_of(job)
    day = plan.days[0]
    location = day.activities[0].location_id
    acts = tuple(a.model_copy(update={"location_id": location}) for a in day.activities)
    nodes = (day.accommodation_location_id, location, location, day.accommodation_location_id)
    routes = tuple(
        r.model_copy(
            update={"origin_location_id": nodes[i], "destination_location_id": nodes[i + 1]}
        )
        for i, r in enumerate(day.routes)
    )
    day = day.model_copy(update={"activities": acts, "routes": routes})
    job = modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    assert facts.context.routes[0].activity_ids == (acts[0].item_id,)
    assert facts.context.routes[1].activity_ids == tuple(a.item_id for a in acts)
    assert facts.context.routes[2].activity_ids == (acts[1].item_id,)


@pytest.mark.parametrize("outside", (False, True))
def test_new_source_and_local_cost_require_exact_derived_origins(outside: bool) -> None:
    job = baseline()
    command = commands(job)[1]
    assert isinstance(command, ReplaceActivity)
    result = candidate_for(job, 1)
    assert isinstance(result.plan, TripPlan)
    plan = result.plan
    sid, cid = UUID(int=9001), UUID(int=9002)
    source = result.sources[3].model_copy(
        update={"source_id": sid, "valid_until": NOW + timedelta(hours=1), "fetched_at": NOW}
    )
    cost = next(c for c in plan.budget_summary.cost_items if c.category.value == "ticket")
    cost = cost.model_copy(
        update={
            "cost_id": cid,
            "source_ids": (sid,),
            "confidence": "estimated",
            "amount": Money(amount=Decimal("1")),
        }
    )
    day = plan.days[0]
    activity = day.activities[0].model_copy(update={"source_ids": (sid,), "cost_items": (cost,)})
    day = day.model_copy(update={"activities": (activity, *day.activities[1:])})
    other = plan.days[1]
    if outside:
        other = other.model_copy(
            update={"activities": (other.activities[0].model_copy(update={"source_ids": (sid,)}),)}
        )
    # Recompute the synthetic aggregate, preserving all unchanged plan-level items.
    temporary = modified(job, plan=plan.model_copy(update={"days": (day, other)}))
    temporary = with_costs(temporary, (*plan.budget_summary.cost_items, cost))
    candidate = replace(result, plan=plan_of(temporary), sources=(*result.sources, source))
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    if outside:
        with pytest.raises(DomainInvariantError):
            PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
    else:
        changes = PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
        origins = dict(changes.added_origins)
        assert origins[sid] == origins[cid] == command.target_activity_id


@pytest.mark.parametrize(
    "fault",
    (
        "source_duplicate",
        "source_dangling",
        "route_missing",
        "fare_conflict",
        "fare_dangling",
        "cost_conflict",
        "request_budget",
        "request_version",
    ),
)
def test_catalog_rejects_unprovable_cost_source_and_request_relations(fault: str) -> None:
    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    plan = plan_of(job)
    day = plan.days[0]
    if fault == "source_duplicate":
        job = modified(job, sources=(*job.result.sources, job.result.sources[0]))
    elif fault == "source_dangling":
        day = day.model_copy(
            update={
                "activities": (
                    day.activities[0].model_copy(update={"source_ids": (UUID(int=99999),)}),
                    *day.activities[1:],
                )
            }
        )
    elif fault == "route_missing":
        day = day.model_copy(update={"routes": day.routes[1:]})
    elif fault in {"fare_conflict", "fare_dangling", "cost_conflict"}:
        cost = plan.budget_summary.cost_items[0].model_copy(
            update={"cost_id": UUID(int=99999)}
            if fault == "fare_dangling"
            else {"description": "conflict"}
        )
        day = (
            day.model_copy(
                update={
                    "activities": (
                        day.activities[0].model_copy(update={"cost_items": (cost,)}),
                        *day.activities[1:],
                    )
                }
            )
            if fault == "cost_conflict"
            else (
                day.model_copy(
                    update={
                        "routes": (day.routes[0].model_copy(update={"fare": cost}), *day.routes[1:])
                    }
                )
            )
        )
    else:
        request = job.request.model_copy(update={"total_budget": Money(amount=Decimal("1"))})
        if fault == "request_version":
            request = TripPlanRequestV2.model_validate(
                dict(request.model_dump(), request_version="2", end_date=plan.end_date)
            )
        job = replace(job, request=request, request_fingerprint=request_fingerprint(request))
    job = modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    with pytest.raises(DomainInvariantError):
        PROJECTOR.analyze(job, commands(job)[0], evaluated_at=NOW)


def test_over_budget_remains_over_budget_with_unknown_and_route_fare_is_owned() -> None:
    job = baseline()
    plan = plan_of(job)
    ticket = next(c for c in plan.budget_summary.cost_items if c.category.value == "ticket")
    meal = next(c for c in plan.budget_summary.cost_items if c.category.value == "meal")
    meal = meal.model_copy(update={"amount": Money(amount=Decimal("9000"))})
    ticket = ticket.model_copy(update={"amount": None, "confidence": "unknown"})
    day = plan.days[0]
    day = day.model_copy(
        update={"routes": (day.routes[0].model_copy(update={"fare": ticket}), *day.routes[1:])}
    )
    job = with_costs(
        modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])})),
        tuple(
            ticket if c.cost_id == ticket.cost_id else meal if c.cost_id == meal.cost_id else c
            for c in plan.budget_summary.cost_items
        ),
    )
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    effect = facts.budget_effect(commands(job)[0])
    assert effect.before.assessment.value == effect.after.assessment.value == "over_budget"
    assert facts.owners[ticket.cost_id] == ("route", day.routes[0].route_id)
    assert effect.after.unknown_count > 0


def test_cached_freshness_and_timezone_representation_do_not_change_fingerprints() -> None:
    from datetime import UTC

    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    original = PROJECTOR.project(job.result, evaluated_at=NOW)
    sources = tuple(
        s.model_copy(
            update={
                "freshness": "stale",
                "fetched_at": s.fetched_at.astimezone(UTC),
                "valid_until": s.valid_until.astimezone(UTC) if s.valid_until else None,
            }
        )
        for s in job.result.sources
    )
    changed = PROJECTOR.project(
        replace(job.result, sources=sources), evaluated_at=NOW.astimezone(UTC)
    )
    assert original.snapshots == changed.snapshots


@pytest.mark.parametrize("index", range(4))
def test_all_commands_remain_zero_io(monkeypatch: pytest.MonkeyPatch, index: int) -> None:
    import subprocess

    job = baseline()
    candidate = candidate_for(job, index)
    command = commands(job)[index]
    evidence_case = diagnostic_case("route", index)

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected I/O")

    with monkeypatch.context() as guard:
        for target, name in (
            (builtins, "open"),
            (Path, "read_text"),
            (Path, "write_text"),
            (os, "getenv"),
            (os, "open"),
            (socket, "create_connection"),
            (socket, "socket"),
            (sqlite3, "connect"),
            (subprocess, "Popen"),
        ):
            guard.setattr(target, name, denied)
        impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
        assert PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
        assert proved(evidence_case[:5], evidence_case[4:])


def test_time_adjustment_can_rebind_scoped_source_without_rewriting_shared_record() -> None:
    job = baseline()
    result = adjusted(job)
    assert isinstance(result.plan, TripPlan)
    source = result.sources[3].model_copy(update={"source_id": UUID(int=9900), "fetched_at": NOW})
    plan = result.plan
    day = plan.days[0]
    target = day.activities[0].model_copy(update={"source_ids": (source.source_id,)})
    day = day.model_copy(update={"activities": (target, *day.activities[1:])})
    candidate = replace(
        result,
        sources=(*result.sources, source),
        plan=plan.model_copy(update={"days": (day, plan.days[1])}),
    )
    command = commands(job)[2]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    changes = PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
    assert dict(changes.added_origins)[source.source_id] == target.item_id
    assert not (set(changes.changed_refs) & {s.source_id for s in result.sources})


@pytest.mark.parametrize("fault", ("stale_route", "unknown_ready", "erased_uncertainty"))
def test_candidate_cannot_upgrade_or_erase_unproven_facts(fault: str) -> None:
    job = baseline()
    if fault == "erased_uncertainty":
        from intelligent_travel_assistant.contracts import Uncertainty

        job = modified(job, uncertainties=(Uncertainty(code="synthetic", message="unknown"),))
    result = adjusted(job)
    if fault == "unknown_ready":
        result = replace(result, status=PlanningStatus.READY)
    elif fault == "erased_uncertainty":
        assert result.uncertainties
        result = replace(result, uncertainties=())
    else:
        assert isinstance(result.plan, TripPlan)
        sid = result.plan.days[0].routes[0].source_ids[0]
        result = replace(
            result,
            sources=tuple(
                s.model_copy(
                    update={
                        "fetched_at": NOW - timedelta(days=2),
                        "valid_until": NOW - timedelta(days=1),
                    }
                )
                if s.source_id == sid
                else s
                for s in result.sources
            ),
        )
    command = commands(job)[2]
    with pytest.raises(DomainInvariantError):
        PROJECTOR.changes(
            job,
            command,
            PROJECTOR.analyze(job, command, evaluated_at=NOW),
            result,
            evaluated_at=NOW,
        )


def test_source_reference_url_is_a_supported_fingerprinted_typed_field() -> None:
    from intelligent_travel_assistant.contracts import SourceRecord

    job = baseline()
    assert isinstance(job.result, PlanningJobResult)
    source = job.result.sources[0]
    changed = SourceRecord.model_validate(
        dict(source.model_dump(), reference_url="https://example.invalid/synthetic-source")
    )
    result = replace(job.result, sources=(changed, *job.result.sources[1:]))
    before = {s.ref_id: s for s in PROJECTOR.project(job.result, evaluated_at=NOW).snapshots}
    after = PROJECTOR.project(result, evaluated_at=NOW).snapshots
    assert {s.ref_id for s in after if s != before[s.ref_id]} == {source.source_id}


def change_weather(result: PlanningJobResult, weather: Any, **fields: Any) -> PlanningJobResult:
    assert result.plan is not None
    day, other = result.plan.days
    plan = result.plan.model_copy(
        update={"days": (day.model_copy(update={"weather": weather}), other)}
    )
    return replace(result, plan=plan, **fields)


def weather_case(v2: bool = False, index: int = 2, state: str = "fresh") -> tuple[Any, ...]:
    """Independent typed fixtures and expectations, shared by weather and alert matrices."""
    from dataclasses import asdict

    from intelligent_travel_assistant.application.ports import (
        DailyWeather,
        WeatherForecastRequest,
        WeatherForecastResult,
    )
    from intelligent_travel_assistant.application.services.replan_facts import EvidenceEvent
    from intelligent_travel_assistant.contracts import (
        ApiError,
        SourceRecord,
        Uncertainty,
        WeatherSnapshot,
    )
    from intelligent_travel_assistant.domain import (
        Coordinates,
        Provider,
        ProviderError,
        ProviderErrorCategory,
        ProviderResult,
        ProviderResultStatus,
    )
    from intelligent_travel_assistant.domain import (
        SourceRecord as DomainSource,
    )

    job = baseline(v2)
    plan = plan_of(job)
    if state == "from_none":
        locations = (
            plan.locations[0].model_copy(update={"coordinates": plan.locations[1].coordinates}),
            *plan.locations[1:],
        )
        assert isinstance(job.result, PlanningJobResult)
        changed = change_weather(job.result, None)
        assert changed.plan is not None
        job = modified(job, plan=changed.plan.model_copy(update={"locations": locations}))
    command = commands(job)[index]
    candidate = candidate_for(job, index)
    assert candidate.plan is not None
    day = candidate.plan.days[0]
    if index == 3:
        activities = tuple(
            a.model_copy(
                update={
                    "start_time": slot.start_time,
                    "end_time": (
                        datetime.combine(NOW.date(), slot.start_time)
                        + (
                            datetime.combine(NOW.date(), a.end_time)
                            - datetime.combine(NOW.date(), a.start_time)
                        )
                    ).time(),
                }
            )
            for a, slot in zip(day.activities, plan.days[0].activities, strict=True)
        )
        day = day.model_copy(update={"activities": activities})
        candidate = replace(
            candidate,
            plan=candidate.plan.model_copy(update={"days": (day, candidate.plan.days[1])}),
        )
    location_id = day.weather.location_id if day.weather else day.accommodation_location_id
    loc = next(
        location for location in plan_of(job).locations if location.location_id == location_id
    )
    assert loc.coordinates is not None
    request = WeatherForecastRequest(
        location_id, Coordinates(**loc.coordinates.model_dump()), day.local_date, day.local_date
    )
    source = DomainSource(
        UUID(int=18001),
        Provider.QWEATHER,
        "qweather_daily_forecast",
        NOW,
        None if state == "unknown" else NOW + timedelta(hours=1),
    )
    if state == "stale":
        source = replace(
            source, fetched_at=NOW - timedelta(hours=2), valid_until=NOW - timedelta(hours=1)
        )
    daily = DailyWeather(day.local_date, "晴", "阴", Decimal(20), Decimal(28))
    data = WeatherForecastResult(location_id, () if state == "missing_date" else (daily,))
    result = ProviderResult(
        ProviderResultStatus.PARTIAL if state == "partial" else ProviderResultStatus.OK,
        Provider.QWEATHER,
        data,
        source.fetched_at,
        source.valid_until,
        ("safe synthetic",),
        ProviderError(ProviderErrorCategory.EMPTY_RESULT) if state == "partial" else None,
        (source,),
    )
    if state == "unavailable":
        result = ProviderResult(
            ProviderResultStatus.UNAVAILABLE,
            Provider.QWEATHER,
            None,
            None,
            None,
            (),
            ProviderError(ProviderErrorCategory.TIMEOUT),
            (),
        )
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    # Expected consumers follow the four commands, independently of production origins.
    refs = (
        (day.routes[0].route_id,)
        if index == 0
        else tuple(
            sorted(
                (a.item_id for a in (day.activities if index == 3 else day.activities[:1])), key=str
            )
        )
    )
    event = EvidenceEvent("forecast", day.local_date, refs, request, result)
    omitted = state in {"unavailable", "stale", "missing_date"}
    source_ids = () if omitted else (source.source_id,)
    weather = (
        None
        if omitted
        else WeatherSnapshot(
            **asdict(daily), location_id=location_id, source_ids=source_ids, alerts=()
        )
    )
    sources = (
        candidate.sources
        if omitted
        else (
            *candidate.sources,
            SourceRecord.model_validate(
                dict(
                    asdict(source),
                    warnings=result.warnings,
                    freshness="unknown_validity" if state == "unknown" else "fresh",
                )
            ),
        )
    )
    error_specs = {
        "unavailable": ("provider_timeout", "外部服务响应超时。", True, None),
        "stale": ("data_stale", "外部数据已超过声明的有效期。", False, "weather_forecast_stale"),
        "partial": ("data_missing", "外部服务没有返回可用数据。", False, None),
    }
    errors: tuple[ApiError, ...] = ()
    if state in error_specs:
        code, message, retryable, diagnostic = error_specs[state]
        errors = (
            ApiError.model_validate(
                dict(
                    code=code,
                    message=message,
                    provider="qweather",
                    retryable=retryable,
                    diagnostic_code=diagnostic,
                )
            ),
        )
    code, message = (
        ("weather_incomplete", "两日天气数据不完整。")
        if omitted
        else (
            ("provider_degraded", "部分外部服务只返回了不完整数据。")
            if state == "partial"
            else ("source_validity_unknown", "部分外部数据未提供固定有效期。")
        )
    )
    uncertainties = (
        (Uncertainty(code=code, message=message, affected_refs=refs, source_ids=source_ids),)
        if omitted or state in {"partial", "unknown"}
        else ()
    )
    warnings = (message,) if omitted or state == "partial" else ()
    candidate = change_weather(
        candidate,
        weather,
        sources=sources,
        errors=(*candidate.errors, *errors),
        warnings=(*candidate.warnings, *warnings),
        uncertainties=(*candidate.uncertainties, *uncertainties),
    )
    return job, command, candidate, impact, event


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize(
    "state", ("fresh", "from_none", "partial", "unknown", "unavailable", "stale", "missing_date")
)
def test_evidenced_weather_changes_are_scoped_and_repeatable(
    v2: bool, index: int, state: str
) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import ReplanEvidence

    job, command, result, impact, event = weather_case(v2, index, state)
    saved = copy.deepcopy((job, command, result, event))
    proof = ReplanEvidence.bind(job, UUID(int=18002), command, result, (event,))
    changes = PROJECTOR.changes(job, command, impact, result, evaluated_at=NOW, evidence=proof)
    assert changes == PROJECTOR.changes(
        job, command, impact, result, evaluated_at=NOW, evidence=proof
    )
    assert (job, command, result, event) == saved
    assert all(
        origin in {*impact.direct_refs, *impact.route_refs} for _, origin in changes.added_origins
    )
    with pytest.raises(DomainInvariantError):
        PROJECTOR.changes(job, command, impact, result, evaluated_at=NOW)


def diagnostic_case(
    kind: str, index: int = 2, v2: bool = False, state: str = "fresh"
) -> tuple[Any, ...]:
    from dataclasses import asdict

    from intelligent_travel_assistant.application.planning.final_validation import (
        FinalValidationIssue,
        FinalValidationIssueCode,
        FinalValidationSeverity,
    )
    from intelligent_travel_assistant.application.ports import (
        CityResolution,
        PoiCandidate,
        PoiSearchRequest,
        PoiSearchResult,
        RouteCalculationRequest,
    )
    from intelligent_travel_assistant.application.services.replan_facts import EvidenceEvent
    from intelligent_travel_assistant.contracts import (
        ApiError,
        ApiErrorCode,
        SourceRecord,
        Uncertainty,
    )
    from intelligent_travel_assistant.domain import (
        Coordinates,
        Provider,
        ProviderError,
        ProviderErrorCategory,
        ProviderResult,
        ProviderResultStatus,
        RouteLeg,
        RouteMode,
    )
    from intelligent_travel_assistant.domain import (
        SourceRecord as DomainSource,
    )

    job, command, candidate, _, weather = weather_case(v2, index)
    plan = plan_of(job)
    locations = tuple(
        loc.model_copy(update={"coordinates": loc.coordinates or plan.locations[1].coordinates})
        for loc in plan.locations
    )
    job = modified(job, plan=plan.model_copy(update={"locations": locations}))
    candidate = replace(candidate, plan=candidate.plan.model_copy(update={"locations": locations}))
    refs = weather.refs
    request: PoiSearchRequest | RouteCalculationRequest | None = None
    primary: ProviderResult[object] | None = None
    city = None
    code, message = None, ""
    source_ids: tuple[UUID, ...] = ()
    errors: tuple[ApiError, ...] = ()
    warnings: tuple[str, ...] = ()
    result: Any
    data: PoiSearchResult | RouteLeg
    day = candidate.plan.days[0]
    if kind == "budget":
        ticket = next(c for c in plan.budget_summary.cost_items if c.category.value == "ticket")
        job = with_costs(
            job,
            tuple(
                c.model_copy(update={"amount": None, "confidence": "unknown"})
                if c.cost_id == ticket.cost_id
                else c
                for c in plan.budget_summary.cost_items
            ),
        )
        candidate = replace(
            candidate,
            plan=candidate.plan.model_copy(update={"budget_summary": plan_of(job).budget_summary}),
        )
        result = summarize_budget(
            DomainMoney(job.request.total_budget.amount),
            PROJECTOR.project(candidate, evaluated_at=NOW)._budget_items,
        )
        refs, code, message = (
            (ticket.cost_id,),
            "budget_indeterminate",
            "存在未知费用，完整预算无法判定。",
        )
    elif kind == "constraint":
        request_model = job.request.model_copy(
            update={
                "preferences": job.request.preferences.model_copy(
                    update={"hard_constraints": ("synthetic constraint",)}
                )
            }
        )
        job = replace(
            job, request=request_model, request_fingerprint=request_fingerprint(request_model)
        )
        result = FinalValidationIssue(
            FinalValidationIssueCode.HARD_CONSTRAINT_UNVERIFIED, FinalValidationSeverity.PARTIAL
        )
        code, message = "hard_constraint_unverified", "硬约束尚不能由确定性规则完全验证。"
    else:
        fetched, until = NOW, None if state == "unknown" else NOW + timedelta(hours=1)
        if state == "stale":
            fetched, until = NOW - timedelta(hours=2), NOW - timedelta(hours=1)
        source = DomainSource(
            UUID(int=20001),
            Provider.AMAP,
            "amap_poi_search" if kind == "location" else "amap_route_walking",
            fetched,
            until,
        )
        source_ids = (source.source_id,)
        envelope_warnings = ("safe synthetic",) if state in {"partial", "unknown"} else ()
        public = SourceRecord.model_validate(
            dict(
                asdict(source),
                freshness="unknown_validity"
                if state == "unknown"
                else "stale"
                if state == "stale"
                else "fresh",
                warnings=envelope_warnings,
            )
        )
        candidate = replace(candidate, sources=(*candidate.sources, public))
        if kind == "location":
            location = next(
                loc for loc in locations if loc.location_id == day.activities[0].location_id
            )
            assert location.coordinates is not None
            location = location.model_copy(update={"source_ids": source_ids})
            assert location.coordinates is not None
            new_locations = tuple(
                location if loc.location_id == location.location_id else loc for loc in locations
            )
            candidate = replace(
                candidate, plan=candidate.plan.model_copy(update={"locations": new_locations})
            )
            refs = (location.location_id,)
            request = PoiSearchRequest(plan.city_adcode, (location.name,), (), 1)
            data = PoiSearchResult(
                (
                    PoiCandidate(
                        location.location_id,
                        location.name,
                        location.category,
                        location.city_adcode,
                        location.address,
                        Coordinates(**location.coordinates.model_dump()),
                    ),
                )
            )
        else:
            route = day.routes[0].model_copy(update={"mode": "walking", "source_ids": source_ids})
            refs = (route.route_id,)
            origin, destination = (
                next(loc for loc in locations if loc.location_id == ref)
                for ref in (route.origin_location_id, route.destination_location_id)
            )
            assert origin.coordinates is not None and destination.coordinates is not None
            request = RouteCalculationRequest(
                origin.location_id,
                destination.location_id,
                Coordinates(**origin.coordinates.model_dump()),
                Coordinates(**destination.coordinates.model_dump()),
                "0571",
                "0571",
                RouteMode.WALKING,
            )
            city = CityResolution("杭州市", plan.city_adcode, "0571", None)
            data = RouteLeg(
                origin.location_id,
                destination.location_id,
                RouteMode.WALKING,
                route.distance_meters,
                route.duration_minutes,
                source_ids,
            )
            candidate = replace(
                candidate,
                plan=candidate.plan.model_copy(
                    update={
                        "days": (
                            day.model_copy(update={"routes": (route, *day.routes[1:])}),
                            candidate.plan.days[1],
                        )
                    }
                ),
            )
            if kind == "fallback":
                primary = ProviderResult(
                    ProviderResultStatus.UNAVAILABLE,
                    Provider.AMAP,
                    None,
                    None,
                    None,
                    (),
                    ProviderError(ProviderErrorCategory.EMPTY_RESULT),
                    (),
                )
                warnings = ("部分路段在首选公交路线不可用时，已按用户允许范围降级为步行。",)
        result = ProviderResult(
            ProviderResultStatus.PARTIAL if state == "partial" else ProviderResultStatus.OK,
            Provider.AMAP,
            data,
            fetched,
            until,
            envelope_warnings,
            ProviderError(ProviderErrorCategory.EMPTY_RESULT) if state == "partial" else None,
            (source,),
        )
        if state == "partial":
            errors = (
                ApiError(
                    code=ApiErrorCode.DATA_MISSING,
                    message="外部服务没有返回可用数据。",
                    provider="amap",
                    retryable=False,
                ),
            )
            code, message = "provider_degraded", "部分外部服务只返回了不完整数据。"
            warnings = (message, *warnings)
        elif state == "unknown":
            code, message = "source_validity_unknown", "部分外部数据未提供固定有效期。"
        elif state == "stale":
            code, message = "source_stale", "部分外部数据已超过有效期。"
            errors = (
                ApiError(
                    code=ApiErrorCode.DATA_STALE,
                    message="外部数据已超过声明的有效期。",
                    provider="amap",
                    diagnostic_code="location_source_stale",
                    retryable=False,
                ),
            )
    event = EvidenceEvent(kind, day.local_date, refs, request, result, primary, city)
    extra = (
        ()
        if code is None
        else (Uncertainty(code=code, message=message, affected_refs=refs, source_ids=source_ids),)
    )
    candidate = replace(
        candidate,
        errors=(*candidate.errors, *errors),
        warnings=(*candidate.warnings, *warnings),
        uncertainties=(*candidate.uncertainties, *extra),
    )
    return (
        job,
        command,
        candidate,
        PROJECTOR.analyze(job, command, evaluated_at=NOW),
        weather,
        event,
    )


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize(
    "kind,state",
    (
        ("route", "fresh"),
        ("route", "partial"),
        ("route", "unknown"),
        ("fallback", "fresh"),
        ("fallback", "partial"),
        ("fallback", "unknown"),
        ("budget", "fresh"),
        ("constraint", "fresh"),
    ),
)
def test_closed_nonweather_diagnostics(kind: str, state: str, index: int, v2: bool) -> None:
    case = diagnostic_case(kind, index, v2, state)
    saved = copy.deepcopy(case)
    if kind == "budget" and index in {2, 3}:
        with pytest.raises(DomainInvariantError):
            proved(case[:5], case[4:])
    else:
        assert proved(case[:5], case[4:]) == proved(
            case[:5], tuple(reversed((*case[4:], case[-1])))
        )
    assert case == saved


def test_budget_evidence_excludes_unrelated_historical_unknown_cost() -> None:
    job, command, candidate, _, weather, event = diagnostic_case("budget", 1)
    job = with_unknown_intercity_cost(job)
    assert candidate.plan is not None
    candidate = replace(
        candidate,
        plan=candidate.plan.model_copy(update={"budget_summary": plan_of(job).budget_summary}),
    )
    budget = summarize_budget(
        DomainMoney(job.request.total_budget.amount),
        PROJECTOR.project(candidate, evaluated_at=NOW)._budget_items,
    )
    event = replace(event, result=budget)
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    case = (job, command, candidate, impact, weather)

    assert proved(case, (weather, event))

    intercity = next(
        cost
        for cost in plan_of(job).budget_summary.cost_items
        if cost.category.value == "intercity_transport"
    )
    forged = replace(event, refs=(*event.refs, intercity.cost_id))
    with pytest.raises(DomainInvariantError):
        proved(case, (weather, forged))


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("state", ("fresh", "partial", "unknown", "stale"))
def test_scoped_location_evidence(state: str, v2: bool) -> None:
    case = diagnostic_case("location", 1, v2, state)
    assert proved(case[:5], case[4:])


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
def test_structurally_invalid_primary_can_use_grounded_fallback(v2: bool, index: int) -> None:
    case = diagnostic_case("fallback", index, v2)
    event = case[-1]
    # An OK envelope with a mismatched endpoint is not a usable primary route.
    primary = replace(
        event.result, data=replace(event.result.data, origin_location_id=UUID(int=24000))
    )
    event = replace(event, primary=primary)
    assert proved(case[:5], (case[4], event))


def test_fallback_rebuilds_primary_lookup_with_current_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[int, RouteLookupStage]] = []

    def observe(lookup: Any) -> bool:
        observed.append((lookup.requirement_index, lookup.stage))
        return original_lookup_allows_fallback(lookup)

    monkeypatch.setattr(replan_facts_module, "_lookup_allows_fallback", observe)
    case = diagnostic_case("fallback")

    assert proved(case[:5], case[4:])
    assert observed == [(1, RouteLookupStage.PRIMARY)]


@pytest.mark.parametrize("seconds", (1.5, float("inf"), float("nan")))
def test_retry_after_is_finite_internal_evidence(seconds: float) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import ReplanEvidence
    from intelligent_travel_assistant.domain import ProviderError, ProviderErrorCategory

    case = weather_case(state="unavailable")
    error = ProviderError(ProviderErrorCategory.RATE_LIMITED, retry_after_seconds=1.5)
    object.__setattr__(error, "retry_after_seconds", seconds)
    event = replace(case[4], result=replace(case[4].result, error=error))
    if seconds != 1.5:
        with pytest.raises((ValueError, TypeError)):
            ReplanEvidence.bind(case[0], UUID(int=18002), case[1], case[2], (event,))
        return
    candidate = replace(
        case[2],
        errors=(
            *case[2].errors[:-1],
            case[2]
            .errors[-1]
            .model_copy(
                update={"code": "provider_rate_limited", "message": "外部服务当前达到调用限制。"}
            ),
        ),
    )
    assert proved((case[0], case[1], candidate, case[3], event))


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize(
    "consumer", ("none", "day", "location", "cost", "history", "destination", "provenance")
)
def test_evidenced_source_drop_and_all_shared_consumers(
    consumer: str, index: int, v2: bool
) -> None:
    from intelligent_travel_assistant.contracts import Uncertainty

    job, command, candidate, _, event = weather_case(v2, index)
    old = plan_of(job).days[0]
    assert old.weather is not None
    source = next(
        s for s in candidate.sources if s.source_id == old.weather.source_ids[0]
    ).model_copy(update={"source_id": UUID(int=23001)})
    sid = source.source_id

    def cite(result: PlanningJobResult, baseline_input: bool) -> PlanningJobResult:
        assert result.plan is not None
        plan = result.plan
        day, other = plan.days
        fields: dict[str, Any] = {}
        if baseline_input:
            assert old.weather is not None
            day = day.model_copy(
                update={"weather": old.weather.model_copy(update={"source_ids": (sid,)})}
            )
        if consumer == "day":
            assert other.weather is not None
            other = other.model_copy(
                update={"weather": other.weather.model_copy(update={"source_ids": (sid,)})}
            )
        elif consumer == "location":
            plan = plan.model_copy(
                update={
                    "locations": (
                        plan.locations[0].model_copy(update={"source_ids": (sid,)}),
                        *plan.locations[1:],
                    )
                }
            )
        elif consumer == "cost":
            costs = plan.budget_summary.cost_items
            plan = plan.model_copy(
                update={
                    "budget_summary": plan.budget_summary.model_copy(
                        update={
                            "cost_items": (
                                costs[0].model_copy(update={"source_ids": (sid,)}),
                                *costs[1:],
                            )
                        }
                    )
                }
            )
        elif consumer == "history":
            fields["uncertainties"] = (
                Uncertainty(code="historical", message="retained", source_ids=(sid,)),
            )
        elif consumer == "destination":
            assert result.resolved_destination is not None
            fields["resolved_destination"] = result.resolved_destination.model_copy(
                update={"source_ids": (sid,)}
            )
        return replace(
            result,
            plan=plan.model_copy(update={"days": (day, other)}),
            sources=(*result.sources, source),
            **fields,
        )

    assert isinstance(job.result, PlanningJobResult)
    job = replace(job, result=cite(job.result, True))
    candidate = cite(candidate, False)
    if consumer == "provenance":
        for result in (job.result, candidate):
            assert result is not None
            object.__setattr__(result.sources[-1], "provider", "system")
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    if consumer == "none":
        retained = copy.deepcopy(candidate)
        object.__setattr__(retained.sources[-1], "warnings", ("forged old source",))
        with pytest.raises((ValueError, TypeError)):
            proved((job, command, retained, impact, event))
        candidate = replace(candidate, sources=candidate.sources[:-1])
    case = (job, command, candidate, impact, event)
    saved = copy.deepcopy(case)
    changes = proved(case)
    assert (sid in changes.removed_refs) is (consumer == "none")
    assert case == saved
    if consumer != "none":
        object.__setattr__(candidate, "sources", candidate.sources[:-1])
        with pytest.raises((ValueError, TypeError)):
            proved(case)


@pytest.mark.parametrize(
    "fault",
    (
        "auth",
        "schema",
        "timeout",
        "rate_limited",
        "server",
        "unknown",
        "budget",
        "deadline",
        "reason",
        "usable_primary",
        "city",
        "request_city",
        "endpoint",
        "route_fact",
        "source_ref",
        "outside_ref",
        "unknown_op",
        "unavailable",
        "stale",
    ),
)
def test_nonweather_required_failures_and_forgery_never_downgrade(fault: str) -> None:
    from intelligent_travel_assistant.domain import (
        ProviderError,
        ProviderErrorCategory,
        ProviderErrorReason,
        RouteMode,
    )

    case = diagnostic_case(
        "route" if fault in {"unavailable", "stale"} else "fallback",
        state="stale" if fault == "stale" else "fresh",
    )
    job, command, candidate, impact, weather, event = case
    if fault in {
        "auth",
        "schema",
        "timeout",
        "rate_limited",
        "server",
        "unknown",
        "budget",
        "deadline",
        "reason",
    }:
        reason = {
            "budget": ProviderErrorReason.RETRY_BUDGET_EXHAUSTED,
            "deadline": ProviderErrorReason.RETRY_DEADLINE_EXHAUSTED,
        }.get(fault)
        error = ProviderError(
            ProviderErrorCategory(fault)
            if fault not in {"budget", "deadline", "reason"}
            else ProviderErrorCategory.TIMEOUT,
            reason,
        )
        if fault == "reason":
            object.__setattr__(error, "reason", "untrusted")
        object.__setattr__(event.primary, "error", error)
    elif fault == "usable_primary":
        object.__setattr__(
            event,
            "primary",
            replace(event.result, data=replace(event.result.data, mode=RouteMode.PUBLIC_TRANSIT)),
        )
    elif fault == "unavailable":
        object.__setattr__(event, "result", diagnostic_case("fallback")[-1].primary)
    elif fault != "stale":
        target, field, value = {
            "city": (event.city, "adcode", "110000"),
            "request_city": (event.request, "origin_citycode", "010"),
            "endpoint": (event.result.source_records[0], "source_type", "amap_poi_search"),
            "route_fact": (event.result.data, "duration_minutes", 999),
            "source_ref": (event.result.data, "source_ids", (UUID(int=99),)),
            "outside_ref": (event, "refs", (candidate.plan.days[1].routes[0].route_id,)),
            "unknown_op": (event, "operation", "cancelled_as_warning"),
        }[fault]
        object.__setattr__(target, field, value)
    with pytest.raises((ValueError, TypeError, AttributeError)):
        proved(case[:5], (weather, event))


@pytest.mark.parametrize("name,capacity", (("errors", 20), ("warnings", 50), ("uncertainties", 50)))
@pytest.mark.parametrize("fault", (None, "delete", "reorder", "change", "capacity", "at_capacity"))
@pytest.mark.parametrize("operation", ("forecast", "city", "model_generate", "model_repair"))
def test_exact_historical_diagnostic_prefix(
    name: str, capacity: int, fault: str | None, operation: str
) -> None:
    from intelligent_travel_assistant.contracts import ApiError, ApiErrorCode, Uncertainty

    job, command, candidate, _, event = weather_case(state="partial")
    events = (event,)
    if operation != "forecast":
        context_case, events = context_quality(*context_evidence_case(operation), "partial")
        job, command, candidate, _, event = context_case
    first, second = {
        "errors": tuple(
            ApiError(code=ApiErrorCode.DATA_MISSING, message=m, retryable=False)
            for m in ("old A", "old B")
        ),
        "warnings": ("old A", "old B"),
        "uncertainties": tuple(
            Uncertainty(
                code="historical",
                message=m,
                affected_refs=(plan_of(job).days[1].activities[0].item_id,),
            )
            for m in ("old A", "old B")
        ),
    }[name]
    prefix = (first,) * capacity if fault == "capacity" else (first, second, first)
    assert isinstance(job.result, PlanningJobResult)
    additions = getattr(candidate, name)[len(getattr(job.result, name)) :]
    if fault == "at_capacity":
        prefix = (first,) * (capacity - len(additions))
    job = modified(job, status=PlanningStatus.PARTIAL, **{name: prefix})
    object.__setattr__(candidate, name, (*prefix, *additions))
    case = (job, command, candidate, PROJECTOR.analyze(job, command, evaluated_at=NOW), event)
    if fault in {None, "at_capacity"}:
        saved = copy.deepcopy(case)
        assert proved(case, events) and case == saved
        return
    replacement = {
        "delete": prefix[1:],
        "reorder": (second, first, first),
        "change": (second, second, first),
        "capacity": prefix,
    }[fault]
    object.__setattr__(candidate, name, (*replacement, *additions))
    with pytest.raises((ValueError, TypeError)):
        proved(case, events)


def test_delete_normalizes_historical_diagnostics_for_the_next_baseline() -> None:
    from intelligent_travel_assistant.contracts import Uncertainty

    job = baseline()
    command = commands(job)[0]
    assert isinstance(command, DeleteActivity)
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    removed_route = impact.route_refs[0]
    plan = plan_of(job)
    retained_activity = plan.days[0].activities[1].item_id
    unrelated_activity = plan.days[1].activities[0].item_id
    assert job.result is not None
    retained_source = job.result.sources[0].source_id
    removed_only = Uncertainty(
        code="source_validity_unknown",
        message="历史路线来源没有固定有效期。",
        affected_refs=(removed_route,),
        source_ids=(retained_source,),
    )
    mixed = Uncertainty(
        code="historical_mixed_scope",
        message="历史诊断同时引用被删除路线和保留活动。",
        affected_refs=(removed_route, retained_activity),
        source_ids=(retained_source,),
    )
    unrelated = Uncertainty(
        code="historical_unrelated",
        message="无关历史诊断必须原样保留。",
        affected_refs=(unrelated_activity,),
    )
    plan_level = Uncertainty(code="historical_plan_level", message="计划级历史诊断。")
    historical = (removed_only, mixed, unrelated, plan_level)
    job = modified(job, status=PlanningStatus.PARTIAL, uncertainties=historical)
    candidate = candidate_for(job, 0)
    saved_job = copy.deepcopy(job)
    saved_candidate = copy.deepcopy(candidate)

    normalized = PROJECTOR.normalize_delete_result(
        job,
        command,
        impact,
        candidate,
        evaluated_at=NOW,
    )

    changes = PROJECTOR.changes(
        job,
        command,
        impact,
        normalized,
        evaluated_at=NOW,
    )

    expected_mixed = mixed.model_copy(update={"affected_refs": (retained_activity,)})
    assert normalized.uncertainties[:3] == (expected_mixed, unrelated, plan_level)
    assert removed_only not in normalized.uncertainties
    assert all(
        set(uncertainty.source_ids) <= {source.source_id for source in normalized.sources}
        for uncertainty in normalized.uncertainties
    )
    assert command.target_activity_id in changes.removed_refs
    assert removed_route in changes.removed_refs
    assert set(changes.removed_refs) <= PROJECTOR.project(job.result, evaluated_at=NOW).allowed(
        command
    )
    assert job == saved_job
    assert candidate == saved_candidate

    next_job = replace(
        job,
        status=normalized.status,
        version=job.version + 1,
        result=normalized,
    )
    PROJECTOR.project(normalized, evaluated_at=NOW)
    PROJECTOR.analyze(next_job, commands(next_job)[2], evaluated_at=NOW)


def test_historical_diagnostic_cannot_make_an_originally_dangling_reference_valid() -> None:
    from intelligent_travel_assistant.contracts import Uncertainty

    job = modified(
        baseline(),
        status=PlanningStatus.PARTIAL,
        uncertainties=(
            Uncertainty(
                code="historical",
                message="原始悬空引用。",
                affected_refs=(UUID(int=99001),),
            ),
        ),
    )

    with pytest.raises(DomainInvariantError):
        PROJECTOR.project(job.result, evaluated_at=NOW)


@pytest.mark.parametrize("fault", ("new", "wrong_target", "other_day"))
def test_historical_missing_reference_exception_cannot_escape_delete_scope(fault: str) -> None:
    from intelligent_travel_assistant.contracts import Uncertainty
    from intelligent_travel_assistant.domain import DeleteActivity

    job = baseline()
    plan = plan_of(job)
    target = plan.days[0].activities[0].item_id
    command: ReplanCommand = commands(job)[0]
    missing_ref = target
    historical = Uncertainty(
        code="historical",
        message="必须保持的历史诊断。",
        affected_refs=(missing_ref,),
    )
    if fault != "new":
        job = modified(job, status=PlanningStatus.PARTIAL, uncertainties=(historical,))
    candidate = candidate_for(job, 0)
    candidate_plan = candidate.plan
    assert candidate_plan is not None
    if fault == "new":
        candidate = replace(candidate, uncertainties=(*candidate.uncertainties, historical))
    elif fault == "wrong_target":
        command = DeleteActivity(plan.days[0].activities[1].item_id)
    else:
        other_day = candidate_plan.days[1]
        missing_ref = other_day.routes[0].route_id
        historical = historical.model_copy(update={"affected_refs": (missing_ref,)})
        job = modified(job, uncertainties=(historical,))
        candidate = candidate_for(job, 0)
        candidate_plan = candidate.plan
        assert candidate_plan is not None
        other_day = candidate_plan.days[1]
        changed_route = other_day.routes[0].model_copy(update={"route_id": UUID(int=99002)})
        changed_day = other_day.model_copy(
            update={"routes": (changed_route, *other_day.routes[1:])}
        )
        candidate = replace(
            candidate,
            plan=candidate_plan.model_copy(update={"days": (candidate_plan.days[0], changed_day)}),
        )

    with pytest.raises(DomainInvariantError):
        PROJECTOR.changes(
            job,
            command,
            PROJECTOR.analyze(job, command, evaluated_at=NOW),
            candidate,
            evaluated_at=NOW,
        )


@pytest.mark.parametrize(
    "fault",
    (
        "orphan",
        "source_cycle",
        "global_source",
        "retained_source",
        "over_budget",
        "schedule",
        "place_id",
        "place_provider",
    ),
)
def test_new_evidence_cannot_bypass_catalog_or_hard_conflicts(fault: str) -> None:
    from intelligent_travel_assistant.contracts import Uncertainty

    case = diagnostic_case("location", 1) if fault.startswith("place_") else weather_case(index=2)
    job, command, candidate, impact, event = case[:5]
    candidate = copy.deepcopy(candidate)
    events = case[4:]
    if fault == "orphan":
        candidate = replace(
            candidate,
            sources=(
                *candidate.sources,
                candidate.sources[-1].model_copy(update={"source_id": UUID(int=88)}),
            ),
        )
    elif fault in {"source_cycle", "global_source"}:
        target = candidate.sources[-1].source_id
        uncertainty = Uncertainty(
            code="unproven",
            message="unproven",
            affected_refs=(target,),
            source_ids=(candidate.sources[-1].source_id,),
        )
        if fault == "global_source":
            day = candidate.plan.days[1]
            object.__setattr__(day.activities[0], "source_ids", (target,))
        else:
            object.__setattr__(candidate, "uncertainties", (uncertainty,))
    elif fault == "retained_source":
        object.__setattr__(candidate.sources[0], "warnings", ("forged retention",))
    elif fault == "over_budget":
        plan = plan_of(job)
        costs = plan.budget_summary.cost_items
        cost = costs[0].model_copy(update={"amount": Money(amount=Decimal("99999"))})
        job = with_costs(job, (cost, *costs[1:]))
        candidate = replace(
            candidate,
            plan=candidate.plan.model_copy(update={"budget_summary": plan_of(job).budget_summary}),
        )
    elif fault == "schedule":
        object.__setattr__(candidate.plan.days[0].routes[0], "duration_minutes", 500)
    else:
        location = next(
            loc for loc in candidate.plan.locations if loc.location_id == events[-1].refs[0]
        )
        object.__setattr__(
            location,
            "provider_place_id" if fault == "place_id" else "provider",
            "unproved" if fault == "place_id" else "user",
        )
    with pytest.raises((ValueError, TypeError, AttributeError)):
        impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
        proved((job, command, candidate, impact, event), events)


@pytest.mark.parametrize("fault", (None, "candidate_alias", "event_alias", "expired", "future"))
def test_bound_evidence_deepcopy_and_completion_time(fault: str | None) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import (
        EvidencedReplanResult,
        ReplanEvidence,
    )

    job, command, candidate, impact, event = weather_case()
    proof = ReplanEvidence.bind(job, UUID(int=18002), command, candidate, (event,))
    wrapped = EvidencedReplanResult(candidate, proof)
    saved = copy.deepcopy(wrapped)
    object.__setattr__(candidate.plan.days[0].weather, "condition_day", "mutated input")
    object.__setattr__(event.request, "location_id", UUID(int=17))
    assert wrapped == saved and proof.events == saved.evidence.events
    at = NOW
    if fault == "candidate_alias":
        assert wrapped.result.plan is not None
        object.__setattr__(wrapped.result.plan.days[0].weather, "condition_day", "forged wrapper")
    elif fault == "event_alias":
        object.__setattr__(wrapped.evidence.events[0], "refs", ())
    elif fault == "expired":
        at += timedelta(hours=2)
    elif fault == "future":
        at -= timedelta(minutes=1)
    if fault is None:
        assert PROJECTOR.changes(
            job, command, impact, wrapped.result, evaluated_at=at, evidence=wrapped.evidence
        )
    else:
        with pytest.raises((ValueError, TypeError)):
            PROJECTOR.changes(
                job, command, impact, wrapped.result, evaluated_at=at, evidence=wrapped.evidence
            )


@pytest.mark.parametrize("operation", ("city", "model_generate", "model_repair"))
@pytest.mark.parametrize(
    "fault",
    (
        None,
        "job_id",
        "baseline_plan_id",
        "job_version",
        "command_fingerprint",
        "candidate_fingerprint",
        "events_fingerprint",
        "request",
        "context",
        "old_field",
    ),
)
def test_context_evidence_binding_and_isolation(
    operation: str, fault: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from intelligent_travel_assistant.application.services.replan_facts import (
        EvidencedReplanResult,
        ReplanEvidence,
    )

    case, events = context_evidence_case(operation)
    job, command, candidate, impact, event = case
    proof = ReplanEvidence.bind(job, UUID(int=18002), command, candidate, events)
    wrapped = EvidencedReplanResult(candidate, proof)
    if fault in {"request", "context"}:
        target = wrapped.evidence.events[-1]
        context = target.model_context or target.request
        object.__setattr__(
            context,
            "city_text"
            if operation == "city"
            else "start_date"
            if operation == "model_generate" or fault == "context"
            else "request_version",
            "forged",
        )
    elif fault == "old_field":
        proof = ReplanEvidence.bind(
            job,
            UUID(int=18002),
            command,
            candidate,
            (
                replace(events[0], model_context=events[-1].model_context or events[-1].request),
                *events[1:],
            ),
        )
        wrapped = EvidencedReplanResult(candidate, proof)
    elif fault is not None:
        value: Any = (
            999 if fault == "job_version" else "0" * 64 if "fingerprint" in fault else UUID(int=99)
        )
        wrapped = EvidencedReplanResult(candidate, replace(proof, **{fault: value}))
    saved = copy.deepcopy(wrapped)
    object.__setattr__(event.result, "warnings", ("caller mutated",))
    assert wrapped == saved

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("external I/O")

    with monkeypatch.context() as guard:
        for module, name in (
            (builtins, "open"),
            (socket, "socket"),
            (sqlite3, "connect"),
            (os, "putenv"),
        ):
            guard.setattr(module, name, forbidden)
        if fault is None:
            assert PROJECTOR.changes(
                job, command, impact, wrapped.result, evaluated_at=NOW, evidence=wrapped.evidence
            )
        else:
            with pytest.raises((ValueError, TypeError, AttributeError)):
                PROJECTOR.changes(
                    job,
                    command,
                    impact,
                    wrapped.result,
                    evaluated_at=NOW,
                    evidence=wrapped.evidence,
                )


def context_quality(case: tuple[Any, ...], events: tuple[Any, ...], state: str) -> tuple[Any, ...]:
    from dataclasses import asdict

    from intelligent_travel_assistant.contracts import (
        ApiError,
        ApiErrorCode,
        SourceRecord,
        Uncertainty,
    )
    from intelligent_travel_assistant.domain import (
        ProviderError,
        ProviderErrorCategory,
        ProviderResultStatus,
    )

    event = events[-1]
    result = event.result
    partial, unknown, stale = "partial" in state, "unknown" in state, state == "stale"
    fetched = NOW - timedelta(hours=2) if stale else NOW
    until = None if unknown else NOW - timedelta(hours=1) if stale else NOW + timedelta(hours=1)
    source = replace(result.source_records[0], fetched_at=fetched, valid_until=until)
    result = replace(
        result,
        fetched_at=fetched,
        valid_until=until,
        source_records=(source,),
        warnings=("synthetic quality warning",) if partial or unknown else (),
        status=ProviderResultStatus.PARTIAL if partial else ProviderResultStatus.OK,
        error=ProviderError(ProviderErrorCategory.EMPTY_RESULT) if partial else None,
    )
    event = replace(event, result=result)
    candidate = case[2]
    public = SourceRecord.model_validate(
        dict(
            asdict(source),
            warnings=result.warnings,
            freshness="stale" if stale else "unknown_validity" if unknown else "fresh",
        )
    )
    candidate = replace(
        candidate,
        sources=tuple(public if s.source_id == source.source_id else s for s in candidate.sources),
    )
    additions, errors, warnings = [], [], []
    if partial:
        errors.append(
            ApiError(
                code=ApiErrorCode.DATA_MISSING,
                message="外部服务没有返回可用数据。",
                provider=source.provider.value,
                retryable=False,
            )
        )
        additions.append(("provider_degraded", "部分外部服务只返回了不完整数据。"))
        warnings.append(additions[-1][1])
    if unknown:
        additions.append(("source_validity_unknown", "部分外部数据未提供固定有效期。"))
    if stale:
        errors.append(
            ApiError(
                code=ApiErrorCode.DATA_STALE,
                message="外部数据已超过声明的有效期。",
                provider="amap",
                diagnostic_code="location_source_stale",
                retryable=False,
            )
        )
        additions.append(("source_stale", "部分外部数据已超过有效期。"))
    candidate = replace(
        candidate,
        status=PlanningStatus.PARTIAL,
        errors=(*candidate.errors, *errors),
        warnings=(*candidate.warnings, *warnings),
        uncertainties=(
            *candidate.uncertainties,
            *(
                Uncertainty(
                    code=c, message=m, source_ids=(source.source_id,), affected_refs=event.refs
                )
                for c, m in sorted(additions)
            ),
        ),
    )
    return (*case[:2], candidate, case[3], event), (*events[:-1], event)


@pytest.mark.parametrize("operation", ("city", "model_generate", "model_repair"))
@pytest.mark.parametrize("state", ("partial", "unknown", "partial_unknown", "stale"))
@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
def test_context_evidence_quality(operation: str, state: str, v2: bool, index: int) -> None:
    case, events = context_quality(*context_evidence_case(operation, index, v2), state)
    original = copy.deepcopy((case, events))
    if state == "stale" and operation != "city":
        with pytest.raises(ValueError):
            proved(case, events)
    else:
        assert proved(case, events) == proved(case, (*events, events[-1]))
        assert case[2].status is PlanningStatus.PARTIAL
    assert (case, events) == original


@pytest.mark.parametrize("operation", ("city", "model_generate", "model_repair"))
@pytest.mark.parametrize(
    "fault",
    (
        "missing_event",
        "no_evidence",
        "wrong_day",
        "missing_ref",
        "outside_ref",
        "duplicate_ref",
        "provider",
        "source_type",
        "old_id",
        "collision",
        "fetched",
        "unavailable",
        "no_sources",
        "extra_request_field",
        "factual_location",
        "factual_route",
        "factual_cost",
        "history_drop",
        "destination",
        "anchor",
        "expired",
        "future",
        "global_source_drop",
    ),
)
def test_context_evidence_rejects_unproved(operation: str, fault: str) -> None:
    from intelligent_travel_assistant.domain import Provider, ProviderResultStatus

    case, events = context_evidence_case(operation)
    job, command, candidate, impact, event = case
    source = event.result.source_records[0]
    if fault == "missing_event":
        events = events[:-1]
    elif fault == "no_evidence":
        with pytest.raises(ValueError):
            PROJECTOR.changes(job, command, impact, candidate, evaluated_at=NOW)
        return
    elif fault in {
        "wrong_day",
        "missing_ref",
        "outside_ref",
        "duplicate_ref",
        "extra_request_field",
    }:
        values = {
            "wrong_day": ("local_date", plan_of(job).end_date),
            "missing_ref": ("refs", event.refs[1:]),
            "outside_ref": ("refs", (plan_of(job).days[1].activities[0].item_id,)),
            "duplicate_ref": ("refs", (*event.refs, event.refs[0])),
            "extra_request_field": ("primary", event.result),
        }
        field, value = values[fault]
        event = replace(event, **{field: value})
    elif fault in {
        "provider",
        "source_type",
        "old_id",
        "collision",
        "fetched",
        "unavailable",
        "no_sources",
    }:
        if fault == "provider":
            object.__setattr__(event.result, "provider", Provider.QWEATHER)
        elif fault == "unavailable":
            object.__setattr__(event.result, "status", ProviderResultStatus.UNAVAILABLE)
            object.__setattr__(event.result, "data", None)
        elif fault == "no_sources":
            object.__setattr__(event.result, "source_records", ())
        else:
            field, value = {
                "source_type": ("source_type", "amap_poi_search"),
                "old_id": ("source_id", candidate.sources[0].source_id),
                "collision": ("source_id", events[1].result.source_records[0].source_id),
                "fetched": ("fetched_at", NOW - timedelta(seconds=1)),
            }[fault]
            object.__setattr__(source, field, value)
    elif fault.startswith("factual_"):
        target = {
            "factual_location": candidate.plan.locations[1],
            "factual_route": candidate.plan.days[0].routes[0],
            "factual_cost": candidate.plan.budget_summary.cost_items[0],
        }[fault]
        object.__setattr__(target, "source_ids", (*target.source_ids, source.source_id))
    elif fault == "history_drop":
        job = modified(job, warnings=("historical warning",), status=PlanningStatus.PARTIAL)
    elif fault == "destination":
        candidate = replace(
            candidate,
            resolved_destination=candidate.resolved_destination.model_copy(
                update={"source_ids": (source.source_id,)}
            ),
        )
    elif fault == "anchor":
        anchor = next(
            loc
            for loc in candidate.plan.locations
            if loc.location_id == candidate.plan.days[0].accommodation_location_id
        )
        object.__setattr__(anchor, "source_ids", (source.source_id,))
    elif fault == "global_source_drop":
        old = next(s for s in job.result.sources if s.provider.value == "deepseek")
        candidate = replace(
            candidate, sources=tuple(s for s in candidate.sources if s.source_id != old.source_id)
        )
    if fault != "missing_event":
        events = (*events[:-1], event)
    if fault in {"expired", "future"}:
        from intelligent_travel_assistant.application.services.replan_facts import ReplanEvidence

        proof = ReplanEvidence.bind(job, UUID(int=18002), command, candidate, events)
        with pytest.raises(ValueError):
            PROJECTOR.changes(
                job,
                command,
                impact,
                candidate,
                evidence=proof,
                evaluated_at=NOW + timedelta(hours=2)
                if fault == "expired"
                else NOW - timedelta(seconds=1),
            )
    else:
        with pytest.raises((ValueError, TypeError, AttributeError)):
            proved((job, command, candidate, impact, event), events)


@pytest.mark.parametrize("operation", ("model_generate", "model_repair"))
@pytest.mark.parametrize(
    "fault",
    (
        "city",
        "date",
        "version",
        "window",
        "budget",
        "travelers",
        "tools",
        "location",
        "duplicate",
        "source",
        "observation",
        "raw_output",
        "selection",
        "selection_source",
        "unadopted",
        "model_title",
        "repair_code",
        "repair_context",
        "repair_refs",
    ),
)
def test_context_evidence_model_binding(operation: str, fault: str) -> None:
    from intelligent_travel_assistant.application.ports import (
        CandidateValidationCode,
        ModelTextOutput,
    )

    case, events = context_evidence_case(operation, 1)
    event = events[-1]
    context = event.model_context or event.request
    changes = {
        "city": ("city_adcode", "110000"),
        "date": ("start_date", context.start_date + timedelta(days=1)),
        "version": ("request_version", "3"),
        "window": ("day_windows", ()),
        "budget": ("budget", DomainMoney(Decimal("1"))),
        "travelers": ("travelers", 99),
        "tools": ("allowed_tools", ()),
        "location": ("locations", (replace(context.locations[0], name="forged"),)),
        "duplicate": ("locations", (*context.locations, context.locations[0])),
        "source": ("activity_source_ids", (events[-1].result.source_records[0].source_id,)),
        "observation": ("observations", ()),
    }
    if fault in changes:
        field, value = changes[fault]
        if fault == "observation":
            from intelligent_travel_assistant.application.ports import PlanningObservation

            value = (PlanningObservation("city", "invented", (UUID(int=98),)),)
        object.__setattr__(context, field, value)
    elif fault == "raw_output":
        object.__setattr__(event.result, "data", ModelTextOutput("not typed evidence"))
    elif fault in {"selection", "selection_source", "unadopted"}:
        selection = event.result.data.days[0].selections[0]
        field, value = {
            "selection": ("location_id", UUID(int=19)),
            "selection_source": ("source_ids", (UUID(int=19),)),
            "unadopted": ("location_id", event.result.data.days[1].selections[0].location_id),
        }[fault]
        object.__setattr__(selection, field, value)
    elif fault == "model_title":
        object.__setattr__(case[2].plan.days[0].activities[0], "title", "untrusted model title")
    elif operation == "model_repair":
        field, value = {
            "repair_code": ("validation_code", CandidateValidationCode.UNSAFE_TEXT),
            "repair_context": ("expected_dates", (context.end_date,)),
            "repair_refs": ("affected_refs", event.refs),
        }[fault]
        object.__setattr__(event.request, field, value)
    else:
        event = replace(event, model_context=context)
        events = (*events[:-1], event)
    with pytest.raises((ValueError, TypeError, AttributeError)):
        proved(case, events)


@pytest.mark.parametrize(
    "fault", ("query", "adcode", "citycode", "no_downstream", "bare_route", "views")
)
def test_context_evidence_city_dependency(fault: str) -> None:
    case, events = context_evidence_case("city")
    event = events[-1]
    if fault == "query":
        object.__setattr__(event.request, "city_text", "other city")
    elif fault in {"adcode", "citycode"}:
        object.__setattr__(event.result.data, fault, "110000" if fault == "adcode" else "010")
    elif fault == "no_downstream":
        events = (events[0], event)
    elif fault == "bare_route":
        events = (events[0], replace(events[1], city=None), event)
    else:
        events = (*events, replace(event, local_date=plan_of(case[0]).end_date))
    with pytest.raises((ValueError, TypeError, AttributeError)):
        proved(case, events)


@pytest.mark.parametrize("operation", ("city", "model_generate", "model_repair"))
@pytest.mark.parametrize(
    "fault", ("ready", "errors", "warnings", "uncertainties", "text", "reorder")
)
def test_context_evidence_diagnostics_exact(operation: str, fault: str) -> None:
    case, events = context_quality(*context_evidence_case(operation), "partial_unknown")
    candidate = case[2]
    if fault == "ready":
        object.__setattr__(candidate, "status", PlanningStatus.READY)
    elif fault in {"errors", "warnings", "uncertainties"}:
        candidate = replace(candidate, **{fault: ()})
    elif fault == "text":
        candidate = replace(candidate, warnings=(*candidate.warnings, "arbitrary external text"))
    else:
        candidate = replace(candidate, uncertainties=tuple(reversed(candidate.uncertainties)))
    with pytest.raises(ValueError):
        proved((*case[:2], candidate, *case[3:]), events)


def context_evidence_case(
    operation: str, index: int = 2, v2: bool = False
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    from dataclasses import asdict

    from intelligent_travel_assistant.application.planning.candidate_resolution import _repair_brief
    from intelligent_travel_assistant.application.ports import (
        ActivityDurationClass,
        ActivitySelection,
        ActivitySelectionKind,
        CandidateValidationCode,
        CityResolutionRequest,
        PlanningContext,
        PlanningDayWindow,
        PlanningLocation,
        PlanningToolName,
        PlanProposal,
        ProposalDay,
    )
    from intelligent_travel_assistant.application.services.replan_facts import EvidenceEvent
    from intelligent_travel_assistant.contracts import SourceRecord
    from intelligent_travel_assistant.domain import Provider, ProviderResult, ProviderResultStatus
    from intelligent_travel_assistant.domain import SourceRecord as DomainSource

    job, command, candidate, impact, weather, route = diagnostic_case("route", index, v2)
    plan = candidate.plan
    if index == 1 and operation != "city":
        day = plan.days[0]
        activity = day.activities[0]
        normalized = next(
            loc.name for loc in plan.locations if loc.location_id == activity.location_id
        )
        day = day.model_copy(
            update={
                "activities": (
                    activity.model_copy(update={"title": normalized}),
                    *day.activities[1:],
                )
            }
        )
        plan = plan.model_copy(update={"days": (day, plan.days[1])})
        candidate = replace(candidate, plan=plan)
    anchor = next(
        loc for loc in plan.locations if loc.location_id == plan.days[0].accommodation_location_id
    )
    locations = tuple(loc for loc in plan.locations if loc.location_id != anchor.location_id)
    context = PlanningContext(
        route.city.city_name,
        plan.city_adcode,
        plan.start_date,
        plan.end_date,
        job.request.travelers,
        DomainMoney(job.request.total_budget.amount),
        job.request.preferences.interests,
        job.request.preferences.hard_constraints,
        tuple(PlanningToolName),
        tuple(
            PlanningLocation(loc.location_id, loc.name, loc.category, loc.city_adcode)
            for loc in locations
        ),
        (),
        free_text=job.request.preferences.free_text,
        route_mode=route.request.mode,
        day_windows=tuple(
            PlanningDayWindow(w.day_offset, w.start_time, w.end_time)
            for w in job.request.day_windows
        ),
        accommodation=PlanningLocation(
            anchor.location_id, "accommodation anchor", "accommodation_anchor", anchor.city_adcode
        ),
        activity_source_ids=tuple(
            sorted({sid for loc in locations for sid in loc.source_ids}, key=str)
        ),
        request_version="2" if v2 else None,
        expected_dates=tuple(day.local_date for day in plan.days) if v2 else (),
    )
    proposal = PlanProposal(
        "synthetic selection",
        tuple(
            ProposalDay(
                day.local_date,
                tuple(
                    ActivitySelection(
                        a.location_id,
                        day.local_date,
                        "untrusted model title",
                        rank,
                        ActivitySelectionKind.REQUIRED,
                        ActivityDurationClass.SHORT,
                        next(
                            loc.source_ids for loc in locations if loc.location_id == a.location_id
                        ),
                    )
                    for rank, a in enumerate(day.activities, 1)
                ),
            )
            for day in plan.days
        ),
        "untrusted explanation",
        (),
    )
    adopted = tuple(sorted(set((*weather.refs, *route.refs)), key=str))
    events = [weather, route]
    for kind in ("city",) if operation == "city" else ("city", operation):
        model = kind != "city"
        source = DomainSource(
            UUID(int=32001 if model else 31001),
            Provider.DEEPSEEK if model else Provider.AMAP,
            ("model_plan_proposal_repair" if kind == "model_repair" else "model_plan_proposal")
            if model
            else "amap_geocode",
            NOW,
            NOW + timedelta(hours=1),
        )
        envelope = ProviderResult(
            ProviderResultStatus.OK,
            source.provider,
            proposal if model else route.city,
            NOW,
            source.valid_until,
            (),
            None,
            (source,),
        )
        candidate = replace(
            candidate,
            sources=(
                *candidate.sources,
                SourceRecord.model_validate(
                    dict(asdict(source), freshness="fresh", warnings=()),
                ),
            ),
        )
        request = (
            _repair_brief(context, CandidateValidationCode.JSON_INVALID)
            if kind == "model_repair"
            else context
            if model
            else CityResolutionRequest(job.request.city)
        )
        events.append(
            EvidenceEvent(
                kind,
                plan.days[0].local_date,
                adopted if operation != "city" else route.refs,
                request,
                envelope,
                model_context=context if kind == "model_repair" else None,
            )
        )
    return (job, command, candidate, impact, events[-1]), tuple(events)


@pytest.mark.parametrize("operation", ("city", "model_generate", "model_repair"))
@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("v2", (False, True))
def test_context_evidence_fresh_positive(operation: str, index: int, v2: bool) -> None:
    case, events = context_evidence_case(operation, index, v2)
    saved = copy.deepcopy((case, events))
    changes = proved(case, events)
    assert changes == proved(case, events)
    assert (case, events) == saved
    new_sources = {s.source_id for event in events[2:] for s in event.result.source_records}
    assert new_sources <= set(changes.added_refs)
    assert all(
        dict(changes.added_origins)[sid] in {*case[3].direct_refs, *case[3].route_refs}
        for sid in new_sources
    )


def scoped_model_context_case() -> tuple[Any, ...]:
    from dataclasses import asdict

    from intelligent_travel_assistant.application.ports import (
        PlanningContext,
        PlanningLocation,
        PoiCandidate,
        PoiSearchRequest,
        PoiSearchResult,
        ReplanSelectionScope,
    )
    from intelligent_travel_assistant.application.services.replan_facts import EvidenceEvent
    from intelligent_travel_assistant.contracts import SourceRecord
    from intelligent_travel_assistant.domain import (
        Coordinates,
        Provider,
        ProviderResult,
        ProviderResultStatus,
    )
    from intelligent_travel_assistant.domain import SourceRecord as DomainSource

    case, events = context_evidence_case("model_generate", 1, True)
    job, _, candidate, _, model_event = case
    assert candidate.plan is not None
    context = model_event.request
    assert isinstance(context, PlanningContext)
    before = PROJECTOR.project(job.result, evaluated_at=NOW)
    baseline = tuple(
        tuple(activity.location_id for activity in day.activities) for day in before.plan.days
    )
    baseline_ids = tuple(dict.fromkeys(location_id for day in baseline for location_id in day))
    selected_id, unselected_id, source_id = UUID(int=51001), UUID(int=51002), UUID(int=51003)
    source = DomainSource(
        source_id,
        Provider.AMAP,
        "amap_poi_search",
        NOW,
        NOW + timedelta(hours=1),
    )
    candidate = replace(
        candidate,
        sources=(
            *candidate.sources,
            SourceRecord.model_validate(dict(asdict(source), freshness="fresh", warnings=())),
        ),
    )
    original = before.locations[baseline[0][0]]
    assert original.coordinates is not None
    selected = original.model_copy(
        update={
            "location_id": selected_id,
            "name": "typed selected candidate",
            "source_ids": (source_id,),
        }
    )
    unselected = selected.model_copy(
        update={"location_id": unselected_id, "name": "typed unselected candidate"}
    )
    first_day = candidate.plan.days[0]
    first_activity = first_day.activities[0].model_copy(
        update={"location_id": selected_id, "title": selected.name}
    )
    first_day = first_day.model_copy(
        update={
            "activities": (first_activity, *first_day.activities[1:]),
            "routes": tuple(
                route.model_copy(
                    update={
                        "origin_location_id": selected_id
                        if route.origin_location_id == original.location_id
                        else route.origin_location_id,
                        "destination_location_id": selected_id
                        if route.destination_location_id == original.location_id
                        else route.destination_location_id,
                    }
                )
                for route in first_day.routes
            ),
        }
    )
    plan = candidate.plan.model_copy(
        update={
            "locations": (*candidate.plan.locations, selected),
            "days": (first_day, candidate.plan.days[1]),
        }
    )
    candidate = replace(candidate, plan=plan)

    def poi(location: Any) -> PoiCandidate:
        assert location.coordinates is not None
        return PoiCandidate(
            location.location_id,
            location.name,
            location.category,
            location.city_adcode,
            location.address,
            Coordinates(**location.coordinates.model_dump()),
        )

    poi_result = ProviderResult(
        ProviderResultStatus.OK,
        Provider.AMAP,
        PoiSearchResult((poi(selected), poi(unselected))),
        NOW,
        NOW + timedelta(hours=1),
        (),
        None,
        (source,),
    )
    location_event = EvidenceEvent(
        "location",
        before.plan.days[0].local_date,
        (selected_id,),
        PoiSearchRequest(before.plan.city_adcode, ("museum",), ("museum",), 5),
        poi_result,
    )
    baseline_locations = tuple(before.locations[ref] for ref in baseline_ids)
    command = commands(job)[1]
    assert isinstance(command, ReplaceActivity)
    scope = ReplanSelectionScope(
        command.target_activity_id,
        before.plan.days[0].local_date,
        0,
        baseline,
        (selected_id, unselected_id),
    )
    context = replace(
        context,
        locations=tuple(
            PlanningLocation(loc.location_id, loc.name, loc.category, loc.city_adcode)
            for loc in (*baseline_locations, selected, unselected)
        ),
        activity_source_ids=tuple(
            sorted(
                {
                    source_id,
                    *(sid for loc in baseline_locations for sid in loc.source_ids),
                },
                key=str,
            )
        ),
        replan_selection_scope=scope,
    )
    return job, candidate, context, (*events, location_event), unselected


def test_scoped_model_context_proves_candidates_without_publishing_unselected() -> None:
    job, candidate, context, events, unselected = scoped_model_context_case()
    before = PROJECTOR.project(job.result, evaluated_at=NOW)
    after = PROJECTOR.project(candidate, evaluated_at=NOW)
    PROJECTOR._model_context(job, before, after, context, list(events))
    assert unselected.location_id not in after.locations


def test_scoped_model_context_rejects_published_unselected_candidate() -> None:
    job, candidate, context, events, unselected = scoped_model_context_case()
    assert candidate.plan is not None
    candidate = replace(
        candidate,
        plan=candidate.plan.model_copy(
            update={"locations": (*candidate.plan.locations, unselected)}
        ),
    )
    with pytest.raises(DomainInvariantError):
        PROJECTOR._model_context(
            job,
            PROJECTOR.project(job.result, evaluated_at=NOW),
            PROJECTOR.project(candidate, evaluated_at=NOW),
            context,
            list(events),
        )
