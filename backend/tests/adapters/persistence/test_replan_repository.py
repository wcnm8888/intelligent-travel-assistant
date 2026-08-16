"""Offline tests for the F-003 SQLite replan aggregate."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from intelligent_travel_assistant.adapters.persistence import (
    MigrationRunner,
    SqliteConnectionConfig,
    SqliteDatabase,
    SqlitePlanningJobRepository,
    SqliteReplanRepository,
)
from intelligent_travel_assistant.application.repositories import (
    PlanningJob,
    PlanningJobResult,
    ReplanCommit,
    ReplanOutcome,
    ReplanRecord,
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
)
from intelligent_travel_assistant.contracts import PlanningStatus, TripPlanRequest, TripPlanResponse
from intelligent_travel_assistant.domain import (
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReplanChoice,
    ReplanStatus,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures"

JOB_ID = UUID("00000000-0000-4000-8000-000000000001")
TRACE_ID = UUID("00000000-0000-4000-8000-000000000002")
CLIENT_REQUEST_ID = UUID("00000000-0000-4000-8000-000000000003")
PLAN_ID = UUID("00000000-0000-4000-8000-000000000004")
ACTIVITY_ID = UUID("00000000-0000-4000-8000-000000000005")
REPLAN_REQUEST_ID = UUID("00000000-0000-4000-8000-000000000006")
REPLAN_ID = UUID("00000000-0000-4000-8000-000000000007")
DECISION_ID = UUID("00000000-0000-4000-8000-000000000008")
NOW = datetime(2026, 8, 16, 12, tzinfo=UTC)
RESULT_PLAN_ID = UUID("00000000-0000-4000-8000-000000000009")
SECOND_REPLAN_REQUEST_ID = UUID("00000000-0000-4000-8000-000000000010")
SECOND_REPLAN_ID = UUID("00000000-0000-4000-8000-000000000011")
SECOND_DECISION_ID = UUID("00000000-0000-4000-8000-000000000012")
REPLAN_TRACE_ID = UUID("00000000-0000-4000-8000-000000000013")
THIRD_PLAN_ID = UUID("00000000-0000-4000-8000-000000000014")


def _database(path: Path) -> SqliteDatabase:
    database = SqliteDatabase(SqliteConnectionConfig(path))
    MigrationRunner().run(database.open())
    connection = database.connection
    connection.execute(
        """
        INSERT INTO planning_jobs(
            job_id, trace_id, client_request_id, request_fingerprint, request_json,
            status, attempt, version, retryable, created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, 'ready', 1, 1, 0, ?, ?, ?)
        """,
        (
            str(JOB_ID),
            str(TRACE_ID),
            str(CLIENT_REQUEST_ID),
            "a" * 64,
            "{}",
            NOW.isoformat(),
            NOW.isoformat(),
            "2026-09-15T12:00:00Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO planning_attempts(
            job_id, attempt, trace_id, status, retryable, started_at, updated_at,
            current_plan_version, result_metadata_json
        ) VALUES (?, 1, ?, 'ready', 0, ?, ?, 1, NULL)
        """,
        (str(JOB_ID), str(TRACE_ID), NOW.isoformat(), NOW.isoformat()),
    )
    connection.execute(
        """
        INSERT INTO plan_versions(
            job_id, version_number, plan_id, attempt, trace_id, status, plan_json, created_at
        ) VALUES (?, 1, ?, 1, ?, 'ready', '{}', ?)
        """,
        (str(JOB_ID), str(PLAN_ID), str(TRACE_ID), NOW.isoformat()),
    )
    return database


def _command() -> DeleteActivity:
    return DeleteActivity(ACTIVITY_ID, reason_code="user_requested")


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


def _auto_impact() -> ImpactAnalysis:
    return ImpactAnalysis(
        categories=(ImpactCategory.SAME_DAY_LOW,),
        disposition=ImpactDisposition.AUTO,
        direct_refs=(ACTIVITY_ID,),
        transitive_refs=(),
        affected_dates=(),
        route_refs=(),
        source_actions=(),
        required_validations=("schedule",),
        confirmation_required=False,
    )


