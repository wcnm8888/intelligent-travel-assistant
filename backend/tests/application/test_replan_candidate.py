"""R2 command candidates, using only synthetic typed baseline construction."""

from __future__ import annotations

import builtins
import copy
import io
import os
import socket
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from tests.application.test_replan_facts import (
    NOW,
    PROJECTOR,
    baseline,
    commands,
    modified,
    plan_of,
)

from intelligent_travel_assistant.application.repositories import PlanningJob
from intelligent_travel_assistant.application.services.replan_candidate import (
    ActivityReplacement,
    ReplanCandidate,
    build_replan_candidate,
)
from intelligent_travel_assistant.contracts import (
    CostCategory,
    CostConfidence,
    CostItem,
    Money,
    TripPlanV2,
)
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DeleteActivity,
    DomainInvariantError,
    ReorderActivities,
    ReplanCommand,
)


def replacement_for(job: PlanningJob) -> ActivityReplacement:
    plan = plan_of(job)
    assert job.result is not None
    source = job.result.sources[0].model_copy(update={"source_id": UUID(int=6001)})
    location = plan.locations[1].model_copy(
        update={
            "location_id": UUID(int=6000),
            "category": "museum",
            "source_ids": (source.source_id,),
        }
    )
    cost = CostItem(
        cost_id=UUID(int=6003),
        category=CostCategory.TICKET,
        confidence=CostConfidence.UNKNOWN,
        amount=None,
        description="Unknown admission",
        source_ids=(),
    )
    activity = (
        plan.days[0]
        .activities[0]
        .model_copy(
            update={
                "item_id": UUID(int=6002),
                "location_id": location.location_id,
                "title": "Replacement museum",
                "source_ids": (source.source_id,),
                "cost_items": (cost,),
            }
        )
    )
    return ActivityReplacement(plan.start_date, activity, location, (source,))


def build(job: PlanningJob, index: int = 0, **kwargs: Any) -> ReplanCandidate:
    command = commands(job)[index]
    return build_replan_candidate(
        job,
        command,
        PROJECTOR.analyze(job, command, evaluated_at=NOW),
        evaluated_at=NOW,
        **kwargs,
    )


@pytest.mark.parametrize("v2", (False, True))
@pytest.mark.parametrize("index", range(4))
def test_four_commands_preserve_baseline_and_unaffected_facts(v2: bool, index: int) -> None:
    job = baseline(v2)
    original = copy.deepcopy(job)
    proposal = replacement_for(job) if index == 1 else None
    original_proposal = copy.deepcopy(proposal)
    result = build(job, index, replacement=proposal)
    assert result == build(job, index, replacement=proposal)
    assert job == original and proposal == original_proposal
    plan = plan_of(job)
    assert type(result.baseline) is type(plan)
    assert result.baseline == plan and result.baseline is not plan
    assert result.days[1].activities == plan.days[1].activities
    assert tuple(e.route for e in result.days[1].edges) == plan.days[1].routes
    assert not hasattr(result, "status")  # Not a READY result or a commit.
    assert {"schedule", "route", "source", "budget", "scope"} <= set(result.pending_validations)
    activities = result.days[0].activities
    old = plan.days[0].activities
    if index == 0:
        assert activities == old[1:]
    elif index == 1:
        assert proposal is not None
        assert activities == (proposal.activity, old[1])
        assert result.locations[-1] == proposal.location
    elif index == 2:
        assert activities[0].start_time == time(10, 15)
        assert activities[0].end_time == time(12, 15)
        assert activities[1] == old[1]
    else:
        assert tuple(a.item_id for a in activities) == tuple(a.item_id for a in reversed(old))
        assert tuple(a.start_time for a in activities) == tuple(a.start_time for a in old)
        for new in activities:
            previous = next(a for a in old if a.item_id == new.item_id)
            assert new.cost_items == previous.cost_items and new.source_ids == previous.source_ids
            assert (
                new.end_time.hour - new.start_time.hour
                == previous.end_time.hour - previous.start_time.hour
            )


