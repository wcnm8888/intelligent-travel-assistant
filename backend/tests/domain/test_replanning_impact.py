"""F-003 deterministic impact classification and confirmation boundary."""

from datetime import date, time
from uuid import UUID

import pytest

from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DataFreshness,
    DeleteActivity,
    DomainInvariantError,
    ImpactActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    ImpactRoute,
    ReorderActivities,
    ReplaceActivity,
    ReplanImpactContext,
    ReplanSourceState,
    SourceAction,
    classify_replan_impact,
)

DAY_1 = date(2026, 8, 20)
DAY_2 = date(2026, 8, 21)
PLAN_ID = UUID("32000000-0000-4000-8000-000000000001")
ACCOMMODATION = UUID("32000000-0000-4000-8000-000000000002")
A1 = UUID("32000000-0000-4000-8000-000000000011")
A2 = UUID("32000000-0000-4000-8000-000000000012")
A3 = UUID("32000000-0000-4000-8000-000000000013")
R1 = UUID("32000000-0000-4000-8000-000000000021")
R2 = UUID("32000000-0000-4000-8000-000000000022")
S1 = UUID("32000000-0000-4000-8000-000000000031")
S2 = UUID("32000000-0000-4000-8000-000000000032")


def context(
    *,
    first_route_touches_accommodation: bool = False,
    freshness: DataFreshness = DataFreshness.FRESH,
    dependencies_complete: bool = True,
    second_city: str = "330100",
    cross_day_dependency: bool = False,
) -> ReplanImpactContext:
    return ReplanImpactContext(
        plan_id=PLAN_ID,
        city_adcode="330100",
        travel_dates=(DAY_1, DAY_2),
        accommodation_location_ids=(ACCOMMODATION,),
        activities=(
            ImpactActivity(A1, DAY_1, "330100", (S1,)),
            ImpactActivity(A2, DAY_1, second_city, (S2,)),
            ImpactActivity(A3, DAY_2, "330100", (S2,)),
        ),
        routes=(
            ImpactRoute(
                R1,
                DAY_1,
                (A1, A2),
                (S2,),
                touches_accommodation=first_route_touches_accommodation,
            ),
            ImpactRoute(R2, DAY_2, (A3, A1) if cross_day_dependency else (A3,), (S2,)),
        ),
        sources=(
            ReplanSourceState(S1, freshness, required=True),
            ReplanSourceState(S2, DataFreshness.FRESH, required=True),
        ),
        dependencies_complete=dependencies_complete,
    )


def test_inner_same_day_time_change_is_the_only_auto_classification() -> None:
    analysis = classify_replan_impact(
        context(),
        AdjustActivityTime(A1, start_time=time(10), end_time=time(11)),
    )

    assert analysis.categories == (ImpactCategory.SAME_DAY_LOW,)
    assert analysis.disposition is ImpactDisposition.AUTO
    assert analysis.confirmation_required is False
    assert analysis.direct_refs == (A1,)
    assert analysis.route_refs == (R1,)
    assert "schedule" in analysis.required_validations


def test_accommodation_dependency_forces_confirmation() -> None:
    analysis = classify_replan_impact(
        context(first_route_touches_accommodation=True),
        AdjustActivityTime(A1, start_time=time(10), end_time=time(11)),
    )

    assert ImpactCategory.SAME_DAY_LOW not in analysis.categories
    assert ImpactCategory.ACCOMMODATION_EFFECT in analysis.categories
    assert analysis.disposition is ImpactDisposition.CONFIRM
    assert ACCOMMODATION in analysis.transitive_refs


def test_replace_requires_budget_and_source_confirmation() -> None:
    analysis = classify_replan_impact(
        context(),
        ReplaceActivity(A1, replacement_categories=("museum",)),
    )

    assert analysis.disposition is ImpactDisposition.CONFIRM
    assert ImpactCategory.BUDGET_RISK in analysis.categories
    assert ImpactCategory.SOURCE_REFRESH in analysis.categories
    assert {item.action for item in analysis.source_actions} >= {
        SourceAction.DROP,
        SourceAction.REFRESH,
    }