def _request() -> TripPlanRequest:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_request.json").read_text(encoding="utf-8")
    )["request"]
    return TripPlanRequest.model_validate(payload)


def _ready_result(*, plan_id: UUID | None = None) -> PlanningJobResult:
    payload = json.loads(
        (FIXTURE_ROOT / "synthetic_hangzhou_ready.json").read_text(encoding="utf-8")
    )["response"]
    response = TripPlanResponse.model_validate(payload)
    plan = response.plan
    assert plan is not None
    if plan_id is not None:
        plan = plan.model_copy(update={"plan_id": plan_id})
    return PlanningJobResult(
        status=response.status,
        resolved_destination=response.resolved_destination,
        plan=plan,
        violations=response.violations,
        warnings=response.warnings,
        uncertainties=response.uncertainties,
        sources=response.sources,
        errors=response.errors,
        retryable=response.retryable,
    )


def _ready_database(path: Path) -> tuple[SqliteDatabase, PlanningJob]:
    database = SqliteDatabase(SqliteConnectionConfig(path))
    MigrationRunner().run(database.open())
    identifiers = iter((JOB_ID, TRACE_ID))
    repository = SqlitePlanningJobRepository(
        database, clock=lambda: NOW, id_factory=identifiers.__next__
    )
    job = asyncio.run(repository.get_or_create(_request())).job
    for status in (
        PlanningStatus.NORMALIZING,
        PlanningStatus.COLLECTING,
        PlanningStatus.PLANNING,
        PlanningStatus.VALIDATING,
    ):
        job = asyncio.run(repository.advance(job.job_id, status, expected_version=job.version))
    job = asyncio.run(
        repository.record_result(job.job_id, _ready_result(), expected_version=job.version)
    )
    return database, job


def _commit(
    job: PlanningJob,
    *,
    result_plan_id: UUID = RESULT_PLAN_ID,
    result: PlanningJobResult | None = None,
) -> ReplanCommit:
    assert job.result is not None and job.result.plan is not None
    committed_result = result or _ready_result(plan_id=result_plan_id)
    return ReplanCommit(
        committed_result,
        PlanChangeSet(
            baseline_plan_id=job.result.plan.plan_id,
            result_plan_id=result_plan_id,
            added_refs=(),
            removed_refs=(),
            changed_refs=(),
            added_origins=(),
            change_codes=(),
        ),
    )


def test_confirmation_ttl_starts_when_analysis_finishes(tmp_path: Path) -> None:
    database, job = _ready_database(tmp_path / "confirmation-ttl.sqlite3")
    current_time = [NOW]
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_ID, DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: current_time[0], id_factory=identifiers.__next__
        )
        reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
                trace_id=REPLAN_TRACE_ID,
            )
        )
        current_time[0] = NOW + timedelta(minutes=7)
        analyzed = asyncio.run(
            repository.record_analysis(
                job.job_id,
                reserved.replan.replan_id,
                _confirm_impact(),
                expected_replan_version=reserved.replan.aggregate_version,
            )
        )

        assert analyzed.expires_at == current_time[0] + timedelta(minutes=15)
    finally:
        database.close()


def test_analysis_failure_can_be_persisted_from_analyzing(tmp_path: Path) -> None:
    database, job = _ready_database(tmp_path / "analysis-failure.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=lambda: REPLAN_ID
        )
        reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
                trace_id=REPLAN_TRACE_ID,
            )
        )
        failed = asyncio.run(
            repository.record_outcome(
                job.job_id,
                reserved.replan.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "replan_analysis_failed"),
                expected_replan_version=reserved.replan.aggregate_version,
            )
        )
        assert failed.status is ReplanStatus.FAILED
        assert failed.error_code == "replan_analysis_failed"
    finally:
        database.close()