@pytest.mark.parametrize("index", range(4))
def test_route_ancestry_and_no_fabricated_measurements(index: int) -> None:
    job = baseline()
    result = build(job, index, replacement=replacement_for(job) if index == 1 else None)
    original = plan_of(job).days[0]
    allowed = set(result.impact.route_refs)
    edges = result.days[0].edges
    nodes = [
        original.accommodation_location_id,
        *(a.location_id for a in result.days[0].activities),
        original.accommodation_location_id,
    ]
    assert len(edges) == len(nodes) - 1
    for i, edge in enumerate(edges):
        assert (edge.requirement.origin_location_id, edge.requirement.destination_location_id) == (
            nodes[i],
            nodes[i + 1],
        )
        if edge.route is None:
            assert set(edge.origin_refs) <= allowed and edge.origin_refs
        else:
            assert edge.route in original.routes
    if index == 0:
        assert edges[0].route is None
        assert set(edges[0].origin_refs) == {r.route_id for r in original.routes[:2]}
        assert edges[-1].route == original.routes[-1]
    if index == 2:
        assert tuple(e.route for e in edges) == original.routes


@pytest.mark.parametrize("index", range(4))
def test_budget_is_explicitly_analysis_only_and_sources_are_not_dropped(index: int) -> None:
    job = baseline()
    result = build(job, index, replacement=replacement_for(job) if index == 1 else None)
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    assert result.budget_analysis == facts.budget_effect(commands(job)[index])
    assert set(result.pending_cost_refs) == facts.scoped_costs(commands(job)[index])
    assert job.result is not None
    assert result.sources[: len(job.result.sources)] == job.result.sources
    if index != 2:
        assert result.budget_analysis.after.unknown_count > 0
    for cost in result.budget_analysis.after.cost_items:
        if cost.confidence.value == "unknown":
            assert cost.amount is None


@pytest.mark.parametrize(
    "change",
    (
        "missing",
        "cross_city",
        "wrong_date",
        "wrong_category",
        "dangling_location",
        "dangling_source",
        "duplicate_source",
        "overwrite_source",
        "activity_collision",
        "cost_collision",
        "entity_collision",
        "unrelated_source",
        "outside_window",
        "overlap",
    ),
)
def test_bad_replacement_fails_closed(change: str) -> None:
    job = baseline()
    proposal = replacement_for(job)
    plan = plan_of(job)
    assert job.result is not None
    if change == "missing":
        proposal = None  # type: ignore[assignment]
    elif change in {"cross_city", "wrong_category"}:
        field, value = (
            ("city_adcode", "110000") if change == "cross_city" else ("category", "hotel")
        )
        proposal = replace(proposal, location=proposal.location.model_copy(update={field: value}))
    elif change == "wrong_date":
        proposal = replace(proposal, local_date=plan.end_date)
    elif change in {
        "dangling_location",
        "activity_collision",
        "entity_collision",
        "outside_window",
        "overlap",
        "dangling_source",
    }:
        changes: dict[str, dict[str, Any]] = {
            "dangling_location": {"location_id": UUID(int=7000)},
            "activity_collision": {"item_id": plan.days[1].activities[0].item_id},
            "entity_collision": {"item_id": plan.days[0].routes[0].route_id},
            "outside_window": {"start_time": time(1), "end_time": time(2)},
            "overlap": {"end_time": time(14, 30)},
            "dangling_source": {"source_ids": (UUID(int=9999),)},
        }
        proposal = replace(proposal, activity=proposal.activity.model_copy(update=changes[change]))
    elif change == "cost_collision":
        cost = proposal.activity.cost_items[0].model_copy(
            update={"cost_id": plan.budget_summary.cost_items[0].cost_id}
        )
        proposal = replace(
            proposal, activity=proposal.activity.model_copy(update={"cost_items": (cost,)})
        )
    elif change == "duplicate_source":
        proposal = replace(proposal, sources=proposal.sources * 2)
    elif change == "overwrite_source":
        proposal = replace(
            proposal,
            sources=(
                *proposal.sources,
                job.result.sources[0].model_copy(update={"source_type": "overwrite"}),
            ),
        )
    elif change == "unrelated_source":
        proposal = replace(
            proposal,
            sources=(
                *proposal.sources,
                proposal.sources[0].model_copy(update={"source_id": UUID(int=7999)}),
            ),
        )
    with pytest.raises(DomainInvariantError):
        build(job, 1, replacement=proposal)


@pytest.mark.parametrize("index", (0, 2, 3))
def test_replacement_on_other_commands_is_rejected(index: int) -> None:
    with pytest.raises(DomainInvariantError):
        build(baseline(), index, replacement=replacement_for(baseline()))


