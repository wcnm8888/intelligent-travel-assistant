"""Contract-level tests for the process-local replan repository double."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.repositories import InMemoryReplanRepository
from intelligent_travel_assistant.application.repositories import (
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
)
from intelligent_travel_assistant.domain import (
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    ReplanChoice,
    ReplanStatus,
)

JOB_ID = UUID("00000000-0000-4000-8000-000000000001")
PLAN_ID = UUID("00000000-0000-4000-8000-000000000004")
ACTIVITY_ID = UUID("00000000-0000-4000-8000-000000000005")
REQUEST_ID = UUID("00000000-0000-4000-8000-000000000006")
NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)


class ManualClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def _confirm_impact() -> ImpactAnalysis:
    return ImpactAnalysis(
        categories=(ImpactCategory.SOURCE_REFRESH,),
        disposition=ImpactDisposition.CONFIRM,
        direct_refs=(ACTIVITY_ID,),
        transitive_refs=(),
        affected_dates=(),
        route_refs=(),
        source_actions=(),
        required_validations=("schedule",),
        confirmation_required=True,
    )


def test_in_memory_replan_reservation_is_idempotent() -> None:
    repository = InMemoryReplanRepository(clock=lambda: NOW)
    command = DeleteActivity(ACTIVITY_ID, reason_code="user_requested")
    first = asyncio.run(
        repository.reserve(
            JOB_ID,
            REQUEST_ID,
            command,
            baseline_plan_id=PLAN_ID,
            baseline_plan_version=1,
            expected_job_version=1,
        )
    )
    second = asyncio.run(
        repository.reserve(
            JOB_ID,
            REQUEST_ID,
            command,
            baseline_plan_id=PLAN_ID,
            baseline_plan_version=1,
            expected_job_version=1,
        )
    )
    assert first.created is True
    assert second.created is False
    assert second.replan.replan_id == first.replan.replan_id


def test_in_memory_replan_rejects_invalid_impact() -> None:
    repository = InMemoryReplanRepository(clock=lambda: NOW)
    command = DeleteActivity(ACTIVITY_ID)
    reserved = asyncio.run(
        repository.reserve(
            JOB_ID,
            REQUEST_ID,
            command,
            baseline_plan_id=PLAN_ID,
            baseline_plan_version=1,
            expected_job_version=1,
        )
    )
    with pytest.raises(ReplanRepositoryError) as error:
        asyncio.run(
            repository.record_analysis(
                JOB_ID,
                reserved.replan.replan_id,
                object(),  # type: ignore[arg-type]
                expected_replan_version=1,
            )
        )
    assert error.value.code is ReplanRepositoryErrorCode.JSON_INVALID


def test_confirmation_is_idempotent_and_opposite_choice_conflicts() -> None:
    identifiers = iter(
        (
            UUID("00000000-0000-4000-8000-000000000011"),
            UUID("00000000-0000-4000-8000-000000000012"),
            UUID("00000000-0000-4000-8000-000000000013"),
        )
    )
    repository = InMemoryReplanRepository(id_factory=identifiers.__next__)
    reserved = asyncio.run(
        repository.reserve(
            JOB_ID,
            REQUEST_ID,
            DeleteActivity(ACTIVITY_ID),
            baseline_plan_id=PLAN_ID,
            expected_job_version=3,
        )
    )
    pending = asyncio.run(
        repository.record_analysis(
            JOB_ID,
            reserved.replan.replan_id,
            _confirm_impact(),
            expected_replan_version=reserved.replan.aggregate_version,
        )
    )
    with pytest.raises(ReplanRepositoryError) as stale_job:
        asyncio.run(
            repository.decide(
                JOB_ID,
                pending.replan_id,
                ReplanChoice.APPROVE,
                expected_replan_version=pending.aggregate_version,
                expected_job_version=4,
            )
        )
    assert stale_job.value.code is ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT
    approved = asyncio.run(
        repository.decide(
            JOB_ID,
            pending.replan_id,
            ReplanChoice.APPROVE,
            expected_replan_version=pending.aggregate_version,
            expected_job_version=3,
        )
    )
    repeated = asyncio.run(
        repository.decide(
            JOB_ID,
            pending.replan_id,
            ReplanChoice.APPROVE,
            expected_replan_version=pending.aggregate_version,
            expected_job_version=3,
        )
    )
    assert repeated == approved

    with pytest.raises(ReplanRepositoryError) as error:
        asyncio.run(
            repository.decide(
                JOB_ID,
                pending.replan_id,
                ReplanChoice.CANCEL,
                expected_replan_version=approved.aggregate_version,
                expected_job_version=3,
            )
        )
    assert error.value.code is ReplanRepositoryErrorCode.DECISION_CONFLICT


def test_expired_confirmation_is_persisted_as_terminal_without_execution() -> None:
    clock = ManualClock()
    identifiers = iter(
        (
            UUID("00000000-0000-4000-8000-000000000021"),
            UUID("00000000-0000-4000-8000-000000000022"),
            UUID("00000000-0000-4000-8000-000000000023"),
        )
    )
    repository = InMemoryReplanRepository(clock=clock, id_factory=identifiers.__next__)
    reserved = asyncio.run(
        repository.reserve(
            JOB_ID,
            REQUEST_ID,
            DeleteActivity(ACTIVITY_ID),
            baseline_plan_id=PLAN_ID,
            expected_job_version=1,
        )
    )
    pending = asyncio.run(
        repository.record_analysis(
            JOB_ID,
            reserved.replan.replan_id,
            _confirm_impact(),
            expected_replan_version=reserved.replan.aggregate_version,
        )
    )
    clock.now += timedelta(minutes=15)

    expired = asyncio.run(
        repository.decide(
            JOB_ID,
            pending.replan_id,
            ReplanChoice.APPROVE,
            expected_replan_version=pending.aggregate_version,
            expected_job_version=1,
        )
    )

    assert expired.status is ReplanStatus.EXPIRED
    assert expired.error_code == ReplanRepositoryErrorCode.CONFIRMATION_EXPIRED.value
    assert expired.decision is not None and expired.decision.choice is None