def test_completed_replan_keeps_its_historical_result_after_later_commit(
    tmp_path: Path,
) -> None:
    database, job = _ready_database(tmp_path / "historical-result.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_ID, DECISION_ID, SECOND_REPLAN_ID, SECOND_DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=identifiers.__next__
        )
        first_reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
                trace_id=REPLAN_TRACE_ID,
            )
        )
        first_analyzed = asyncio.run(
            repository.record_analysis(
                job.job_id,
                first_reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=first_reserved.replan.aggregate_version,
            )
        )
        asyncio.run(
            repository.commit(
                job.job_id,
                first_analyzed.replan_id,
                _commit(job),
                expected_replan_version=first_analyzed.aggregate_version,
                expected_job_version=job.version,
            )
        )
        lineage_json = database.connection.execute(
            """
            SELECT change_set_json FROM plan_version_lineage
            WHERE job_id = ? AND child_version = 2
            """,
            (str(job.job_id),),
        ).fetchone()[0]
        lineage_payload = json.loads(lineage_json)
        database.connection.execute(
            """
            UPDATE plan_version_lineage SET change_set_json = ?
            WHERE job_id = ? AND child_version = 2
            """,
            (json.dumps(lineage_payload["change_set"]), str(job.job_id)),
        )
        next_job = asyncio.run(SqlitePlanningJobRepository(database).get(job.job_id))
        assert next_job.result is not None and next_job.result.plan is not None
        second_reserved = asyncio.run(
            repository.reserve(
                next_job.job_id,
                SECOND_REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=next_job.result.plan.plan_id,
                expected_job_version=next_job.version,
                trace_id=REPLAN_TRACE_ID,
            )
        )
        second_analyzed = asyncio.run(
            repository.record_analysis(
                next_job.job_id,
                second_reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=second_reserved.replan.aggregate_version,
            )
        )
        latest_result = _ready_result(plan_id=THIRD_PLAN_ID)
        latest_result = PlanningJobResult(
            status=latest_result.status,
            resolved_destination=latest_result.resolved_destination,
            plan=latest_result.plan,
            violations=latest_result.violations,
            warnings=("latest-only-warning",),
            uncertainties=latest_result.uncertainties,
            sources=latest_result.sources,
            errors=latest_result.errors,
            retryable=latest_result.retryable,
        )
        asyncio.run(
            repository.commit(
                next_job.job_id,
                second_analyzed.replan_id,
                _commit(
                    next_job,
                    result_plan_id=THIRD_PLAN_ID,
                    result=latest_result,
                ),
                expected_replan_version=second_analyzed.aggregate_version,
                expected_job_version=next_job.version,
            )
        )

        historical = asyncio.run(repository.get(job.job_id, first_analyzed.replan_id))
        assert historical.result_plan_version == 2
        assert historical.result is not None and historical.result.plan is not None
        assert historical.result.plan.plan_id == RESULT_PLAN_ID
        assert "latest-only-warning" not in historical.result.warnings
        assert historical.change_set is not None
        assert historical.change_set.result_plan_id == RESULT_PLAN_ID
        upgraded_lineage = json.loads(
            database.connection.execute(
                """
                SELECT change_set_json FROM plan_version_lineage
                WHERE job_id = ? AND child_version = 2
                """,
                (str(job.job_id),),
            ).fetchone()[0]
        )
        assert "result_metadata" in upgraded_lineage
    finally:
        database.close()


def test_sqlite_replan_reserve_is_idempotent_and_typed(tmp_path: Path) -> None:
    database = _database(tmp_path / "replan.sqlite3")
    try:
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=lambda: REPLAN_ID
        )
        first = asyncio.run(
            repository.reserve(
                JOB_ID,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=PLAN_ID,
                baseline_plan_version=1,
                expected_job_version=1,
                trace_id=TRACE_ID,
            )
        )
        second = asyncio.run(
            repository.reserve(
                JOB_ID,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=PLAN_ID,
                baseline_plan_version=1,
                expected_job_version=1,
                trace_id=TRACE_ID,
            )
        )
        assert first.created is True
        assert second.created is False
        assert second.replan.replan_id == REPLAN_ID
        assert second.replan.command == _command()
        assert second.replan.impact is None
    finally:
        database.close()