@pytest.mark.parametrize(
    "kind", ("unknown_target", "omitted", "cross_day", "wrong_date", "duplicate")
)
def test_invalid_target_and_reorder_set_are_rejected(kind: str) -> None:
    job = baseline()
    day = plan_of(job).days[0]
    good = PROJECTOR.analyze(job, commands(job)[3], evaluated_at=NOW)
    with pytest.raises(DomainInvariantError):
        ids = tuple(a.item_id for a in day.activities)
        command: ReplanCommand
        if kind == "unknown_target":
            command = DeleteActivity(UUID(int=9999))
        else:
            ids = ids[:1] if kind == "omitted" else ids
            ids = (
                ids + (plan_of(job).days[1].activities[0].item_id,) if kind == "cross_day" else ids
            )
            ids = (ids[0], ids[0]) if kind == "duplicate" else ids
            when = day.local_date + timedelta(days=4) if kind == "wrong_date" else day.local_date
            command = ReorderActivities(when, ids)
        build_replan_candidate(job, command, good, evaluated_at=NOW)


@pytest.mark.parametrize(
    "field", ("direct_refs", "route_refs", "transitive_refs", "affected_dates")
)
def test_narrowed_or_foreign_impact_cannot_authorize_changes(field: str) -> None:
    job = baseline()
    command = commands(job)[0]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    narrowed: dict[str, Any] = {field: ()}
    with pytest.raises(DomainInvariantError):
        build_replan_candidate(job, command, replace(impact, **narrowed), evaluated_at=NOW)


@pytest.mark.parametrize(
    "times,valid",
    (
        ((time(9), time(10)), True),
        ((time(12), time(14)), True),
        ((time(13), time(14, 1)), False),
        ((time(1), time(2)), False),
    ),
)
def test_adjust_time_window_and_overlap_boundaries(times: tuple[time, time], valid: bool) -> None:
    job = baseline()
    command = AdjustActivityTime(plan_of(job).days[0].activities[0].item_id, *times)
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    if valid:
        result = build_replan_candidate(job, command, impact, evaluated_at=NOW)
        assert result.days[0].activities[0].start_time == times[0]
    else:
        with pytest.raises(DomainInvariantError):
            build_replan_candidate(job, command, impact, evaluated_at=NOW)


@pytest.mark.parametrize("v2", (False, True))
def test_delete_last_activity_respects_original_version(v2: bool) -> None:
    job = baseline(v2)
    command = DeleteActivity(plan_of(job).days[1].activities[0].item_id)
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    if v2:
        with pytest.raises(DomainInvariantError):
            build_replan_candidate(job, command, impact, evaluated_at=NOW)
    else:
        result = build_replan_candidate(job, command, impact, evaluated_at=NOW)
        assert result.days[1].activities == () and result.days[1].edges == ()


def test_known_replacement_cost_is_retained_without_claiming_final_budget() -> None:
    job = baseline(True)
    proposal = replacement_for(job)
    cost = proposal.activity.cost_items[0].model_copy(
        update={
            "confidence": type(proposal.activity.cost_items[0].confidence).ESTIMATED,
            "amount": Money(amount=Decimal("12.00")),
        }
    )
    proposal = replace(
        proposal, activity=proposal.activity.model_copy(update={"cost_items": (cost,)})
    )
    result = build(job, 1, replacement=proposal)
    assert isinstance(result.baseline, TripPlanV2)
    assert result.days[0].activities[0].cost_items[0].amount == Money(amount=Decimal("12.00"))
    assert result.budget_analysis.after.unknown_count > 0


def test_corrupted_baseline_and_clock_fail_closed() -> None:
    job = baseline()
    command = commands(job)[0]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)
    for changed in (modified(job, plan=None), job):
        with pytest.raises(DomainInvariantError):
            build_replan_candidate(changed, command, impact, evaluated_at=NOW.replace(tzinfo=None))


def test_same_id_location_refresh_invalidates_old_route_measurements() -> None:
    job = baseline()
    proposal = replacement_for(job)
    facts = PROJECTOR.project(job.result, evaluated_at=NOW)
    old_location = facts.locations[plan_of(job).days[0].activities[0].location_id]
    location = old_location.model_copy(update={"name": "Refreshed museum", "category": "museum"})
    proposal = replace(
        proposal,
        location=location,
        activity=proposal.activity.model_copy(update={"location_id": location.location_id}),
    )
    result = build(job, 1, replacement=proposal)
    assert all(edge.route is None for edge in result.days[0].edges[:2])
    assert result.days[0].edges[-1].route == plan_of(job).days[0].routes[-1]


@pytest.mark.parametrize("bad_time", (False, True))
def test_reorder_rejects_overflow_and_overlap_without_repair(bad_time: bool) -> None:
    job = baseline()
    plan = plan_of(job)
    day = plan.days[0]
    activity = day.activities[1].model_copy(
        update={
            "start_time": time(19) if bad_time else time(14),
            "end_time": time(20),
        }
    )
    day = day.model_copy(update={"activities": (day.activities[0], activity)})
    job = modified(job, plan=plan.model_copy(update={"days": (day, plan.days[1])}))
    original = copy.deepcopy(job)
    with pytest.raises(DomainInvariantError):
        build(job, 3)
    assert job == original


