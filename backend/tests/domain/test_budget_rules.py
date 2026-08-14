"""F-001 Decimal budget aggregation and unknown-cost rules."""

import json
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.contracts import TripPlanResponse
from intelligent_travel_assistant.domain import (
    BudgetAssessment,
    BudgetCostItem,
    BudgetSummaryResult,
    CostCategory,
    CostConfidence,
    DomainInvariantError,
    Money,
    summarize_budget,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"
SOURCE_ID = UUID("20000000-0000-4000-8000-000000000001")


def cost(
    sequence: int,
    category: CostCategory,
    confidence: CostConfidence,
    amount: str | None,
) -> BudgetCostItem:
    return BudgetCostItem(
        cost_id=UUID(f"93000000-0000-4000-8000-{sequence:012d}"),
        category=category,
        confidence=confidence,
        amount=Money(Decimal(amount)) if amount is not None else None,
        source_ids=(SOURCE_ID,) if confidence is CostConfidence.VERIFIED else (),
    )


def summarize(
    budget: str,
    items: tuple[BudgetCostItem, ...],
) -> BudgetSummaryResult:
    return summarize_budget(Money(Decimal(budget)), items)


def test_zero_costs_are_known_and_do_not_become_unknown() -> None:
    result = summarize(
        "0.00",
        (cost(1, CostCategory.TICKET, CostConfidence.ESTIMATED, "0.00"),),
    )

    assert result.known_total == Money(Decimal("0.00"))
    assert result.unknown_count == 0
    assert result.assessment is BudgetAssessment.WITHIN_BUDGET


@pytest.mark.parametrize(
    ("known_amount", "expected"),
    [
        ("99.99", BudgetAssessment.WITHIN_BUDGET),
        ("100.00", BudgetAssessment.WITHIN_BUDGET),
        ("100.01", BudgetAssessment.OVER_BUDGET),
    ],
)
def test_one_cent_and_exact_budget_boundaries(
    known_amount: str, expected: BudgetAssessment
) -> None:
    result = summarize(
        "100.00",
        (cost(1, CostCategory.MEAL, CostConfidence.ESTIMATED, known_amount),),
    )
    assert result.assessment is expected


def test_unknown_cost_is_counted_without_changing_known_total() -> None:
    known = cost(1, CostCategory.ACCOMMODATION, CostConfidence.USER_PROVIDED, "80.00")
    unknown = cost(2, CostCategory.TICKET, CostConfidence.UNKNOWN, None)

    result = summarize("100.00", (known, unknown))

    assert result.known_total == Money(Decimal("80.00"))
    assert result.unknown_count == 1
    assert result.assessment is BudgetAssessment.INDETERMINATE
    assert result.cost_items == (known, unknown)


def test_unknown_never_downgrades_known_over_budget_result() -> None:
    result = summarize(
        "100.00",
        (
            cost(1, CostCategory.MEAL, CostConfidence.ESTIMATED, "100.01"),
            cost(2, CostCategory.TICKET, CostConfidence.UNKNOWN, None),
        ),
    )

    assert result.unknown_count == 1
    assert result.assessment is BudgetAssessment.OVER_BUDGET


def test_unknown_keeps_an_exact_known_budget_indeterminate() -> None:
    result = summarize(
        "100.00",
        (
            cost(1, CostCategory.MEAL, CostConfidence.ESTIMATED, "100.00"),
            cost(2, CostCategory.TICKET, CostConfidence.UNKNOWN, None),
        ),
    )
    assert result.known_total.amount == Decimal("100.00")
    assert result.assessment is BudgetAssessment.INDETERMINATE


def test_empty_cost_collection_is_a_known_zero_total() -> None:
    result = summarize("100.00", ())
    assert result.known_total == Money(Decimal("0.00"))
    assert result.assessment is BudgetAssessment.WITHIN_BUDGET


def test_all_approved_categories_and_confidences_aggregate_as_decimal() -> None:
    items = (
        cost(1, CostCategory.ACCOMMODATION, CostConfidence.USER_PROVIDED, "700.00"),
        cost(2, CostCategory.INTERCITY_TRANSPORT, CostConfidence.USER_PROVIDED, "1000.00"),
        cost(3, CostCategory.LOCAL_TRANSPORT, CostConfidence.ESTIMATED, "40.00"),
        cost(4, CostCategory.TICKET, CostConfidence.VERIFIED, "0.00"),
        cost(5, CostCategory.MEAL, CostConfidence.ESTIMATED, "400.00"),
        cost(6, CostCategory.OTHER, CostConfidence.UNKNOWN, None),
    )
    result = summarize("4000.00", items)

    assert result.known_total.amount == Decimal("2140.00")
    assert result.unknown_count == 1
    assert result.assessment is BudgetAssessment.INDETERMINATE


def test_duplicate_cost_ids_are_rejected() -> None:
    item = cost(1, CostCategory.MEAL, CostConfidence.ESTIMATED, "100.00")
    with pytest.raises(DomainInvariantError) as error:
        summarize("1000.00", (item, item))

    assert error.value.code == "duplicate_cost_id"
    assert error.value.field == "cost_items"


def test_budget_cost_item_enforces_truth_state_and_verified_source_rules() -> None:
    with pytest.raises(DomainInvariantError) as error:
        BudgetCostItem(
            cost_id=UUID("93000000-0000-4000-8000-000000000001"),
            category=CostCategory.TICKET,
            confidence=CostConfidence.UNKNOWN,
            amount=Money(Decimal("0.00")),
        )
    assert error.value.code == "unknown_cost_has_amount"

    with pytest.raises(DomainInvariantError) as error:
        BudgetCostItem(
            cost_id=UUID("93000000-0000-4000-8000-000000000002"),
            category=CostCategory.MEAL,
            confidence=CostConfidence.ESTIMATED,
            amount=None,
        )
    assert error.value.code == "known_cost_missing_amount"

    with pytest.raises(DomainInvariantError) as error:
        BudgetCostItem(
            cost_id=UUID("93000000-0000-4000-8000-000000000003"),
            category=CostCategory.TICKET,
            confidence=CostConfidence.VERIFIED,
            amount=Money(Decimal("10.00")),
            source_ids=(),
        )
    assert error.value.code == "verified_cost_missing_source"


def test_budget_summary_rejects_non_tuple_or_wrong_item_types() -> None:
    with pytest.raises(DomainInvariantError) as error:
        summarize_budget(Money(Decimal("100.00")), [])  # type: ignore[arg-type]
    assert error.value.code == "cost_items_invalid"

    with pytest.raises(DomainInvariantError):
        summarize_budget(Money(Decimal("100.00")), ("not-a-cost",))  # type: ignore[arg-type]


def test_minor_unit_aggregation_is_not_rounded_by_global_decimal_context() -> None:
    with localcontext() as context:
        context.prec = 3
        result = summarize(
            "100000000000000000000.00",
            (
                cost(
                    1,
                    CostCategory.ACCOMMODATION,
                    CostConfidence.USER_PROVIDED,
                    "99999999999999999999.99",
                ),
                cost(2, CostCategory.MEAL, CostConfidence.ESTIMATED, "0.01"),
            ),
        )

    assert result.known_total.amount == Decimal("100000000000000000000.00")
    assert result.assessment is BudgetAssessment.WITHIN_BUDGET


def confidence_from_contract(value: object) -> CostConfidence:
    return CostConfidence(str(value))


def category_from_contract(value: object) -> CostCategory:
    return CostCategory(str(value))


@pytest.mark.parametrize(
    ("fixture_name", "expected_assessment"),
    [
        ("synthetic_hangzhou_ready.json", BudgetAssessment.WITHIN_BUDGET),
        ("synthetic_hangzhou_partial.json", BudgetAssessment.INDETERMINATE),
        ("synthetic_hangzhou_conflict.json", BudgetAssessment.OVER_BUDGET),
    ],
)
def test_synthetic_budget_summaries_are_recomputed_without_drift(
    fixture_name: str, expected_assessment: BudgetAssessment
) -> None:
    fixture = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
    response = TripPlanResponse.model_validate(fixture["response"])
    assert response.plan is not None
    contract_summary = response.plan.budget_summary
    items = tuple(
        BudgetCostItem(
            cost_id=item.cost_id,
            category=category_from_contract(item.category),
            confidence=confidence_from_contract(item.confidence),
            amount=Money(item.amount.amount) if item.amount is not None else None,
            source_ids=item.source_ids,
        )
        for item in contract_summary.cost_items
    )

    result = summarize_budget(Money(contract_summary.budget.amount), items)

    assert result.known_total.amount == contract_summary.known_total.amount
    assert result.unknown_count == contract_summary.unknown_count
    assert result.assessment.value == contract_summary.assessment.value
    assert result.assessment is expected_assessment
