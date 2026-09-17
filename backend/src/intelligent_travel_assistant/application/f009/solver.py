"""Bounded deterministic F-009 schedule enumeration and route validation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, pairwise, permutations, product
from math import asin, cos, radians, sin, sqrt
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.application.f009.ports import F009RouteFact
from intelligent_travel_assistant.contracts.f009 import (
    FeasibilityConflictCode,
    Gcj02Point,
    PoiImportance,
    PoiIntent,
    PoiOption,
    PreplanningSelection,
    PreplanningTripInput,
)
from intelligent_travel_assistant.contracts.trip_planning import Pace, TransportMode

EARTH_RADIUS_METERS: Final = 6_371_008.8
MAX_CANDIDATES: Final = 3
MAX_ATOMIC_POIS_PER_DAY: Final = 4
EXTREME_STRAIGHT_LINE_METERS: Final = 120_000
MAX_ROUTE_METERS: Final = 200_000
MAX_ROUTE_MINUTES: Final = 240
MAX_WALKING_METERS: Final = 20_000
MAX_WALKING_MINUTES: Final = 300
ROUTE_ENDPOINT_TOLERANCE_METERS: Final = 500


@dataclass(frozen=True, slots=True)
class ScheduleDayCandidate:
    day_offset: int
    intents: tuple[PoiIntent, ...]


@dataclass(frozen=True, slots=True)
class ScheduleCandidate:
    days: tuple[ScheduleDayCandidate, ...]
    omitted_location_ids: tuple[UUID, ...]
    straight_line_meters: int
    preferred_day_deviation: int
    tie_break: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RouteValidation:
    accepted: bool
    code: FeasibilityConflictCode | None = None


def haversine_meters(origin: Gcj02Point, destination: Gcj02Point) -> int:
    """Return a rounded GCJ-02 straight-line screening distance."""

    lat1 = radians(origin.latitude)
    lat2 = radians(destination.latitude)
    lat_delta = lat2 - lat1
    lon_delta = radians(destination.longitude - origin.longitude)
    value = sin(lat_delta / 2) ** 2 + cos(lat1) * cos(lat2) * sin(lon_delta / 2) ** 2
    return round(2 * EARTH_RADIUS_METERS * asin(sqrt(value)))


def validate_route_fact(
    *,
    origin: Gcj02Point,
    destination: Gcj02Point,
    mode: TransportMode,
    fact: F009RouteFact,
) -> RouteValidation:
    """Apply frozen spatial/schema thresholds without classifying Provider failures."""

    straight = haversine_meters(origin, destination)
    if not fact.points:
        return RouteValidation(False, FeasibilityConflictCode.ROUTE_ENDPOINT_MISMATCH)
    if (
        haversine_meters(origin, fact.points[0]) > ROUTE_ENDPOINT_TOLERANCE_METERS
        or haversine_meters(destination, fact.points[-1]) > ROUTE_ENDPOINT_TOLERANCE_METERS
    ):
        return RouteValidation(False, FeasibilityConflictCode.ROUTE_ENDPOINT_MISMATCH)
    if fact.distance_meters > MAX_ROUTE_METERS or fact.duration_minutes > MAX_ROUTE_MINUTES:
        return RouteValidation(False, FeasibilityConflictCode.EXTREME_SAME_CITY_LEG)
    if straight < 1_000 and fact.distance_meters > 10_000:
        return RouteValidation(False, FeasibilityConflictCode.IMPLAUSIBLE_ROUTE_RATIO)
    if (
        straight >= 1_000
        and fact.distance_meters / straight > 8
        and fact.distance_meters - straight > 20_000
    ):
        return RouteValidation(False, FeasibilityConflictCode.IMPLAUSIBLE_ROUTE_RATIO)
    if mode is TransportMode.WALKING and (
        fact.distance_meters > MAX_WALKING_METERS or fact.duration_minutes > MAX_WALKING_MINUTES
    ):
        return RouteValidation(False, FeasibilityConflictCode.ROUTE_UNREACHABLE)
    return RouteValidation(True)


def enumerate_schedule_candidates(
    *,
    trip: PreplanningTripInput,
    selection: PreplanningSelection,
    options: dict[UUID, PoiOption],
) -> tuple[ScheduleCandidate, ...]:
    """Exhaustively enumerate the frozen <=8 POI model and retain its best three."""

    lodging = options[selection.accommodation.route_anchor_location_id]
    ranked: list[tuple[tuple[object, ...], ScheduleCandidate]] = []
    all_ids = {item.location_id for item in selection.pois}
    for chosen in _selection_variants(selection.pois):
        blocks = _blocks(chosen)
        if len(blocks) < trip.day_count:
            continue
        for ordered_blocks in permutations(blocks):
            for split in combinations(range(1, len(blocks)), trip.day_count - 1):
                partitions = _partition(ordered_blocks, split)
                if any(
                    sum(len(block) for block in day) > MAX_ATOMIC_POIS_PER_DAY for day in partitions
                ):
                    continue
                days = tuple(
                    ScheduleDayCandidate(
                        day_offset=day_offset,
                        intents=tuple(intent for block in day for intent in block),
                    )
                    for day_offset, day in enumerate(partitions)
                )
                if _has_extreme_leg(lodging, days, options):
                    continue
                chosen_ids = {intent.location_id for day in days for intent in day.intents}
                omitted = tuple(sorted(all_ids - chosen_ids, key=str))
                preferred_deviation = sum(
                    abs(day.day_offset - intent.preferred_day)
                    for day in days
                    for intent in day.intents
                    if intent.preferred_day is not None
                )
                straight = _schedule_distance(lodging, days, options)
                tie_break = tuple(str(intent.location_id) for day in days for intent in day.intents)
                candidate = ScheduleCandidate(
                    days=days,
                    omitted_location_ids=omitted,
                    straight_line_meters=straight,
                    preferred_day_deviation=preferred_deviation,
                    tie_break=tie_break,
                )
                score: tuple[object, ...] = (
                    len(omitted),
                    preferred_deviation,
                    straight,
                    tie_break,
                )
                ranked.append((score, candidate))
    ranked.sort(key=lambda item: item[0])
    unique: list[ScheduleCandidate] = []
    seen: set[tuple[str, ...]] = set()
    for _, candidate in ranked:
        if candidate.tie_break in seen:
            continue
        seen.add(candidate.tie_break)
        unique.append(candidate)
        if len(unique) == MAX_CANDIDATES:
            break
    return tuple(unique)


def transport_budget_minutes(pace: Pace) -> int:
    return {Pace.RELAXED: 120, Pace.BALANCED: 180, Pace.INTENSIVE: 240}[pace]


def _selection_variants(intents: tuple[PoiIntent, ...]) -> tuple[tuple[PoiIntent, ...], ...]:
    either_groups: dict[str, list[PoiIntent]] = {}
    independent: list[PoiIntent] = []
    for intent in intents:
        if intent.either_or_group_id is None:
            independent.append(intent)
        else:
            either_groups.setdefault(intent.either_or_group_id, []).append(intent)

    choices: list[tuple[tuple[PoiIntent, ...], ...]] = []
    for members in either_groups.values():
        variants: tuple[tuple[PoiIntent, ...], ...] = tuple((member,) for member in members)
        if members[0].importance is PoiImportance.OPTIONAL and all(
            member.omission_allowed for member in members
        ):
            variants = ((), *variants)
        choices.append(variants)
    for intent in independent:
        choices.append(
            ((), (intent,))
            if intent.importance is PoiImportance.OPTIONAL and intent.omission_allowed
            else ((intent,),)
        )
    return tuple(
        tuple(intent for choice in variant for intent in choice) for variant in product(*choices)
    )


def _blocks(intents: tuple[PoiIntent, ...]) -> tuple[tuple[PoiIntent, ...], ...]:
    grouped: dict[str, list[PoiIntent]] = {}
    standalone: list[tuple[PoiIntent, ...]] = []
    for intent in intents:
        if intent.visit_group_id is None:
            standalone.append((intent,))
        else:
            grouped.setdefault(intent.visit_group_id, []).append(intent)
    visit_blocks = [
        tuple(sorted(members, key=lambda item: str(item.location_id)))
        for members in grouped.values()
    ]
    return tuple(sorted([*standalone, *visit_blocks], key=lambda block: str(block[0].location_id)))


def _partition(
    blocks: tuple[tuple[PoiIntent, ...], ...],
    split: tuple[int, ...],
) -> tuple[tuple[tuple[PoiIntent, ...], ...], ...]:
    boundaries = (0, *split, len(blocks))
    return tuple(
        blocks[boundaries[index] : boundaries[index + 1]] for index in range(len(boundaries) - 1)
    )


def _has_extreme_leg(
    lodging: PoiOption,
    days: tuple[ScheduleDayCandidate, ...],
    options: dict[UUID, PoiOption],
) -> bool:
    for day in days:
        chain = (
            lodging,
            *(options[intent.route_anchor_location_id] for intent in day.intents),
            lodging,
        )
        if any(
            haversine_meters(left.coordinate_gcj02, right.coordinate_gcj02)
            > EXTREME_STRAIGHT_LINE_METERS
            for left, right in pairwise(chain)
        ):
            return True
    return False


def _schedule_distance(
    lodging: PoiOption,
    days: tuple[ScheduleDayCandidate, ...],
    options: dict[UUID, PoiOption],
) -> int:
    total = 0
    for day in days:
        chain = (
            lodging,
            *(options[intent.route_anchor_location_id] for intent in day.intents),
            lodging,
        )
        total += sum(
            haversine_meters(left.coordinate_gcj02, right.coordinate_gcj02)
            for left, right in pairwise(chain)
        )
    return total