@pytest.mark.parametrize("index", (0, 1, 2))
def test_all_single_target_commands_reject_missing_target(index: int) -> None:
    job = baseline()
    valid = commands(job)[index]
    assert not isinstance(valid, ReorderActivities)
    impact = PROJECTOR.analyze(job, valid, evaluated_at=NOW)
    invalid = replace(valid, target_activity_id=UUID(int=9000))
    with pytest.raises(DomainInvariantError):
        build_replan_candidate(job, invalid, impact, evaluated_at=NOW)


@pytest.mark.parametrize("kind", ("future", "duplicate_refs", "unknown_amount", "duplicate_costs"))
def test_replacement_cannot_smuggle_invalid_typed_facts(kind: str) -> None:
    job = baseline()
    value = replacement_for(job)
    if kind == "future":
        value = replace(
            value,
            sources=(value.sources[0].model_copy(update={"fetched_at": NOW + timedelta(days=1)}),),
        )
    else:
        updates: dict[str, Any] = {"source_ids": value.activity.source_ids * 2}
        if kind != "duplicate_refs":
            costs = (
                value.activity.cost_items * 2
                if kind == "duplicate_costs"
                else (
                    value.activity.cost_items[0].model_copy(
                        update={"amount": Money(amount=Decimal("1.00"))}
                    ),
                )
            )
            updates = {"cost_items": costs}
        value = replace(value, activity=value.activity.model_copy(update=updates))
    with pytest.raises(DomainInvariantError):
        build(job, 1, replacement=value)


def test_same_location_different_activity_does_not_reuse_deleted_edge() -> None:
    job = baseline()
    plan = plan_of(job)
    day = plan.days[0]
    loc = day.activities[0].location_id
    second = day.activities[1].model_copy(update={"location_id": loc})
    routes = (
        day.routes[0],
        day.routes[1].model_copy(update={"destination_location_id": loc}),
        day.routes[2].model_copy(update={"origin_location_id": loc}),
    )
    changed = day.model_copy(update={"activities": (day.activities[0], second), "routes": routes})
    job = modified(job, plan=plan.model_copy(update={"days": (changed, plan.days[1])}))
    candidate = build(job)
    edge = candidate.days[0].edges[0]
    assert edge.route is None and len(edge.origin_refs) == 2
    assert candidate.days[0].edges[1].route == routes[2]


@pytest.mark.parametrize("index", range(4))
def test_candidate_graph_is_detached_from_inputs(index: int) -> None:
    job = baseline()
    before = copy.deepcopy(job)
    proposal = replacement_for(job) if index == 1 else None
    saved = copy.deepcopy(proposal)
    candidate = build(job, index, replacement=proposal)
    # Bypass the DTO freeze deliberately to test graph ownership, not setters.
    object.__setattr__(candidate.days[0].activities[0], "title", "Only the draft changed")
    object.__setattr__(candidate.sources[0], "source_type", "Only the draft changed")
    assert job == before and proposal == saved


@pytest.mark.parametrize("index", range(4))
def test_pure_transform_has_zero_io(index: int) -> None:
    # Full-suite collection may import the app; the original safety assertions
    # must observe only this module and its operation in a clean interpreter.
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys, pytest; from tests.application.test_replan_candidate import "
            "_assert_pure_transform_has_zero_io as check; "
            "check(int(sys.argv[1]), pytest.MonkeyPatch())",
            str(index),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "APP_ENV": "test", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _assert_pure_transform_has_zero_io(index: int, monkeypatch: pytest.MonkeyPatch) -> None:
    job = baseline()
    proposal = replacement_for(job) if index == 1 else None
    command = commands(job)[index]
    impact = PROJECTOR.analyze(job, command, evaluated_at=NOW)

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("candidate_io_forbidden")

    with monkeypatch.context() as guarded:
        for owner, attribute in (
            (builtins, "open"),
            (io, "open"),
            (os, "open"),
            (sqlite3, "connect"),
            (socket, "socket"),
            (os, "getenv"),
        ):
            guarded.setattr(owner, attribute, denied)
        candidate = build_replan_candidate(
            job, command, impact, evaluated_at=NOW, replacement=proposal
        )
    assert candidate.days and "intelligent_travel_assistant.app" not in sys.modules
