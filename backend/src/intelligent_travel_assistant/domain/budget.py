"""Pure CNY budget aggregation with explicit unknown-cost semantics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from intelligent_travel_assistant.domain.foundation import (
    CostConfidence,
    DomainInvariantError,
    Money,
)


class CostCategory(StrEnum):
    ACCOMMODATION = "accommodation"
    INTERCITY_TRANSPORT = "intercity_transport"
    LOCAL_TRANSPORT = "local_transport"
    TICKET = "ticket"
    MEAL = "meal"
    OTHER = "other"


class BudgetAssessment(StrEnum):
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"
    INDETERMINATE = "budget_indeterminate"


@dataclass(frozen=True, slots=True)
class BudgetCostItem:
    cost_id: UUID
    category: CostCategory
    confidence: CostConfidence
    amount: Money | None
    source_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.cost_id, UUID):
            raise DomainInvariantError("cost_id_invalid", field="cost_id")
        if not isinstance(self.category, CostCategory):
            raise DomainInvariantError("cost_category_invalid", field="category")
        if not isinstance(self.confidence, CostConfidence):
            raise DomainInvariantError("cost_confidence_invalid", field="confidence")
        if not isinstance(self.source_ids, tuple) or not all(
            isinstance(item, UUID) for item in self.source_ids
        ):
            raise DomainInvariantError("source_ids_invalid", field="source_ids")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise DomainInvariantError("duplicate_reference_id", field="source_ids")
        if self.confidence is CostConfidence.UNKNOWN:
            if self.amount is not None:
                raise DomainInvariantError("unknown_cost_has_amount", field="amount")
        elif not isinstance(self.amount, Money):
            raise DomainInvariantError("known_cost_missing_amount", field="amount")
        if self.confidence is CostConfidence.VERIFIED and not self.source_ids:
            raise DomainInvariantError("verified_cost_missing_source", field="source_ids")


@dataclass(frozen=True, slots=True)
class BudgetSummaryResult:
    budget: Money
    known_total: Money
    unknown_count: int
    assessment: BudgetAssessment
    cost_items: tuple[BudgetCostItem, ...]


def summarize_budget(
    budget: Money,
    cost_items: tuple[BudgetCostItem, ...],
) -> BudgetSummaryResult:
    if not isinstance(budget, Money):
        raise DomainInvariantError("budget_invalid", field="budget")
    if not isinstance(cost_items, tuple) or not all(
        isinstance(item, BudgetCostItem) for item in cost_items
    ):
        raise DomainInvariantError("cost_items_invalid", field="cost_items")
    if len({item.cost_id for item in cost_items}) != len(cost_items):
        raise DomainInvariantError("duplicate_cost_id", field="cost_items")

    known_minor_units = 0
    unknown_count = 0
    for item in cost_items:
        if item.confidence is CostConfidence.UNKNOWN:
            unknown_count += 1
        else:
            assert item.amount is not None
            known_minor_units += _to_minor_units(item.amount)

    known_total = _from_minor_units(known_minor_units)
    if known_total.amount > budget.amount:
        assessment = BudgetAssessment.OVER_BUDGET
    elif unknown_count:
        assessment = BudgetAssessment.INDETERMINATE
    else:
        assessment = BudgetAssessment.WITHIN_BUDGET

    return BudgetSummaryResult(
        budget=budget,
        known_total=known_total,
        unknown_count=unknown_count,
        assessment=assessment,
        cost_items=cost_items,
    )


def calculate_multiday_meal_cost(
    per_person_per_day: Money | None,
    travelers: int,
    day_count: int,
) -> Money | None:
    """Scale an allowlisted known meal amount while preserving unknown as ``None``."""

    _require_travelers(travelers)
    _require_day_count(day_count)
    if per_person_per_day is None:
        return None
    if not isinstance(per_person_per_day, Money):
        raise DomainInvariantError("meal_cost_invalid", field="per_person_per_day")
    return _from_minor_units(_to_minor_units(per_person_per_day) * travelers * day_count)


def calculate_multiday_lodging_cost(
    per_night: Money | None,
    day_count: int,
) -> Money | None:
    """Scale one-night lodging across D-1 nights without manufacturing unknown data."""

    _require_day_count(day_count)
    if per_night is None:
        return None
    if not isinstance(per_night, Money):
        raise DomainInvariantError("lodging_cost_invalid", field="per_night")
    return _from_minor_units(_to_minor_units(per_night) * (day_count - 1))


def _require_travelers(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 8:
        raise DomainInvariantError("travelers_invalid", field="travelers")


def _require_day_count(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not 2 <= value <= 7:
        raise DomainInvariantError("trip_day_count_invalid", field="day_count")


def _to_minor_units(value: Money) -> int:
    exponent = value.amount.as_tuple().exponent
    if not isinstance(exponent, int):
        raise DomainInvariantError("money_not_finite", field="amount")
    exponent_value = int(exponent)
    digits = 0
    for raw_digit in value.amount.as_tuple().digits:
        digit = int(raw_digit)
        digits = digits * 10 + digit
    scale = exponent_value + 2
    if scale < 0:
        raise DomainInvariantError("money_precision_invalid", field="amount")
    return int(digits * (10**scale))


def _from_minor_units(value: int) -> Money:
    return Money(Decimal(value).scaleb(-2))
