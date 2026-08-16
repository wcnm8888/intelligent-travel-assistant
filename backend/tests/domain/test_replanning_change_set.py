"""F-003 baseline-to-result typed change-set rules."""

from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    ChangeEntityKind,
    DomainInvariantError,
    PlanChangeSet,
    PlanEntitySnapshot,
    build_plan_change_set,
    validate_change_set_scope,
)

BASELINE = UUID("33000000-0000-4000-8000-000000000001")
RESULT = UUID("33000000-0000-4000-8000-000000000002")
A1 = UUID("33000000-0000-4000-8000-000000000011")
A2 = UUID("33000000-0000-4000-8000-000000000012")
A3 = UUID("33000000-0000-4000-8000-000000000013")
R1 = UUID("33000000-0000-4000-8000-000000000021")


def snapshot(
    ref_id: UUID,
    kind: ChangeEntityKind,
    fingerprint: str,
    *,
    origin_ref_id: UUID | None = None,
) -> PlanEntitySnapshot:
    return PlanEntitySnapshot(ref_id, kind, fingerprint, origin_ref_id)


def test_change_set_reports_added_removed_changed_and_codes() -> None:
    before = (
        snapshot(A1, ChangeEntityKind.ACTIVITY, "a" * 64),
        snapshot(A2, ChangeEntityKind.ACTIVITY, "b" * 64),
        snapshot(R1, ChangeEntityKind.ROUTE, "c" * 64),
    )
    after = (
        snapshot(A2, ChangeEntityKind.ACTIVITY, "d" * 64),
        snapshot(A3, ChangeEntityKind.ACTIVITY, "e" * 64, origin_ref_id=A1),
        snapshot(R1, ChangeEntityKind.ROUTE, "c" * 64),
    )

    result = build_plan_change_set(BASELINE, RESULT, before, after)

    assert result.added_refs == (A3,)
    assert result.removed_refs == (A1,)
    assert result.changed_refs == (A2,)
    assert result.change_codes == ("activity",)
    assert result.added_origins == ((A3, A1),)


def test_change_set_scope_accepts_replacement_origin_and_rejects_silent_changes() -> None:
    allowed = (A1,)
    valid = build_plan_change_set(
        BASELINE,
        RESULT,
        (snapshot(A1, ChangeEntityKind.ACTIVITY, "a" * 64),),
        (snapshot(A3, ChangeEntityKind.ACTIVITY, "b" * 64, origin_ref_id=A1),),
    )
    validate_change_set_scope(valid, allowed_refs=allowed)

    invalid = build_plan_change_set(
        BASELINE,
        RESULT,
        (snapshot(A1, ChangeEntityKind.ACTIVITY, "a" * 64),),
        (
            snapshot(A1, ChangeEntityKind.ACTIVITY, "a" * 64),
            snapshot(A2, ChangeEntityKind.ACTIVITY, "b" * 64),
        ),
    )
    with pytest.raises(DomainInvariantError) as error:
        validate_change_set_scope(invalid, allowed_refs=allowed)
    assert error.value.code == "change_set_scope_exceeded"


def test_duplicate_refs_and_same_plan_id_are_rejected() -> None:
    item = snapshot(A1, ChangeEntityKind.ACTIVITY, "a" * 64)
    with pytest.raises(DomainInvariantError) as error:
        build_plan_change_set(BASELINE, RESULT, (item, item), ())
    assert error.value.code == "change_snapshot_duplicate"

    with pytest.raises(DomainInvariantError) as error:
        build_plan_change_set(BASELINE, BASELINE, (), ())
    assert error.value.code == "result_plan_id_unchanged"


def test_fingerprint_must_be_a_lowercase_sha256_digest() -> None:
    with pytest.raises(DomainInvariantError) as error:
        snapshot(A1, ChangeEntityKind.ACTIVITY, "raw payload")
    assert error.value.code == "change_fingerprint_invalid"


def test_change_set_value_rejects_overlapping_fact_buckets() -> None:
    with pytest.raises(DomainInvariantError) as error:
        PlanChangeSet(
            baseline_plan_id=BASELINE,
            result_plan_id=RESULT,
            added_refs=(A1,),
            removed_refs=(A1,),
            changed_refs=(),
            added_origins=(),
            change_codes=("activity",),
        )
    assert error.value.code == "change_set_overlap"
