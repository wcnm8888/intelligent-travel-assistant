"""F-003 typed local-replanning command invariants."""

from dataclasses import FrozenInstanceError
from datetime import date, time
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DeleteActivity,
    DomainInvariantError,
    ReorderActivities,
    ReplaceActivity,
    ReplanOperation,
)

ACTIVITY_1 = UUID("31000000-0000-4000-8000-000000000001")
ACTIVITY_2 = UUID("31000000-0000-4000-8000-000000000002")


def test_four_commands_are_frozen_typed_values() -> None:
    replace = ReplaceActivity(
        target_activity_id=ACTIVITY_1,
        replacement_categories=("museum", "history"),
        reason_code="user.preference",
    )
    delete = DeleteActivity(target_activity_id=ACTIVITY_1)
    adjust = AdjustActivityTime(
        target_activity_id=ACTIVITY_1,
        start_time=time(10),
        end_time=time(12),
    )
    reorder = ReorderActivities(
        local_date=date(2026, 8, 20),
        ordered_activity_ids=(ACTIVITY_2, ACTIVITY_1),
    )

    assert replace.operation is ReplanOperation.REPLACE_ACTIVITY
    assert delete.operation is ReplanOperation.DELETE_ACTIVITY
    assert adjust.operation is ReplanOperation.ADJUST_ACTIVITY_TIME
    assert reorder.operation is ReplanOperation.REORDER_ACTIVITIES
    with pytest.raises(FrozenInstanceError):
        replace.target_activity_id = ACTIVITY_2  # type: ignore[misc]
    assert not hasattr(replace, "__dict__")


@pytest.mark.parametrize(
    "categories",
    [(), ("museum",) * 4, ("Museum",), ("provider:id",), ("",)],
)
def test_replace_rejects_unbounded_or_unsafe_categories(
    categories: tuple[str, ...],
) -> None:
    with pytest.raises(DomainInvariantError) as error:
        ReplaceActivity(
            target_activity_id=ACTIVITY_1,
            replacement_categories=categories,
        )
    assert error.value.code == "replacement_categories_invalid"


@pytest.mark.parametrize(
    "reason_code",
    ["free text is not retained", "Authorization: bearer", "token=value", "UPPER"],
)
def test_commands_reject_free_text_or_sensitive_reason_codes(reason_code: str) -> None:
    with pytest.raises(DomainInvariantError) as error:
        DeleteActivity(target_activity_id=ACTIVITY_1, reason_code=reason_code)
    assert error.value.code == "reason_code_invalid"


def test_adjust_time_requires_a_positive_local_interval() -> None:
    with pytest.raises(DomainInvariantError) as error:
        AdjustActivityTime(
            target_activity_id=ACTIVITY_1,
            start_time=time(12),
            end_time=time(12),
        )
    assert error.value.code == "activity_time_range_invalid"


def test_reorder_requires_a_complete_non_duplicate_sequence_shape() -> None:
    with pytest.raises(DomainInvariantError) as error:
        ReorderActivities(
            local_date=date(2026, 8, 20),
            ordered_activity_ids=(ACTIVITY_1, ACTIVITY_1),
        )
    assert error.value.code == "ordered_activity_ids_duplicate"

    with pytest.raises(DomainInvariantError) as error:
        ReorderActivities(local_date=date(2026, 8, 20), ordered_activity_ids=())
    assert error.value.code == "ordered_activity_ids_empty"


def test_identifiers_and_enum_fields_are_runtime_checked() -> None:
    with pytest.raises(DomainInvariantError) as error:
        DeleteActivity(target_activity_id="not-a-uuid")  # type: ignore[arg-type]
    assert error.value.code == "activity_id_invalid"
