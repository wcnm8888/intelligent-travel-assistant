"""Pure local drafts, never serialized as plans or accepted as commits.

R3 must resolve route requirements and final cost/source facts, then validate the
whole candidate. The conservative R1 budget analysis is NOT a candidate quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from intelligent_travel_assistant.application.planning.scheduling import RouteRequirement
from intelligent_travel_assistant.application.repositories import PlanningJob
from intelligent_travel_assistant.application.services.replan_facts import (
    ReplanFactProjector,
    ReplanFacts,
)
from intelligent_travel_assistant.contracts import (
    ItineraryItem,
    LocationRef,
    PlanDay,
    RouteLeg,
    SourceRecord,
    TripPlan,
    TripPlanV2,
)
from intelligent_travel_assistant.domain import (
    ActivityTimeSlot,
    AdjustActivityTime,
    DailyAvailability,
    DeleteActivity,
    DomainInvariantError,
    ImpactAnalysis,
    ImpactDisposition,
    MultiDayTimePlan,
    ReorderActivities,
    ReplaceActivity,
    ReplanBudgetResult,
    ReplanCommand,
    TwoDayTimePlan,
    evaluate_freshness,
)


@dataclass(frozen=True, slots=True)
class ActivityReplacement:
    local_date: date
    activity: ItineraryItem
    location: LocationRef
    sources: tuple[SourceRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateEdge:
    requirement: RouteRequirement
    origin_refs: tuple[UUID, ...]
    route: RouteLeg | None  # None means measurements are required, never zero.


@dataclass(frozen=True, slots=True)
class CandidateDay:
    baseline: PlanDay
    activities: tuple[ItineraryItem, ...]
    edges: tuple[CandidateEdge, ...]


@dataclass(frozen=True, slots=True)
class ReplanCandidate:
    baseline: TripPlan  # Exact legacy/V2 runtime type; no revised public DTO.
    days: tuple[CandidateDay, ...]
    locations: tuple[LocationRef, ...]
    sources: tuple[SourceRecord, ...]
    impact: ImpactAnalysis
    budget_analysis: ReplanBudgetResult
    pending_cost_refs: tuple[UUID, ...]
    pending_validations: tuple[str, ...] = ("schedule", "route", "source", "budget", "scope")


def _require(condition: bool) -> None:
    if not condition:
        raise DomainInvariantError("replan_candidate_invalid", field="candidate")


def _replacement(
    value: ActivityReplacement,
    command: ReplaceActivity,
    facts: ReplanFacts,
    evaluated_at: datetime,
) -> tuple[ItineraryItem, tuple[LocationRef, ...], tuple[SourceRecord, ...]]:
    activity = ItineraryItem.model_validate(value.activity.model_dump(mode="python"))
    location = LocationRef.model_validate(value.location.model_dump(mode="python"))
    additions = tuple(
        SourceRecord.model_validate(s.model_dump(mode="python")) for s in value.sources
    )
    _require(value.local_date == facts.activity_days[command.target_activity_id].local_date)
    _require(location.city_adcode == facts.plan.city_adcode)
    _require(location.category in command.replacement_categories)
    _require(activity.location_id == location.location_id)
    existing = {s.ref_id for s in facts.snapshots} | set(facts.locations)
    allowed = facts.allowed(command)
    _require(activity.item_id == command.target_activity_id or activity.item_id not in existing)
    _require(location.location_id not in existing or location.location_id in facts.locations)
    if location.location_id in facts.locations:
        _require(
            location == facts.locations[location.location_id] or location.location_id in allowed
        )
    costs = activity.cost_items
    _require(len({c.cost_id for c in costs}) == len(costs))
    for cost in costs:
        _require(
            cost.cost_id not in existing
            or facts.owners.get(cost.cost_id) == ("activity", command.target_activity_id)
        )
    sources = dict(facts.sources)
    _require(len({s.source_id for s in additions}) == len(additions))
    for source in additions:
        evaluate_freshness(source.fetched_at, source.valid_until, evaluated_at)
        _require(source.source_id not in existing or sources.get(source.source_id) == source)
        sources[source.source_id] = source
    refs = (
        *activity.source_ids,
        *location.source_ids,
        *(sid for c in costs for sid in c.source_ids),
    )
    _require(set(refs) <= sources.keys())
    _require({s.source_id for s in additions} <= set(refs))
    for ids in (activity.source_ids, location.source_ids, *(c.source_ids for c in costs)):
        _require(len(ids) == len(set(ids)))
    identities = (activity.item_id, location.location_id, *(c.cost_id for c in costs), *sources)
    _require(len(identities) == len(set(identities)))
    locations = dict(facts.locations)
    locations[location.location_id] = location
    return activity, tuple(locations.values()), tuple(sources.values())


def _activities(
    day: PlanDay,
    command: ReplanCommand,
    replacement: ItineraryItem | None,
) -> tuple[ItineraryItem, ...]:
    if isinstance(command, ReorderActivities):
        if day.local_date != command.local_date:
            return day.activities
        by_id = {a.item_id: a for a in day.activities}
        result = []
        # Reorder only the explicitly selected day's slots, preserving durations.
        # No compaction/overflow repair: overlapping or out-of-window slots fail.
        for slot, aid in zip(day.activities, command.ordered_activity_ids, strict=True):
            activity = by_id[aid]
            duration = datetime.combine(day.local_date, activity.end_time) - datetime.combine(
                day.local_date, activity.start_time
            )
            end = datetime.combine(day.local_date, slot.start_time) + duration
            _require(end.date() == day.local_date)
            result.append(
                activity.model_copy(update={"start_time": slot.start_time, "end_time": end.time()})
            )
        return tuple(result)
    result = []
    for activity in day.activities:
        if activity.item_id != command.target_activity_id:
            result.append(activity)
        elif isinstance(command, ReplaceActivity):
            assert replacement is not None
            result.append(replacement)
        elif isinstance(command, AdjustActivityTime):
            result.append(
                activity.model_copy(
                    update={"start_time": command.start_time, "end_time": command.end_time}
                )
            )
        else:
            _require(isinstance(command, DeleteActivity))
    return tuple(result)


def _edges(
    day: PlanDay,
    activities: tuple[ItineraryItem, ...],
    offset: int,
    command: ReplanCommand,
    impact: ImpactAnalysis,
    changed_locations: set[UUID],
) -> tuple[CandidateEdge, ...]:
    if not activities:
        return ()
    old_nodes: tuple[UUID | None, ...] = (None, *(a.item_id for a in day.activities), None)
    new_ids = tuple(a.item_id for a in activities)
    if isinstance(command, ReplaceActivity) and command.target_activity_id in old_nodes:
        index = old_nodes.index(command.target_activity_id) - 1
        new_ids = tuple(
            command.target_activity_id if i == index else aid for i, aid in enumerate(new_ids)
        )
    new_nodes = (None, *new_ids, None)
    locations = (
        day.accommodation_location_id,
        *(a.location_id for a in activities),
        day.accommodation_location_id,
    )
    result = []
    for i, (left, right) in enumerate(zip(new_nodes, new_nodes[1:], strict=False)):
        requirement = RouteRequirement(offset, locations[i], locations[i + 1])
        matching = next(
            (
                r
                for j, r in enumerate(day.routes)
                if old_nodes[j : j + 2] == (left, right)
                and (r.origin_location_id, r.destination_location_id) == locations[i : i + 2]
                and not (set(locations[i : i + 2]) & changed_locations)
            ),
            None,
        )
        if matching is not None:
            origins: tuple[UUID, ...] = (matching.route_id,)
        else:
            if isinstance(command, ReorderActivities):
                indices = {
                    j
                    for j in range(len(day.routes))
                    if old_nodes[j] in {left, right} or old_nodes[j + 1] in {left, right}
                }
            else:
                start = 0 if i == 0 else old_nodes.index(left)
                end = len(old_nodes) - 1 if i == len(activities) else old_nodes.index(right)
                _require(start < end)
                indices = set(range(start, end))
            origins = tuple(
                sorted((day.routes[j].route_id for j in indices), key=lambda ref: ref.hex)
            )
            _require(bool(origins) and set(origins) <= set(impact.route_refs))
        result.append(CandidateEdge(requirement, origins, matching))
    return tuple(result)


def build_replan_candidate(
    job: PlanningJob,
    command: ReplanCommand,
    impact: ImpactAnalysis,
    *,
    evaluated_at: datetime,
    replacement: ActivityReplacement | None = None,
) -> ReplanCandidate:
    """Validate typed inputs and approved impact before constructing a local draft.

    Existing source records and untouched entity facts are preserved. Source DROP,
    final pricing, Provider freshness/route validation and commit are NOT performed.
    """
    try:
        projector = ReplanFactProjector()
        current = projector.analyze(job, command, evaluated_at=evaluated_at)
        _require(current == impact and current.disposition is not ImpactDisposition.REJECT)
        facts = projector.project(job.result, evaluated_at=evaluated_at)
        locations, sources = tuple(facts.locations.values()), tuple(facts.sources.values())
        activity = None
        if isinstance(command, ReplaceActivity):
            _require(isinstance(replacement, ActivityReplacement))
            assert replacement is not None
            activity, locations, sources = _replacement(replacement, command, facts, evaluated_at)
        else:
            _require(replacement is None)
        changed_locations = {
            loc.location_id for loc in locations if facts.locations.get(loc.location_id) != loc
        }
        days = tuple(
            CandidateDay(day, changed, _edges(day, changed, i, command, current, changed_locations))
            for i, day in enumerate(facts.plan.days)
            for changed in (_activities(day, command, activity),)
        )
        windows = tuple(
            DailyAvailability(w.day_offset, w.start_time, w.end_time)
            for w in job.request.day_windows
        )
        slots = tuple(
            ActivityTimeSlot(a.item_id, day.baseline.local_date, a.start_time, a.end_time)
            for day in days
            for a in day.activities
        )
        if isinstance(facts.plan, TripPlanV2):
            MultiDayTimePlan(facts.plan.start_date, facts.plan.end_date, windows, slots)
        else:
            TwoDayTimePlan(facts.plan.start_date, windows, slots)
        for day in days:
            _require(
                all(
                    a.end_time <= b.start_time
                    for a, b in zip(day.activities, day.activities[1:], strict=False)
                )
            )
        return ReplanCandidate(
            facts.plan,
            days,
            locations,
            sources,
            current,
            facts.budget_effect(command),
            tuple(sorted(facts.scoped_costs(command), key=lambda ref: ref.hex)),
        )
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        raise DomainInvariantError("replan_candidate_invalid", field="candidate") from None