def test_sqlite_analysis_persists_typed_decision_and_expected_version(tmp_path: Path) -> None:
    database = _database(tmp_path / "decision.sqlite3")
    try:
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=iter((REPLAN_ID, DECISION_ID)).__next__
        )
        reserved = asyncio.run(
            repository.reserve(
                JOB_ID,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=PLAN_ID,
                baseline_plan_version=1,
                expected_job_version=1,
                trace_id=TRACE_ID,
            )
        )
        analyzed = asyncio.run(
            repository.record_analysis(
                JOB_ID, reserved.replan.replan_id, _confirm_impact(), expected_replan_version=1
            )
        )
        assert analyzed.status.value == "awaiting_confirmation"
        assert analyzed.aggregate_version == 2
        assert analyzed.decision is not None
        assert analyzed.decision.status.value == "pending"
        decided = asyncio.run(
            repository.decide(
                JOB_ID,
                reserved.replan.replan_id,
                ReplanChoice.APPROVE,
                expected_replan_version=2,
                expected_job_version=1,
            )
        )
        assert decided.status.value == "replanning"
        assert decided.decision is not None
        assert decided.decision.choice is ReplanChoice.APPROVE
        repeated = asyncio.run(
            repository.decide(
                JOB_ID,
                reserved.replan.replan_id,
                ReplanChoice.APPROVE,
                expected_replan_version=2,
                expected_job_version=1,
            )
        )
        assert repeated == decided
        with pytest.raises(ReplanRepositoryError) as choice_error:
            asyncio.run(
                repository.decide(
                    JOB_ID,
                    reserved.replan.replan_id,
                    ReplanChoice.CANCEL,
                    expected_replan_version=decided.aggregate_version,
                    expected_job_version=1,
                )
            )
        assert choice_error.value.code is ReplanRepositoryErrorCode.DECISION_CONFLICT
        with pytest.raises(ReplanRepositoryError) as error:
            asyncio.run(
                repository.record_analysis(
                    JOB_ID, reserved.replan.replan_id, _confirm_impact(), expected_replan_version=2
                )
            )
        assert error.value.code is ReplanRepositoryErrorCode.VERSION_CONFLICT
    finally:
        database.close()