def test_shared_activity_source_is_not_dropped_from_the_result() -> None:
    shared = ReplanImpactContext(
        plan_id=PLAN_ID,
        city_adcode="330100",
        travel_dates=(DAY_1, DAY_2),
        accommodation_location_ids=(ACCOMMODATION,),
        activities=(
            ImpactActivity(A1, DAY_1, "330100", (S1,)),
            ImpactActivity(A2, DAY_1, "330100", (S1,)),
            ImpactActivity(A3, DAY_2, "330100", (S2,)),
        ),
        routes=(),
        sources=(
            ReplanSourceState(S1, DataFreshness.FRESH, required=True),
            ReplanSourceState(S2, DataFreshness.FRESH, required=True),
        ),
    )
    analysis = classify_replan_impact(
        shared,
        ReplaceActivity(A1, replacement_categories=("museum",)),
    )
    source_one = next(value for value in analysis.source_actions if value.source_id == S1)
    assert source_one.action is SourceAction.REUSE
    assert ImpactCategory.SOURCE_REFRESH in analysis.categories


def test_cross_day_transitive_dependency_requires_confirmation() -> None:
    analysis = classify_replan_impact(
        context(cross_day_dependency=True),
        AdjustActivityTime(A1, start_time=time(10), end_time=time(11)),
    )

    assert ImpactCategory.ADJACENT_DAY in analysis.categories
    assert ImpactCategory.CROSS_DAY in analysis.categories
    assert analysis.affected_dates == (DAY_1, DAY_2)
    assert analysis.disposition is ImpactDisposition.CONFIRM


def test_reorder_must_match_the_complete_activity_set_for_one_day() -> None:
    with pytest.raises(DomainInvariantError) as error:
        classify_replan_impact(
            context(),
            ReorderActivities(DAY_1, ordered_activity_ids=(A1, A3)),
        )
    assert error.value.code == "reorder_activity_set_mismatch"


def test_cross_city_is_rejected_before_any_execution_boundary() -> None:
    analysis = classify_replan_impact(
        context(second_city="310000"),
        DeleteActivity(A2),
    )

    assert ImpactCategory.CROSS_CITY in analysis.categories
    assert analysis.disposition is ImpactDisposition.REJECT


def test_incomplete_dependency_graph_is_unknown_and_never_auto() -> None:
    analysis = classify_replan_impact(
        context(dependencies_complete=False),
        AdjustActivityTime(A1, start_time=time(10), end_time=time(11)),
    )
    assert ImpactCategory.UNKNOWN_IMPACT in analysis.categories
    assert analysis.disposition is ImpactDisposition.CONFIRM


def test_stale_required_source_forces_refresh_and_confirmation() -> None:
    analysis = classify_replan_impact(
        context(freshness=DataFreshness.STALE),
        AdjustActivityTime(A1, start_time=time(10), end_time=time(11)),
    )
    assert ImpactCategory.SOURCE_REFRESH in analysis.categories
    assert analysis.source_actions[0].action is SourceAction.REFRESH


def test_unknown_target_fails_closed_instead_of_guessing() -> None:
    with pytest.raises(DomainInvariantError) as error:
        classify_replan_impact(
            context(),
            DeleteActivity(UUID("32000000-0000-4000-8000-000000000099")),
        )
    assert error.value.code == "replan_target_not_found"


def test_impact_value_cannot_forge_auto_for_a_high_impact_category() -> None:
    with pytest.raises(DomainInvariantError) as error:
        ImpactAnalysis(
            categories=(ImpactCategory.BUDGET_RISK,),
            disposition=ImpactDisposition.AUTO,
            direct_refs=(A1,),
            transitive_refs=(),
            affected_dates=(DAY_1,),
            route_refs=(),
            source_actions=(),
            required_validations=("budget",),
            confirmation_required=False,
        )
    assert error.value.code == "auto_impact_invalid"
