"""Pure F-003 local-replanning commands, impact, diff, budget, and source policy."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

from intelligent_travel_assistant.domain.budget import (
    BudgetAssessment,
    BudgetCostItem,
    BudgetSummaryResult,
    summarize_budget,
)
from intelligent_travel_assistant.domain.foundation import DomainInvariantError, Money
from intelligent_travel_assistant.domain.provider_result import DataFreshness

_SAFE_CATEGORY: Final = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_SAFE_CODE: Final = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_UNSAFE_TEXT: Final = re.compile(
    r"authorization\s*:|cookie\s*:|(?:api[_-]?key|token|jwt|secret|password|"
    r"private[_-]?key)\s*[=:]|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ReplanOperation(StrEnum):
    REPLACE_ACTIVITY = "replace_activity"
    DELETE_ACTIVITY = "delete_activity"
    ADJUST_ACTIVITY_TIME = "adjust_activity_time"
    REORDER_ACTIVITIES = "reorder_activities"


class ReplanStatus(StrEnum):
    """Independent lifecycle; it must not be added to PlanningStatus."""

    ANALYZING = "analyzing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    CONFLICT = "conflict"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ReplanDecisionStatus(StrEnum):
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class ReplanChoice(StrEnum):
    APPROVE = "approve"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class ReplaceActivity:
    target_activity_id: UUID
    replacement_categories: tuple[str, ...]
    reason_code: str | None = None
    operation: ReplanOperation = field(init=False, default=ReplanOperation.REPLACE_ACTIVITY)

    def __post_init__(self) -> None:
        _require_uuid(self.target_activity_id, field="target_activity_id")
        if (
            not isinstance(self.replacement_categories, tuple)
            or not 1 <= len(self.replacement_categories) <= 3
            or len(set(self.replacement_categories)) != len(self.replacement_categories)
            or any(
                not isinstance(value, str) or _SAFE_CATEGORY.fullmatch(value) is None
                for value in self.replacement_categories
            )
        ):
            raise DomainInvariantError(
                "replacement_categories_invalid", field="replacement_categories"
            )
        _require_reason_code(self.reason_code)


@dataclass(frozen=True, slots=True)
class DeleteActivity:
    target_activity_id: UUID
    reason_code: str | None = None
    operation: ReplanOperation = field(init=False, default=ReplanOperation.DELETE_ACTIVITY)

    def __post_init__(self) -> None:
        _require_uuid(self.target_activity_id, field="target_activity_id")
        _require_reason_code(self.reason_code)


@dataclass(frozen=True, slots=True)
class AdjustActivityTime:
    target_activity_id: UUID
    start_time: time
    end_time: time
    reason_code: str | None = None
    operation: ReplanOperation = field(init=False, default=ReplanOperation.ADJUST_ACTIVITY_TIME)

    def __post_init__(self) -> None:
        _require_uuid(self.target_activity_id, field="target_activity_id")
        if (
            not isinstance(self.start_time, time)
            or not isinstance(self.end_time, time)
            or self.start_time.tzinfo is not None
            or self.end_time.tzinfo is not None
            or self.end_time <= self.start_time
        ):
            raise DomainInvariantError("activity_time_range_invalid", field="end_time")
        _require_reason_code(self.reason_code)


@dataclass(frozen=True, slots=True)
class ReorderActivities:
    local_date: date
    ordered_activity_ids: tuple[UUID, ...]
    reason_code: str | None = None
    operation: ReplanOperation = field(init=False, default=ReplanOperation.REORDER_ACTIVITIES)

    def __post_init__(self) -> None:
        if not isinstance(self.local_date, date):
            raise DomainInvariantError("local_date_invalid", field="local_date")
        if not isinstance(self.ordered_activity_ids, tuple) or not self.ordered_activity_ids:
            raise DomainInvariantError("ordered_activity_ids_empty", field="ordered_activity_ids")
        if any(not isinstance(value, UUID) for value in self.ordered_activity_ids):
            raise DomainInvariantError("ordered_activity_ids_invalid", field="ordered_activity_ids")
        if len(set(self.ordered_activity_ids)) != len(self.ordered_activity_ids):
            raise DomainInvariantError(
                "ordered_activity_ids_duplicate", field="ordered_activity_ids"
            )
        _require_reason_code(self.reason_code)


type ReplanCommand = ReplaceActivity | DeleteActivity | AdjustActivityTime | ReorderActivities


class ImpactCategory(StrEnum):
    SAME_DAY_LOW = "same_day_low"
    ADJACENT_DAY = "adjacent_day"
    CROSS_DAY = "cross_day"
    ACCOMMODATION_EFFECT = "accommodation_effect"
    BUDGET_RISK = "budget_risk"
    SOURCE_REFRESH = "source_refresh"
    CROSS_CITY = "cross_city"
    UNKNOWN_IMPACT = "unknown_impact"


class ImpactDisposition(StrEnum):
    AUTO = "auto"
    CONFIRM = "confirm"
    REJECT = "reject"


class SourceAction(StrEnum):
    REUSE = "reuse"
    REFRESH = "refresh"
    DROP = "drop"


class SourceActionReason(StrEnum):
    UNAFFECTED_FRESH = "unaffected_fresh"
    AFFECTED = "affected"
    STALE = "stale"
    UNKNOWN_VALIDITY = "unknown_validity"
    REMOVED = "removed"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True, slots=True)
class ReplanSourceState:
    source_id: UUID
    freshness: DataFreshness
    required: bool

    def __post_init__(self) -> None:
        _require_uuid(self.source_id, field="source_id")
        if not isinstance(self.freshness, DataFreshness):
            raise DomainInvariantError("source_freshness_invalid", field="freshness")
        if type(self.required) is not bool:
            raise DomainInvariantError("source_required_invalid", field="required")


@dataclass(frozen=True, slots=True)
class SourceActionRecord:
    source_id: UUID
    action: SourceAction
    freshness: DataFreshness
    reason: SourceActionReason

    def __post_init__(self) -> None:
        _require_uuid(self.source_id, field="source_id")
        if not isinstance(self.action, SourceAction):
            raise DomainInvariantError("source_action_invalid", field="action")
        if not isinstance(self.freshness, DataFreshness):
            raise DomainInvariantError("source_freshness_invalid", field="freshness")
        if not isinstance(self.reason, SourceActionReason):
            raise DomainInvariantError("source_action_reason_invalid", field="reason")


@dataclass(frozen=True, slots=True)
class ImpactActivity:
    activity_id: UUID
    local_date: date
    city_adcode: str
    source_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        _require_uuid(self.activity_id, field="activity_id")
        if not isinstance(self.local_date, date):
            raise DomainInvariantError("local_date_invalid", field="local_date")
        if re.fullmatch(r"\d{6}", self.city_adcode) is None:
            raise DomainInvariantError("adcode_invalid", field="city_adcode")
        _require_unique_uuid_tuple(self.source_ids, field="source_ids")


@dataclass(frozen=True, slots=True)
class ImpactRoute:
    route_id: UUID
    local_date: date
    activity_ids: tuple[UUID, ...]
    source_ids: tuple[UUID, ...]
    touches_accommodation: bool = False

    def __post_init__(self) -> None:
        _require_uuid(self.route_id, field="route_id")
        if not isinstance(self.local_date, date):
            raise DomainInvariantError("local_date_invalid", field="local_date")
        _require_unique_uuid_tuple(self.activity_ids, field="activity_ids")
        _require_unique_uuid_tuple(self.source_ids, field="source_ids")
        if type(self.touches_accommodation) is not bool:
            raise DomainInvariantError(
                "touches_accommodation_invalid", field="touches_accommodation"
            )


@dataclass(frozen=True, slots=True)
class ReplanImpactContext:
    plan_id: UUID
    city_adcode: str
    travel_dates: tuple[date, date]
    accommodation_location_ids: tuple[UUID, ...]
    activities: tuple[ImpactActivity, ...]
    routes: tuple[ImpactRoute, ...]
    sources: tuple[ReplanSourceState, ...]
    dependencies_complete: bool = True

    def __post_init__(self) -> None:
        _require_uuid(self.plan_id, field="plan_id")
        if re.fullmatch(r"\d{6}", self.city_adcode) is None:
            raise DomainInvariantError("adcode_invalid", field="city_adcode")
        if (
            not isinstance(self.travel_dates, tuple)
            or len(self.travel_dates) != 2
            or any(not isinstance(value, date) for value in self.travel_dates)
            or self.travel_dates[1] != self.travel_dates[0] + timedelta(days=1)
        ):
            raise DomainInvariantError("travel_dates_invalid", field="travel_dates")
        _require_unique_uuid_tuple(
            self.accommodation_location_ids, field="accommodation_location_ids"
        )
        if not self.accommodation_location_ids:
            raise DomainInvariantError(
                "accommodation_reference_required", field="accommodation_location_ids"
            )
        if not isinstance(self.activities, tuple) or not all(
            isinstance(value, ImpactActivity) for value in self.activities
        ):
            raise DomainInvariantError("impact_activities_invalid", field="activities")
        if not isinstance(self.routes, tuple) or not all(
            isinstance(value, ImpactRoute) for value in self.routes
        ):
            raise DomainInvariantError("impact_routes_invalid", field="routes")
        if not isinstance(self.sources, tuple) or not all(
            isinstance(value, ReplanSourceState) for value in self.sources
        ):
            raise DomainInvariantError("impact_sources_invalid", field="sources")
        if type(self.dependencies_complete) is not bool:
            raise DomainInvariantError(
                "dependencies_complete_invalid", field="dependencies_complete"
            )
        activity_ids = tuple(value.activity_id for value in self.activities)
        route_ids = tuple(value.route_id for value in self.routes)
        source_ids = tuple(value.source_id for value in self.sources)
        _require_no_duplicates(activity_ids, code="impact_activity_duplicate", field="activities")
        _require_no_duplicates(route_ids, code="impact_route_duplicate", field="routes")
        _require_no_duplicates(source_ids, code="impact_source_duplicate", field="sources")
        if any(value.local_date not in self.travel_dates for value in self.activities):
            raise DomainInvariantError("activity_date_out_of_range", field="activities")
        if any(value.local_date not in self.travel_dates for value in self.routes):
            raise DomainInvariantError("route_date_out_of_range", field="routes")
        if any(set(value.activity_ids) - set(activity_ids) for value in self.routes):
            raise DomainInvariantError("route_activity_missing", field="routes")
        referenced_sources = {
            source_id for value in self.activities for source_id in value.source_ids
        }
        referenced_sources.update(
            source_id for value in self.routes for source_id in value.source_ids
        )
        if referenced_sources - set(source_ids):
            raise DomainInvariantError("impact_source_missing", field="sources")


@dataclass(frozen=True, slots=True)
class ImpactAnalysis:
    categories: tuple[ImpactCategory, ...]
    disposition: ImpactDisposition
    direct_refs: tuple[UUID, ...]
    transitive_refs: tuple[UUID, ...]
    affected_dates: tuple[date, ...]
    route_refs: tuple[UUID, ...]
    source_actions: tuple[SourceActionRecord, ...]
    required_validations: tuple[str, ...]
    confirmation_required: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.categories, tuple)
            or not self.categories
            or not all(isinstance(value, ImpactCategory) for value in self.categories)
            or len(set(self.categories)) != len(self.categories)
        ):
            raise DomainInvariantError("impact_categories_invalid", field="categories")
        if not isinstance(self.disposition, ImpactDisposition):
            raise DomainInvariantError("impact_disposition_invalid", field="disposition")
        if ImpactCategory.SAME_DAY_LOW in self.categories and (
            len(self.categories) != 1 or self.disposition is not ImpactDisposition.AUTO
        ):
            raise DomainInvariantError("same_day_low_not_exclusive", field="categories")
        if self.disposition is ImpactDisposition.AUTO and self.categories != (
            ImpactCategory.SAME_DAY_LOW,
        ):
            raise DomainInvariantError("auto_impact_invalid", field="categories")
        if (
            self.disposition is ImpactDisposition.REJECT
            and ImpactCategory.CROSS_CITY not in self.categories
        ):
            raise DomainInvariantError("rejected_impact_invalid", field="categories")
        for values, value_field in (
            (self.direct_refs, "direct_refs"),
            (self.transitive_refs, "transitive_refs"),
            (self.route_refs, "route_refs"),
        ):
            _require_unique_uuid_tuple(values, field=value_field)
        if not isinstance(self.affected_dates, tuple) or not all(
            isinstance(value, date) for value in self.affected_dates
        ):
            raise DomainInvariantError("affected_dates_invalid", field="affected_dates")
        if not isinstance(self.source_actions, tuple) or not all(
            isinstance(value, SourceActionRecord) for value in self.source_actions
        ):
            raise DomainInvariantError("source_actions_invalid", field="source_actions")
        if (
            not isinstance(self.required_validations, tuple)
            or any(_SAFE_CATEGORY.fullmatch(value) is None for value in self.required_validations)
            or len(set(self.required_validations)) != len(self.required_validations)
        ):
            raise DomainInvariantError("required_validations_invalid", field="required_validations")
        if type(self.confirmation_required) is not bool or self.confirmation_required != (
            self.disposition is ImpactDisposition.CONFIRM
        ):
            raise DomainInvariantError(
                "confirmation_requirement_invalid", field="confirmation_required"
            )


def plan_source_actions(
    sources: tuple[ReplanSourceState, ...],
    *,
    affected_source_ids: tuple[UUID, ...],
    dropped_source_ids: tuple[UUID, ...],
) -> tuple[SourceActionRecord, ...]:
    if not isinstance(sources, tuple) or not all(
        isinstance(value, ReplanSourceState) for value in sources
    ):
        raise DomainInvariantError("source_states_invalid", field="sources")
    known = tuple(value.source_id for value in sources)
    _require_no_duplicates(known, code="source_state_duplicate", field="sources")
    _require_unique_uuid_tuple(affected_source_ids, field="affected_source_ids")
    _require_unique_uuid_tuple(dropped_source_ids, field="dropped_source_ids")
    if set(affected_source_ids) & set(dropped_source_ids):
        raise DomainInvariantError("source_action_overlap", field="source_ids")
    if (set(affected_source_ids) | set(dropped_source_ids)) - set(known):
        raise DomainInvariantError("source_action_reference_missing", field="source_ids")

    affected = set(affected_source_ids)
    dropped = set(dropped_source_ids)
    records: list[SourceActionRecord] = []
    for source in sources:
        if source.source_id in dropped:
            action, reason = SourceAction.DROP, SourceActionReason.REMOVED
        elif not source.required:
            action, reason = SourceAction.DROP, SourceActionReason.NOT_REQUIRED
        elif source.source_id in affected:
            action, reason = SourceAction.REFRESH, SourceActionReason.AFFECTED
        elif source.freshness is DataFreshness.STALE:
            action, reason = SourceAction.REFRESH, SourceActionReason.STALE
        elif source.freshness is DataFreshness.UNKNOWN_VALIDITY:
            action, reason = SourceAction.REFRESH, SourceActionReason.UNKNOWN_VALIDITY
        else:
            action, reason = SourceAction.REUSE, SourceActionReason.UNAFFECTED_FRESH
        records.append(SourceActionRecord(source.source_id, action, source.freshness, reason))
    return tuple(records)


def classify_replan_impact(
    context: ReplanImpactContext,
    command: ReplanCommand,
    *,
    budget_effect: ReplanBudgetResult | None = None,
) -> ImpactAnalysis:
    if not isinstance(context, ReplanImpactContext):
        raise DomainInvariantError("impact_context_invalid", field="context")
    if not isinstance(
        command,
        ReplaceActivity | DeleteActivity | AdjustActivityTime | ReorderActivities,
    ):
        raise DomainInvariantError("replan_command_invalid", field="command")
    if budget_effect is not None and not isinstance(budget_effect, ReplanBudgetResult):
        raise DomainInvariantError("budget_effect_invalid", field="budget_effect")

    activities = {value.activity_id: value for value in context.activities}
    if isinstance(command, ReorderActivities):
        target_ids = command.ordered_activity_ids
        primary_date = command.local_date
        if primary_date not in context.travel_dates:
            raise DomainInvariantError("reorder_date_out_of_range", field="local_date")
        expected_ids = {
            value.activity_id for value in context.activities if value.local_date == primary_date
        }
        if set(target_ids) != expected_ids:
            raise DomainInvariantError(
                "reorder_activity_set_mismatch", field="ordered_activity_ids"
            )
    else:
        target_ids = (command.target_activity_id,)
        target = activities.get(command.target_activity_id)
        if target is None:
            raise DomainInvariantError("replan_target_not_found", field="target_activity_id")
        primary_date = target.local_date
    if set(target_ids) - activities.keys():
        raise DomainInvariantError("replan_target_not_found", field="target_activity_id")

    affected_activities = tuple(activities[value] for value in target_ids)
    affected_routes = tuple(
        route for route in context.routes if set(route.activity_ids) & set(target_ids)
    )
    affected_dates = tuple(
        sorted(
            {
                primary_date,
                *(value.local_date for value in affected_activities),
                *(value.local_date for value in affected_routes),
            }
        )
    )
    direct_refs = _sorted_uuids(target_ids)
    route_refs = _sorted_uuids(tuple(value.route_id for value in affected_routes))
    transitive = set(route_refs)

    categories: set[ImpactCategory] = set()
    if any(value.city_adcode != context.city_adcode for value in affected_activities):
        categories.add(ImpactCategory.CROSS_CITY)
    if any(value != primary_date for value in affected_dates):
        categories.update({ImpactCategory.ADJACENT_DAY, ImpactCategory.CROSS_DAY})
    if any(value.touches_accommodation for value in affected_routes):
        categories.add(ImpactCategory.ACCOMMODATION_EFFECT)
        transitive.update(context.accommodation_location_ids)
    if not context.dependencies_complete:
        categories.add(ImpactCategory.UNKNOWN_IMPACT)

    activity_source_ids = {
        source_id for value in affected_activities for source_id in value.source_ids
    }
    route_source_ids = {source_id for value in affected_routes for source_id in value.source_ids}
    dropped_source_ids: set[UUID] = set()
    force_refresh_ids: set[UUID] = set()
    if isinstance(command, ReplaceActivity | DeleteActivity):
        remaining_source_ids = {
            source_id
            for value in context.activities
            if value.activity_id not in set(target_ids)
            for source_id in value.source_ids
        }
        remaining_source_ids.update(
            source_id for value in context.routes for source_id in value.source_ids
        )
        dropped_source_ids.update(activity_source_ids - remaining_source_ids)
        force_refresh_ids.update(route_source_ids)
    elif isinstance(command, ReorderActivities):
        force_refresh_ids.update(route_source_ids)

    source_actions = plan_source_actions(
        context.sources,
        affected_source_ids=_sorted_uuids(tuple(force_refresh_ids)),
        dropped_source_ids=_sorted_uuids(tuple(dropped_source_ids)),
    )
    if isinstance(command, ReplaceActivity) or any(
        value.action is SourceAction.REFRESH for value in source_actions
    ):
        categories.add(ImpactCategory.SOURCE_REFRESH)

    if isinstance(command, ReplaceActivity) or (
        budget_effect is not None and budget_effect.risk_increased
    ):
        categories.add(ImpactCategory.BUDGET_RISK)

    validations = {"schedule", "constraints"}
    if affected_routes:
        validations.add("route")
    if any(value.touches_accommodation for value in affected_routes):
        validations.add("accommodation")
    if ImpactCategory.BUDGET_RISK in categories:
        validations.add("budget")
    if source_actions:
        validations.add("source")

    if ImpactCategory.CROSS_CITY in categories:
        disposition = ImpactDisposition.REJECT
    elif categories:
        disposition = ImpactDisposition.CONFIRM
    else:
        categories.add(ImpactCategory.SAME_DAY_LOW)
        disposition = ImpactDisposition.AUTO

    return ImpactAnalysis(
        categories=tuple(value for value in ImpactCategory if value in categories),
        disposition=disposition,
        direct_refs=direct_refs,
        transitive_refs=_sorted_uuids(tuple(transitive - set(direct_refs))),
        affected_dates=affected_dates,
        route_refs=route_refs,
        source_actions=source_actions,
        required_validations=tuple(sorted(validations)),
        confirmation_required=disposition is ImpactDisposition.CONFIRM,
    )


@dataclass(frozen=True, slots=True)
class ReplanBudgetResult:
    before: BudgetSummaryResult
    after: BudgetSummaryResult
    known_total_delta: Decimal
    unknown_count_delta: int
    risk_increased: bool

    def __post_init__(self) -> None:
        if not isinstance(self.before, BudgetSummaryResult) or not isinstance(
            self.after, BudgetSummaryResult
        ):
            raise DomainInvariantError("budget_summary_invalid", field="before")
        if not isinstance(self.known_total_delta, Decimal):
            raise DomainInvariantError("budget_delta_invalid", field="known_total_delta")
        if type(self.unknown_count_delta) is not int:
            raise DomainInvariantError("unknown_delta_invalid", field="unknown_count_delta")
        if type(self.risk_increased) is not bool:
            raise DomainInvariantError("budget_risk_invalid", field="risk_increased")


def recalculate_replan_budget(
    budget: Money,
    current_items: tuple[BudgetCostItem, ...],
    *,
    remove_cost_ids: tuple[UUID, ...] = (),
    replacement_items: tuple[BudgetCostItem, ...] = (),
) -> ReplanBudgetResult:
    _require_unique_uuid_tuple(remove_cost_ids, field="remove_cost_ids")
    if not isinstance(replacement_items, tuple) or not all(
        isinstance(value, BudgetCostItem) for value in replacement_items
    ):
        raise DomainInvariantError("replacement_cost_items_invalid", field="replacement_items")
    before = summarize_budget(budget, current_items)
    current_ids = {value.cost_id for value in current_items}
    if set(remove_cost_ids) - current_ids:
        raise DomainInvariantError("remove_cost_id_missing", field="remove_cost_ids")
    retained = tuple(value for value in current_items if value.cost_id not in remove_cost_ids)
    after = summarize_budget(budget, (*retained, *replacement_items))
    risk_increased = (
        after.assessment is BudgetAssessment.OVER_BUDGET
        or after.unknown_count > before.unknown_count
        or _assessment_rank(after.assessment) > _assessment_rank(before.assessment)
    )
    return ReplanBudgetResult(
        before=before,
        after=after,
        known_total_delta=after.known_total.amount - before.known_total.amount,
        unknown_count_delta=after.unknown_count - before.unknown_count,
        risk_increased=risk_increased,
    )


class ChangeEntityKind(StrEnum):
    ACTIVITY = "activity"
    ROUTE = "route"
    SCHEDULE = "schedule"
    COST = "cost"
    SOURCE = "source"


@dataclass(frozen=True, slots=True)
class PlanEntitySnapshot:
    ref_id: UUID
    kind: ChangeEntityKind
    fingerprint: str
    origin_ref_id: UUID | None = None

    def __post_init__(self) -> None:
        _require_uuid(self.ref_id, field="ref_id")
        if not isinstance(self.kind, ChangeEntityKind):
            raise DomainInvariantError("change_entity_kind_invalid", field="kind")
        if not isinstance(self.fingerprint, str) or _SHA256.fullmatch(self.fingerprint) is None:
            raise DomainInvariantError("change_fingerprint_invalid", field="fingerprint")
        if self.origin_ref_id is not None:
            _require_uuid(self.origin_ref_id, field="origin_ref_id")


@dataclass(frozen=True, slots=True)
class PlanChangeSet:
    baseline_plan_id: UUID
    result_plan_id: UUID
    added_refs: tuple[UUID, ...]
    removed_refs: tuple[UUID, ...]
    changed_refs: tuple[UUID, ...]
    added_origins: tuple[tuple[UUID, UUID], ...]
    change_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_uuid(self.baseline_plan_id, field="baseline_plan_id")
        _require_uuid(self.result_plan_id, field="result_plan_id")
        if self.baseline_plan_id == self.result_plan_id:
            raise DomainInvariantError("result_plan_id_unchanged", field="result_plan_id")
        for values, value_field in (
            (self.added_refs, "added_refs"),
            (self.removed_refs, "removed_refs"),
            (self.changed_refs, "changed_refs"),
        ):
            _require_unique_uuid_tuple(values, field=value_field)
        if (
            set(self.added_refs) & set(self.removed_refs)
            or set(self.added_refs) & set(self.changed_refs)
            or set(self.removed_refs) & set(self.changed_refs)
        ):
            raise DomainInvariantError("change_set_overlap", field="changed_refs")
        if not isinstance(self.added_origins, tuple) or any(
            not isinstance(value, tuple)
            or len(value) != 2
            or not all(isinstance(item, UUID) for item in value)
            for value in self.added_origins
        ):
            raise DomainInvariantError("added_origins_invalid", field="added_origins")
        if any(value[0] not in self.added_refs for value in self.added_origins):
            raise DomainInvariantError("added_origin_not_added", field="added_origins")
        if (
            not isinstance(self.change_codes, tuple)
            or any(_SAFE_CATEGORY.fullmatch(value) is None for value in self.change_codes)
            or len(set(self.change_codes)) != len(self.change_codes)
        ):
            raise DomainInvariantError("change_codes_invalid", field="change_codes")


def build_plan_change_set(
    baseline_plan_id: UUID,
    result_plan_id: UUID,
    before: tuple[PlanEntitySnapshot, ...],
    after: tuple[PlanEntitySnapshot, ...],
) -> PlanChangeSet:
    _require_uuid(baseline_plan_id, field="baseline_plan_id")
    _require_uuid(result_plan_id, field="result_plan_id")
    if baseline_plan_id == result_plan_id:
        raise DomainInvariantError("result_plan_id_unchanged", field="result_plan_id")
    _require_snapshot_collection(before, field="before")
    _require_snapshot_collection(after, field="after")
    before_map = {value.ref_id: value for value in before}
    after_map = {value.ref_id: value for value in after}
    added = set(after_map) - set(before_map)
    removed = set(before_map) - set(after_map)
    changed = {
        ref_id
        for ref_id in set(before_map) & set(after_map)
        if before_map[ref_id].kind is not after_map[ref_id].kind
        or before_map[ref_id].fingerprint != after_map[ref_id].fingerprint
    }
    changed_kinds = {
        *(after_map[value].kind for value in added | changed),
        *(before_map[value].kind for value in removed),
    }
    origin_pairs: list[tuple[UUID, UUID]] = []
    for ref_id in added:
        origin_ref_id = after_map[ref_id].origin_ref_id
        if origin_ref_id is not None:
            origin_pairs.append((ref_id, origin_ref_id))
    added_origins = tuple(sorted(origin_pairs, key=lambda value: value[0].hex))
    return PlanChangeSet(
        baseline_plan_id=baseline_plan_id,
        result_plan_id=result_plan_id,
        added_refs=_sorted_uuids(tuple(added)),
        removed_refs=_sorted_uuids(tuple(removed)),
        changed_refs=_sorted_uuids(tuple(changed)),
        added_origins=added_origins,
        change_codes=tuple(sorted(value.value for value in changed_kinds)),
    )


def validate_change_set_scope(
    change_set: PlanChangeSet,
    *,
    allowed_refs: tuple[UUID, ...],
) -> None:
    if not isinstance(change_set, PlanChangeSet):
        raise DomainInvariantError("change_set_invalid", field="change_set")
    _require_unique_uuid_tuple(allowed_refs, field="allowed_refs")
    allowed = set(allowed_refs)
    if (set(change_set.removed_refs) | set(change_set.changed_refs)) - allowed:
        raise DomainInvariantError("change_set_scope_exceeded", field="changed_refs")
    origins = dict(change_set.added_origins)
    if any(origins.get(value) not in allowed for value in change_set.added_refs):
        raise DomainInvariantError("change_set_scope_exceeded", field="added_refs")


def _require_snapshot_collection(values: tuple[PlanEntitySnapshot, ...], *, field: str) -> None:
    if not isinstance(values, tuple) or not all(
        isinstance(value, PlanEntitySnapshot) for value in values
    ):
        raise DomainInvariantError("change_snapshot_invalid", field=field)
    ids = tuple(value.ref_id for value in values)
    _require_no_duplicates(ids, code="change_snapshot_duplicate", field=field)


def _assessment_rank(value: BudgetAssessment) -> int:
    return {
        BudgetAssessment.WITHIN_BUDGET: 0,
        BudgetAssessment.INDETERMINATE: 1,
        BudgetAssessment.OVER_BUDGET: 2,
    }[value]


def _require_reason_code(value: str | None) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or _SAFE_CODE.fullmatch(value) is None
        or _UNSAFE_TEXT.search(value) is not None
    ):
        raise DomainInvariantError("reason_code_invalid", field="reason_code")


def _require_uuid(value: object, *, field: str) -> None:
    if not isinstance(value, UUID):
        code = "activity_id_invalid" if field == "target_activity_id" else "identifier_invalid"
        raise DomainInvariantError(code, field=field)


def _require_unique_uuid_tuple(values: tuple[UUID, ...], *, field: str) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, UUID) for value in values):
        raise DomainInvariantError("identifier_collection_invalid", field=field)
    _require_no_duplicates(values, code="duplicate_reference_id", field=field)


def _require_no_duplicates[T](values: tuple[T, ...], *, code: str, field: str) -> None:
    if len(set(values)) != len(values):
        raise DomainInvariantError(code, field=field)


def _sorted_uuids(values: tuple[UUID, ...]) -> tuple[UUID, ...]:
    return tuple(sorted(values, key=lambda value: value.hex))