def test_sqlite_expired_confirmation_is_durable(tmp_path: Path) -> None:
    database = _database(tmp_path / "expired-decision.sqlite3")
    clock = [NOW]
    try:
        repository = SqliteReplanRepository(
            database,
            clock=lambda: clock[0],
            id_factory=iter((REPLAN_ID, DECISION_ID)).__next__,
        )
        reserved = asyncio.run(
            repository.reserve(
                JOB_ID,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=PLAN_ID,
                baseline_plan_version=1,
                expected_job_version=1,
                trace_id=TRACE_ID,
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
        clock[0] += timedelta(minutes=15)

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
        restored = asyncio.run(repository.get(JOB_ID, pending.replan_id))
        assert restored == expired
        assert restored.decision is not None
        assert restored.decision.status.value == "expired"
    finally:
        database.close()


def test_sqlite_confirmation_rejects_a_newer_job_version_than_its_baseline(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "stale-confirmation.sqlite3")
    try:
        repository = SqliteReplanRepository(
            database,
            clock=lambda: NOW,
            id_factory=iter((REPLAN_ID, DECISION_ID)).__next__,
        )
        reserved = asyncio.run(
            repository.reserve(
                JOB_ID,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=PLAN_ID,
                baseline_plan_version=1,
                expected_job_version=1,
                trace_id=TRACE_ID,
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
        database.connection.execute(
            "UPDATE planning_jobs SET version = 2 WHERE job_id = ?", (str(JOB_ID),)
        )

        with pytest.raises(ReplanRepositoryError) as error:
            asyncio.run(
                repository.decide(
                    JOB_ID,
                    pending.replan_id,
                    ReplanChoice.APPROVE,
                    expected_replan_version=pending.aggregate_version,
                    expected_job_version=2,
                )
            )

        assert error.value.code is ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT
        restored = asyncio.run(repository.get(JOB_ID, pending.replan_id))
        assert restored.status is ReplanStatus.AWAITING_CONFIRMATION
        assert restored.decision is not None and restored.decision.choice is None
    finally:
        database.close()


def test_sqlite_commit_atomically_appends_plan_lineage_and_updates_current_job(
    tmp_path: Path,
) -> None:
    database, job = _ready_database(tmp_path / "commit.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_TRACE_ID, REPLAN_ID, DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=identifiers.__next__
        )
        reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
            )
        )
        analyzed = asyncio.run(
            repository.record_analysis(
                job.job_id,
                reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=reserved.replan.aggregate_version,
            )
        )
        assert analyzed.trace_id == REPLAN_TRACE_ID
        assert analyzed.trace_id != job.trace_id
        asyncio.run(
            repository.begin_execution(
                job.job_id,
                analyzed.replan_id,
                expected_replan_version=analyzed.aggregate_version,
                expected_job_version=job.version,
            )
        )

        committed = asyncio.run(
            repository.commit(
                job.job_id,
                analyzed.replan_id,
                _commit(job),
                expected_replan_version=analyzed.aggregate_version,
                expected_job_version=job.version,
            )
        )

        assert committed.replan.status is ReplanStatus.COMPLETED
        assert committed.plan_version == 2
        assert committed.job_version == job.version + 1
        assert committed.replan.result is not None
        assert committed.replan.result.plan is not None
        assert committed.replan.result.plan.plan_id == RESULT_PLAN_ID
        assert committed.replan.change_set == _commit(job).change_set
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?", (str(job.job_id),)
            ).fetchone()[0]
            == 2
        )
        lineage = database.connection.execute(
            "SELECT parent_version, child_version FROM plan_version_lineage WHERE replan_id = ?",
            (str(analyzed.replan_id),),
        ).fetchone()
        assert lineage is not None and tuple(lineage) == (1, 2)
        restored = asyncio.run(SqlitePlanningJobRepository(database).get(job.job_id))
        assert restored.result is not None and restored.result.plan is not None
        assert restored.result.plan.plan_id == RESULT_PLAN_ID
        assert restored.version == job.version + 1
        stored_trace_id = database.connection.execute(
            "SELECT trace_id FROM plan_versions WHERE job_id = ? AND version_number = 2",
            (str(job.job_id),),
        ).fetchone()[0]
        assert stored_trace_id == str(job.trace_id)
        restored_replan = asyncio.run(repository.get(job.job_id, analyzed.replan_id))
        assert restored_replan.result == committed.replan.result
        assert restored_replan.change_set == committed.replan.change_set
    finally:
        database.close()


def test_same_baseline_concurrent_replans_allow_only_one_commit(tmp_path: Path) -> None:
    database, job = _ready_database(tmp_path / "concurrent-commit.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_ID, DECISION_ID, SECOND_REPLAN_ID, SECOND_DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=identifiers.__next__
        )
        baseline_plan_id = job.result.plan.plan_id

        async def prepare(request_id: UUID) -> ReplanRecord:
            reserved = await repository.reserve(
                job.job_id,
                request_id,
                _command(),
                baseline_plan_id=baseline_plan_id,
                expected_job_version=job.version,
                trace_id=TRACE_ID,
            )
            return await repository.record_analysis(
                job.job_id,
                reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=reserved.replan.aggregate_version,
            )

        first = asyncio.run(prepare(REPLAN_REQUEST_ID))
        second = asyncio.run(prepare(SECOND_REPLAN_REQUEST_ID))
        asyncio.run(
            repository.commit(
                job.job_id,
                first.replan_id,
                _commit(job),
                expected_replan_version=first.aggregate_version,
                expected_job_version=job.version,
            )
        )

        with pytest.raises(ReplanRepositoryError) as error:
            asyncio.run(
                repository.commit(
                    job.job_id,
                    second.replan_id,
                    _commit(job),
                    expected_replan_version=second.aggregate_version,
                    expected_job_version=job.version,
                )
            )

        assert error.value.code is ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?", (str(job.job_id),)
            ).fetchone()[0]
            == 2
        )
        assert (
            asyncio.run(repository.get(job.job_id, second.replan_id)).status
            is ReplanStatus.REPLANNING
        )
    finally:
        database.close()


