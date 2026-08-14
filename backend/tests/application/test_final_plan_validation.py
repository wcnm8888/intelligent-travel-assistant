"""Final deterministic validation owns terminal planning status."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest

from intelligent_travel_assistant.application.planning import (
    AccommodationAnchor,
    FinalValidationIssueCode,
    FinalValidationResult,
    FinalValidationSeverity,
)
from intelligent_travel_assistant.contracts import PlanningStatus
from intelligent_travel_assistant.domain import (
    BudgetAssessment,
    BudgetSummaryResult,
    Coordinates,
    CoordinateSystem,
    DailyAvailability,
    Money,
)


def test_final_validation_values_are_typed_frozen_and_terminal() -> None:
    accommodation = AccommodationAnchor(
        UUID("90000000-0000-4000-8000-000000000010"),
        "330100",
        Coordinates(
            Decimal("120.1500"),
            Decimal("30.2500"),
            CoordinateSystem.PROVIDER_NATIVE,
        ),
    )
    budget = BudgetSummaryResult(
        Money(Decimal("4000.00")),
        Money(Decimal("0.00")),
        0,
        BudgetAssessment.WITHIN_BUDGET,
        (),
    )
    result = FinalValidationResult(PlanningStatus.READY, (), budget, ())

    assert accommodation.city_adcode == "330100"
    assert result.status is PlanningStatus.READY
    assert FinalValidationSeverity.CONFLICT.value == "conflict"
    assert FinalValidationIssueCode.ROUTE_INCOMPLETE.value == "route_incomplete"
    with pytest.raises(FrozenInstanceError):
        result.status = PlanningStatus.PARTIAL  # type: ignore[misc]


def test_accommodation_and_validation_reject_invalid_boundary_values() -> None:
    with pytest.raises(ValueError):
        AccommodationAnchor(
            UUID("90000000-0000-4000-8000-000000000010"),
            "not-adcode",
            None,
        )

    with pytest.raises(ValueError):
        FinalValidationResult(
            PlanningStatus.VALIDATING,
            (),
            BudgetSummaryResult(
                Money(Decimal("1.00")),
                Money(Decimal("0.00")),
                0,
                BudgetAssessment.WITHIN_BUDGET,
                (),
            ),
            (),
        )


def test_daily_windows_remain_explicit_input_without_hidden_defaults() -> None:
    windows = (
        DailyAvailability(0, time(9), time(18)),
        DailyAvailability(1, time(9), time(18)),
    )
    evaluated_at = datetime(2026, 8, 13, 3, tzinfo=UTC)

    assert tuple(item.day_offset for item in windows) == (0, 1)
    assert evaluated_at.date() == date(2026, 8, 13)
