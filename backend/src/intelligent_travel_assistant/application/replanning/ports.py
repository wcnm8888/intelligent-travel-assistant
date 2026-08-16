"""Provider-neutral execution boundary for one analyzed replan."""

from typing import Protocol, runtime_checkable

from intelligent_travel_assistant.application.replanning.models import ReplanExecutionResult
from intelligent_travel_assistant.application.repositories import PlanningJob, ReplanRecord
from intelligent_travel_assistant.domain import ImpactAnalysis, ReplanCommand


@runtime_checkable
class ReplanExecutionPort(Protocol):
    async def analyze(self, job: PlanningJob, command: ReplanCommand) -> ImpactAnalysis: ...

    async def execute(self, job: PlanningJob, replan: ReplanRecord) -> ReplanExecutionResult: ...