def test_commit_failure_rolls_back_plan_job_lineage_and_replan_state(tmp_path: Path) -> None:
    database, job = _ready_database(tmp_path / "rollback.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_ID, DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=identifiers.__next__
        )
        reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
                trace_id=TRACE_ID,
            )
        )
        analyzed = asyncio.run(
            repository.record_analysis(
                job.job_id,
                reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=reserved.replan.aggregate_version,
            )
        )
        database.connection.execute(
            """
            CREATE TEMP TRIGGER fail_lineage BEFORE INSERT ON plan_version_lineage
            BEGIN SELECT RAISE(ABORT, 'synthetic_failure'); END
            """
        )

        with pytest.raises(ReplanRepositoryError) as error:
            asyncio.run(
                repository.commit(
                    job.job_id,
                    analyzed.replan_id,
                    _commit(job),
                    expected_replan_version=analyzed.aggregate_version,
                    expected_job_version=job.version,
                )
            )

        assert error.value.code is ReplanRepositoryErrorCode.COMMIT_INVALID
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?", (str(job.job_id),)
            ).fetchone()[0]
            == 1
        )
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_version_lineage WHERE replan_id = ?",
                (str(analyzed.replan_id),),
            ).fetchone()[0]
            == 0
        )
        restored = asyncio.run(SqlitePlanningJobRepository(database).get(job.job_id))
        assert restored.version == job.version and restored.result == job.result
        assert (
            asyncio.run(repository.get(job.job_id, analyzed.replan_id)).status
            is ReplanStatus.REPLANNING
        )
    finally:
        database.close()


def test_safe_terminal_outcome_does_not_create_plan_version(tmp_path: Path) -> None:
    database, job = _ready_database(tmp_path / "outcome.sqlite3")
    try:
        assert job.result is not None and job.result.plan is not None
        identifiers = iter((REPLAN_ID, DECISION_ID))
        repository = SqliteReplanRepository(
            database, clock=lambda: NOW, id_factory=identifiers.__next__
        )
        reserved = asyncio.run(
            repository.reserve(
                job.job_id,
                REPLAN_REQUEST_ID,
                _command(),
                baseline_plan_id=job.result.plan.plan_id,
                expected_job_version=job.version,
                trace_id=TRACE_ID,
            )
        )
        analyzed = asyncio.run(
            repository.record_analysis(
                job.job_id,
                reserved.replan.replan_id,
                _auto_impact(),
                expected_replan_version=reserved.replan.aggregate_version,
            )
        )
        failed = asyncio.run(
            repository.record_outcome(
                job.job_id,
                analyzed.replan_id,
                ReplanOutcome(ReplanStatus.FAILED, "offline_execution_failed"),
                expected_replan_version=analyzed.aggregate_version,
            )
        )
        assert failed.status is ReplanStatus.FAILED
        assert failed.error_code == "offline_execution_failed"
        assert (
            database.connection.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE job_id = ?", (str(job.job_id),)
            ).fetchone()[0]
            == 1
        )
        assert asyncio.run(SqlitePlanningJobRepository(database).get(job.job_id)) == job
    finally:
        database.close()
