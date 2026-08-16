"""Provider-neutral offline orchestration around deterministic replan rules."""

from __future__ import annotations

from typing import Protocol

from intelligent_travel_assistant.application.replanning import ReplanExecutionResult
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.contracts import TripPlan
from intelligent_travel_assistant.domain import (
    DomainInvariantError,
    ImpactAnalysis,
    PlanEntitySnapshot,
    ReplanBudgetResult,
    ReplanCommand,
    ReplanImpactContext,
    ReplanStatus,
    build_plan_change_set,
    classify_replan_impact,
    validate_change_set_scope,
)


class ReplanImpactContextPort(Protocol):
    def build(self, job: PlanningJob) -> ReplanImpactContext: ...


class ReplanBudgetEffectPort(Protocol):
    def calculate(self, job: PlanningJob, command: ReplanCommand) -> ReplanBudgetResult | None: ...


class ReplanPlanPort(Protocol):
    async def execute(
        self, job: PlanningJob, replan: ReplanRecord
    ) -> PlanningJobResult | ReplanOutcome: ...


class PlanSnapshotPort(Protocol):
    def project(self, plan: TripPlan) -> tuple[PlanEntitySnapshot, ...]: ...


class ProviderNeutralReplanExecutor:
    """Uses injected narrow facts without importing provider adapters or transport types."""

    def __init__(
        self,
        context: ReplanImpactContextPort,
        budget: ReplanBudgetEffectPort,
        planner: ReplanPlanPort,
        snapshots: PlanSnapshotPort,
    ) -> None:
        self._context = context
        self._budget = budget
        self._planner = planner
        self._snapshots = snapshots

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        return classify_replan_impact(
            self._context.build(job),
            command,
            budget_effect=self._budget.calculate(job, command),
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        if job.result is None or job.result.plan is None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_baseline_missing")
            )
        result = await self._planner.execute(job, replan)
        if isinstance(result, ReplanOutcome):
            return ReplanExecutionResult(outcome=result)
        if result.plan is None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_result_missing")
            )
        impact = replan.impact
        if impact is None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_impact_missing")
            )
        try:
            change_set = build_plan_change_set(
                job.result.plan.plan_id,
                result.plan.plan_id,
                self._snapshots.project(job.result.plan),
                self._snapshots.project(result.plan),
            )
            validate_change_set_scope(
                change_set,
                allowed_refs=tuple(
                    dict.fromkeys(
                        (*impact.direct_refs, *impact.transitive_refs, *impact.route_refs)
                    )
                ),
            )
        except DomainInvariantError:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
            )
        return ReplanExecutionResult(commit=ReplanCommit(result, change_set))
