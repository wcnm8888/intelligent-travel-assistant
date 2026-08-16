"""F-003 budget recomputation and source reuse/refresh/drop policy."""

from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    BudgetAssessment,
    BudgetCostItem,
    CostCategory,
    CostConfidence,
    DataFreshness,
    DomainInvariantError,
    Money,
    ReplanSourceState,
    SourceAction,
    plan_source_actions,
    recalculate_replan_budget,
)

S1 = UUID("34000000-0000-4000-8000-000000000001")
S2 = UUID("34000000-0000-4000-8000-000000000002")
C1 = UUID("34000000-0000-4000-8000-000000000011")
C2 = UUID("34000000-0000-4000-8000-000000000012")
C3 = UUID("34000000-0000-4000-8000-000000000013")


def item(
    cost_id: UUID,
    confidence: CostConfidence,
    amount: str | None,
) -> BudgetCostItem:
    return BudgetCostItem(
        cost_id,
        CostCategory.TICKET,
        confidence,
        Money(Decimal(amount)) if amount is not None else None,
        (S1,) if confidence is CostConfidence.VERIFIED else (),
    )


def test_budget_recalculation_preserves_unknown_null_and_marks_new_risk() -> None:
    result = recalculate_replan_budget(
        Money(Decimal("100.00")),
        (item(C1, CostConfidence.ESTIMATED, "50.00"),),
        remove_cost_ids=(),
        replacement_items=(item(C2, CostConfidence.UNKNOWN, None),),
    )

    assert result.after.known_total.amount == Decimal("50.00")
    assert result.after.unknown_count == 1
    assert result.after.cost_items[-1].amount is None
    assert result.after.assessment is BudgetAssessment.INDETERMINATE
    assert result.risk_increased is True


def test_removing_unknown_cost_reduces_risk_without_creating_zero() -> None:
    unknown = item(C1, CostConfidence.UNKNOWN, None)
    known = item(C2, CostConfidence.ESTIMATED, "20.00")
    result = recalculate_replan_budget(
        Money(Decimal("100.00")),
        (unknown, known),
        remove_cost_ids=(C1,),
    )

    assert result.after.unknown_count == 0
    assert result.after.known_total.amount == Decimal("20.00")
    assert all(cost.cost_id != C1 for cost in result.after.cost_items)
    assert result.risk_increased is False


def test_known_over_budget_is_always_a_budget_risk() -> None:
    result = recalculate_replan_budget(
        Money(Decimal("100.00")),
        (item(C1, CostConfidence.ESTIMATED, "90.00"),),
        replacement_items=(item(C2, CostConfidence.ESTIMATED, "20.01"),),
    )
    assert result.after.assessment is BudgetAssessment.OVER_BUDGET
    assert result.risk_increased is True


def test_source_policy_never_promotes_freshness() -> None:
    actions = plan_source_actions(
        (
            ReplanSourceState(S1, DataFreshness.FRESH, required=True),
            ReplanSourceState(S2, DataFreshness.UNKNOWN_VALIDITY, required=True),
        ),
        affected_source_ids=(),
        dropped_source_ids=(),
    )
    assert actions[0].action is SourceAction.REUSE
    assert actions[0].freshness is DataFreshness.FRESH
    assert actions[1].action is SourceAction.REFRESH
    assert actions[1].freshness is DataFreshness.UNKNOWN_VALIDITY


def test_source_cannot_be_both_dropped_and_refreshed() -> None:
    with pytest.raises(DomainInvariantError) as error:
        plan_source_actions(
            (ReplanSourceState(S1, DataFreshness.STALE, required=True),),
            affected_source_ids=(S1,),
            dropped_source_ids=(S1,),
        )
    assert error.value.code == "source_action_overlap"


def test_unrequired_source_is_not_reused() -> None:
    actions = plan_source_actions(
        (ReplanSourceState(S2, DataFreshness.FRESH, required=False),),
        affected_source_ids=(),
        dropped_source_ids=(),
    )
    assert actions[0].action is SourceAction.DROP
