"""Provider-neutral offline orchestration around deterministic replan rules."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, cast

from intelligent_travel_assistant.application.replanning import ReplanExecutionResult
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
)
from intelligent_travel_assistant.application.services.replan_facts import (
    EvidencedReplanResult,
    ReplanEvidence,
)
from intelligent_travel_assistant.contracts import ApiErrorCode, TripPlan
from intelligent_travel_assistant.domain import (
    DomainInvariantError,
    ImpactAnalysis,
    PlanChangeSet,
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
    ) -> PlanningJobResult | ReplanOutcome | EvidencedReplanResult: ...


class PlanSnapshotPort(Protocol):
    def project(self, plan: TripPlan) -> tuple[PlanEntitySnapshot, ...]: ...


class ReplanFactsPort(Protocol):
    def analyze(
        self, job: PlanningJob, command: ReplanCommand, *, evaluated_at: datetime
    ) -> ImpactAnalysis: ...

    def changes(
        self,
        job: PlanningJob,
        command: ReplanCommand,
        impact: ImpactAnalysis,
        result: PlanningJobResult,
        *,
        evaluated_at: datetime,
    ) -> PlanChangeSet: ...


class EvidencedReplanFactsPort(ReplanFactsPort, Protocol):
    def changes(
        self,
        job: PlanningJob,
        command: ReplanCommand,
        impact: ImpactAnalysis,
        result: PlanningJobResult,
        *,
        evaluated_at: datetime,
        evidence: ReplanEvidence | None = None,
    ) -> PlanChangeSet: ...


class ProviderNeutralReplanExecutor:
    """Uses injected narrow facts without importing provider adapters or transport types."""

    def __init__(
        self,
        context: ReplanImpactContextPort,
        budget: ReplanBudgetEffectPort,
        planner: ReplanPlanPort,
        snapshots: PlanSnapshotPort,
        *,
        facts: ReplanFactsPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if (facts is None) != (clock is None):
            raise ValueError("replan_fact_clock_pair_required")
        self._context = context
        self._budget = budget
        self._planner = planner
        self._snapshots = snapshots
        self._facts = facts
        self._clock = clock

    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis:
        if self._facts is not None:
            assert self._clock is not None
            try:
                return self._facts.analyze(job, command, evaluated_at=self._clock())
            except (ValueError, TypeError, AttributeError):
                raise DomainInvariantError("replan_analysis_failed", field="facts") from None
        return classify_replan_impact(
            self._context.build(job),
            command,
            budget_effect=self._budget.calculate(job, command),
        )

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult:
        if not isinstance(job.result, PlanningJobResult) or job.result.plan is None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_baseline_missing")
            )
        result = await self._planner.execute(job, replan)
        if isinstance(result, ReplanOutcome):
            return ReplanExecutionResult(outcome=result)
        evidence = None
        if isinstance(result, EvidencedReplanResult):
            evidence = result.evidence
            if (
                self._facts is None
                or self._clock is None
                or type(evidence) is not ReplanEvidence
                or evidence.job_id != job.job_id
                or replan.job_id != job.job_id
                or evidence.replan_id != replan.replan_id
                or evidence.baseline_plan_id != replan.baseline_plan_id
                or evidence.job_version != job.version
                or replan.expected_job_version != job.version
                or type(result.result) is not PlanningJobResult
                or result.result.plan is None
            ):
                return ReplanExecutionResult(
                    outcome=ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
                )
            result = result.result
        if result.plan is None:
            return ReplanExecutionResult(outcome=_planless_outcome(result))
        if not isinstance(job.result.plan, TripPlan) or not isinstance(result.plan, TripPlan):
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_scope_not_supported")
            )
        impact = replan.impact
        if impact is None:
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.FAILED, "replan_impact_missing")
            )
        try:
            if self._facts is not None:
                assert self._clock is not None
                # Evaluate after candidate completion: newly fetched sources cannot be
                # assessed against an earlier instant. Both snapshots share this clock.
                at = self._clock()
                change_set = (
                    self._facts.changes(job, replan.command, impact, result, evaluated_at=at)
                    if evidence is None
                    else cast(EvidencedReplanFactsPort, self._facts).changes(
                        job, replan.command, impact, result, evaluated_at=at, evidence=evidence
                    )
                )
                return ReplanExecutionResult(commit=ReplanCommit(result, change_set))
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
        except (ValueError, TypeError, AttributeError):
            return ReplanExecutionResult(
                outcome=ReplanOutcome(ReplanStatus.CONFLICT, "replan_change_scope_conflict")
            )
        return ReplanExecutionResult(commit=ReplanCommit(result, change_set))


def _planless_outcome(result: PlanningJobResult) -> ReplanOutcome:
    if not result.errors:
        return ReplanOutcome(ReplanStatus.FAILED, "replan_result_missing")
    code = result.errors[0].code
    if code in {ApiErrorCode.DATA_MISSING, ApiErrorCode.BUDGET_INCOMPLETE}:
        status = ReplanStatus.NEEDS_INPUT
    elif code in {ApiErrorCode.CONSTRAINT_CONFLICT, ApiErrorCode.VERSION_CONFLICT}:
        status = ReplanStatus.CONFLICT
    elif code is ApiErrorCode.REPLAN_SCOPE_NOT_SUPPORTED:
        status = ReplanStatus.REJECTED
    else:
        status = ReplanStatus.FAILED
    return ReplanOutcome(status, code.value)
