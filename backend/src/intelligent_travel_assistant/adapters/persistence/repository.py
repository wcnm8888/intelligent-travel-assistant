"""SQLite implementation of the application-owned planning-job repository port."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import NoReturn, cast
from uuid import UUID, uuid4

from pydantic import Field, TypeAdapter

from intelligent_travel_assistant.adapters.persistence.connection import (
    SqliteDatabase,
    sqlite_transaction,
)
from intelligent_travel_assistant.application.repositories import (
    AcceptanceRecord,
    PlanningJob,
    PlanningJobRepositoryError,
    PlanningJobRepositoryErrorCode,
    PlanningJobReservation,
    PlanningJobResult,
    ReplanCommit,
    ReplanCommitResult,
    ReplanDecisionRecord,
    ReplanOutcome,
    ReplanRecord,
    ReplanRepositoryError,
    ReplanRepositoryErrorCode,
    ReplanReservation,
    RequestFingerprint,
    request_fingerprint,
    result_matches_request,
)
from intelligent_travel_assistant.application.state_machine import (
    PlanningStateMachine,
    PlanningTransitionCommand,
    PlanningTransitionError,
    PlanningTransitionTrigger,
)
from intelligent_travel_assistant.contracts import (
    ApiError,
    ConstraintViolation,
    PlanningPlan,
    PlanningRequest,
    PlanningStatus,
    ResolvedDestination,
    SourceRecord,
    TripPlan,
    TripPlanRequestV2,
    TripPlanV2,
    Uncertainty,
)
from intelligent_travel_assistant.contracts.base import ContractModel
from intelligent_travel_assistant.domain import (
    AdjustActivityTime,
    DataFreshness,
    DeleteActivity,
    ImpactAnalysis,
    ImpactCategory,
    ImpactDisposition,
    PlanChangeSet,
    ReorderActivities,
    ReplaceActivity,
    ReplanChoice,
    ReplanCommand,
    ReplanDecisionStatus,
    ReplanOperation,
    ReplanStatus,
    SourceAction,
    SourceActionReason,
    SourceActionRecord,
)

_RETENTION_PERIOD = timedelta(days=30)
_TERMINAL_STATUSES = frozenset(
    {
        PlanningStatus.READY,
        PlanningStatus.PARTIAL,
        PlanningStatus.CONFLICT,
        PlanningStatus.NEEDS_INPUT,
        PlanningStatus.FAILED,
    }
)
_PRIVATE_MATERIAL = re.compile(
    r"authorization\s*:|cookie\s*:|(?:api[_-]?key|access[_-]?token|token|jwt|"
    r"private[_-]?key|secret|password)\s*[=:]|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)
_PLANNING_REQUEST_ADAPTER: TypeAdapter[PlanningRequest] = TypeAdapter(PlanningRequest)
_PLANNING_PLAN_ADAPTER: TypeAdapter[PlanningPlan] = TypeAdapter(PlanningPlan)


class _StoredResultMetadata(ContractModel):
    """Typed, allowlisted terminal metadata stored outside the plan snapshot."""

    resolved_destination: ResolvedDestination | None
    violations: tuple[ConstraintViolation, ...] = Field(max_length=50)
    warnings: tuple[str, ...] = Field(max_length=50)
    uncertainties: tuple[Uncertainty, ...] = Field(max_length=50)
    errors: tuple[ApiError, ...] = Field(max_length=20)
    source_ids: tuple[UUID, ...] = Field(max_length=100)


class SqlitePlanningJobRepository:
    """Single-connection SQLite adapter with atomic optimistic updates."""

    def __init__(
        self,
        database: SqliteDatabase,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        if not isinstance(database, SqliteDatabase):
            raise TypeError("sqlite_database_invalid")
        self._database = database
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._lock = asyncio.Lock()

    async def get_or_create(self, request: PlanningRequest) -> PlanningJobReservation:
        fingerprint = request_fingerprint(request)
        try:
            request_json = self._dump_json(request.model_dump(mode="json"))
        except ValueError:
            self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    existing = self._database.connection.execute(
                        "SELECT * FROM planning_jobs WHERE client_request_id = ?",
                        (str(request.client_request_id),),
                    ).fetchone()
                    if existing is not None:
                        if self._text(existing, "request_fingerprint") != fingerprint.digest:
                            self._raise(PlanningJobRepositoryErrorCode.IDEMPOTENCY_CONFLICT)
                        return PlanningJobReservation(
                            created=False,
                            job=self._hydrate_job(existing),
                        )

                    created_at = self._now()
                    job_id, trace_id = self._new_identifiers(2)
                    values = (
                        str(job_id),
                        str(trace_id),
                        str(request.client_request_id),
                        fingerprint.digest,
                        request_json,
                        PlanningStatus.DRAFT.value,
                        1,
                        1,
                        0,
                        self._format_datetime(created_at),
                        self._format_datetime(created_at),
                        self._format_datetime(created_at + _RETENTION_PERIOD),
                    )
                    self._database.connection.execute(
                        """
                        INSERT INTO planning_jobs(
                            job_id, trace_id, client_request_id, request_fingerprint,
                            request_json, status, attempt, version, retryable,
                            created_at, updated_at, expires_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                    self._database.connection.execute(
                        """
                        INSERT INTO planning_attempts(
                            job_id, attempt, trace_id, status, retryable,
                            started_at, updated_at, current_plan_version,
                            result_metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                        """,
                        (
                            str(job_id),
                            1,
                            str(trace_id),
                            PlanningStatus.DRAFT.value,
                            0,
                            self._format_datetime(created_at),
                            self._format_datetime(created_at),
                        ),
                    )
                    row = self._job_row(job_id)
                    return PlanningJobReservation(created=True, job=self._hydrate_job(row))
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def get(self, job_id: UUID) -> PlanningJob:
        self._require_job_id(job_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection, immediate=False):
                    return self._hydrate_job(self._job_row(job_id))
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def advance(
        self,
        job_id: UUID,
        target_status: PlanningStatus,
        *,
        expected_version: int,
        retryable: bool = False,
    ) -> PlanningJob:
        self._require_job_id(job_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    current = self._hydrate_job(self._job_row(job_id))
                    self._require_version(current, expected_version)
                    if type(retryable) is not bool or (
                        retryable
                        and target_status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}
                    ):
                        self._raise(PlanningJobRepositoryErrorCode.RETRYABLE_FLAG_INVALID)
                    try:
                        transition = PlanningStateMachine.transition(
                            PlanningTransitionCommand(
                                current_status=current.status,
                                target_status=target_status,
                            )
                        )
                    except PlanningTransitionError:
                        self._raise(PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED)
                    if transition.current_status in _TERMINAL_STATUSES:
                        self._raise(PlanningJobRepositoryErrorCode.RESULT_REQUIRED)

                    updated_at = self._now(not_before=current.updated_at)
                    self._update_current_snapshot(
                        current,
                        status=transition.current_status,
                        retryable=retryable,
                        updated_at=updated_at,
                        expected_version=expected_version,
                    )
                    return self._hydrate_job(self._job_row(job_id))
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def record_result(
        self,
        job_id: UUID,
        result: PlanningJobResult,
        *,
        expected_version: int,
    ) -> PlanningJob:
        self._require_job_id(job_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    current = self._hydrate_job(self._job_row(job_id))
                    self._require_version(current, expected_version)
                    if not isinstance(result, PlanningJobResult):
                        self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
                    if not result_matches_request(result, current.request):
                        self._raise(PlanningJobRepositoryErrorCode.RESULT_REQUEST_MISMATCH)
                    try:
                        transition = PlanningStateMachine.transition(
                            PlanningTransitionCommand(
                                current_status=current.status,
                                target_status=result.status,
                            )
                        )
                    except PlanningTransitionError:
                        self._raise(PlanningJobRepositoryErrorCode.TRANSITION_NOT_ALLOWED)

                    updated_at = self._now(not_before=current.updated_at)
                    metadata = _StoredResultMetadata(
                        resolved_destination=result.resolved_destination,
                        violations=result.violations,
                        warnings=result.warnings,
                        uncertainties=result.uncertainties,
                        errors=result.errors,
                        source_ids=tuple(source.source_id for source in result.sources),
                    )
                    metadata_json = self._dump_json(metadata.model_dump(mode="json"))
                    self._insert_sources(current, result.sources)
                    plan_version = self._insert_plan_version(current, result, updated_at)
                    self._database.connection.execute(
                        """
                        UPDATE planning_attempts
                        SET status = ?, retryable = ?, updated_at = ?,
                            current_plan_version = ?, result_metadata_json = ?
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (
                            transition.current_status.value,
                            int(result.retryable),
                            self._format_datetime(updated_at),
                            plan_version,
                            metadata_json,
                            str(current.job_id),
                            current.attempt,
                        ),
                    )
                    self._update_job_row(
                        current,
                        status=transition.current_status,
                        retryable=result.retryable,
                        updated_at=updated_at,
                        expected_version=expected_version,
                    )
                    return self._hydrate_job(self._job_row(job_id))
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def retry(self, job_id: UUID, *, expected_version: int) -> PlanningJob:
        self._require_job_id(job_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    current = self._hydrate_job(self._job_row(job_id))
                    self._require_version(current, expected_version)
                    if current.attempt >= 3:
                        self._raise(PlanningJobRepositoryErrorCode.RETRY_LIMIT_REACHED)
                    if current.status not in {PlanningStatus.PARTIAL, PlanningStatus.FAILED}:
                        self._raise(PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED)
                    if not current.retryable:
                        self._raise(PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED)
                    try:
                        transition = PlanningStateMachine.transition(
                            PlanningTransitionCommand(
                                current_status=current.status,
                                target_status=PlanningStatus.NORMALIZING,
                                trigger=PlanningTransitionTrigger.RETRY,
                                retryable=True,
                            )
                        )
                    except PlanningTransitionError:
                        self._raise(PlanningJobRepositoryErrorCode.RETRY_NOT_ALLOWED)

                    updated_at = self._now(not_before=current.updated_at)
                    trace_id = self._new_identifiers(1)[0]
                    self._database.connection.execute(
                        """
                        INSERT INTO planning_attempts(
                            job_id, attempt, trace_id, status, retryable,
                            started_at, updated_at, current_plan_version,
                            result_metadata_json
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)
                        """,
                        (
                            str(current.job_id),
                            current.attempt + 1,
                            str(trace_id),
                            transition.current_status.value,
                            self._format_datetime(updated_at),
                            self._format_datetime(updated_at),
                        ),
                    )
                    cursor = self._database.connection.execute(
                        """
                        UPDATE planning_jobs
                        SET trace_id = ?, status = ?, attempt = ?, version = version + 1,
                            retryable = 0, updated_at = ?
                        WHERE job_id = ? AND version = ?
                        """,
                        (
                            str(trace_id),
                            transition.current_status.value,
                            current.attempt + 1,
                            self._format_datetime(updated_at),
                            str(current.job_id),
                            expected_version,
                        ),
                    )
                    if cursor.rowcount != 1:
                        self._raise(PlanningJobRepositoryErrorCode.VERSION_CONFLICT)
                    return self._hydrate_job(self._job_row(job_id))
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def delete(self, job_id: UUID) -> None:
        """Delete one job and all job-owned rows through foreign-key cascades."""

        self._require_job_id(job_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    cursor = self._database.connection.execute(
                        "DELETE FROM planning_jobs WHERE job_id = ?",
                        (str(job_id),),
                    )
                    if cursor.rowcount != 1:
                        self._raise(PlanningJobRepositoryErrorCode.JOB_NOT_FOUND)
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def cleanup_expired(self, now: datetime, *, limit: int = 1000) -> int:
        """Delete at most ``limit`` jobs whose 30-day retention window has elapsed."""

        if not isinstance(now, datetime) or now.utcoffset() is None:
            self._raise(PlanningJobRepositoryErrorCode.CLOCK_INVALID)
        if type(limit) is not int or not 1 <= limit <= 1000:
            self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
        cutoff = now.astimezone(UTC)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    rows = self._database.connection.execute(
                        """
                        SELECT job_id, expires_at
                        FROM planning_jobs
                        ORDER BY expires_at, job_id
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                    expired_ids: list[str] = []
                    for row in rows:
                        expires_at = self._datetime(self._text(row, "expires_at"))
                        if expires_at > cutoff:
                            break
                        expired_ids.append(self._text(row, "job_id"))
                    if not expired_ids:
                        return 0
                    placeholders = ", ".join("?" for _ in expired_ids)
                    self._database.connection.execute(
                        f"DELETE FROM planning_jobs WHERE job_id IN ({placeholders})",
                        tuple(expired_ids),
                    )
                    return len(expired_ids)
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    async def record_acceptance(self, record: AcceptanceRecord) -> AcceptanceRecord:
        """Persist one typed, code-only acceptance summary without public exposure."""

        if not isinstance(record, AcceptanceRecord):
            self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
        evidence_json = self._dump_json(
            {
                "check_codes": list(record.evidence.check_codes),
                "limitation_codes": list(record.evidence.limitation_codes),
            }
        )
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    job_row = self._job_row(record.job_id)
                    if record.observed_at < self._datetime(self._text(job_row, "created_at")):
                        self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
                    attempt_row = self._database.connection.execute(
                        """
                        SELECT 1 FROM planning_attempts
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (str(record.job_id), record.attempt),
                    ).fetchone()
                    if attempt_row is None:
                        self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
                    if record.plan_version is not None:
                        version_row = self._database.connection.execute(
                            """
                            SELECT 1 FROM plan_versions
                            WHERE job_id = ? AND version_number = ? AND attempt = ?
                            """,
                            (str(record.job_id), record.plan_version, record.attempt),
                        ).fetchone()
                        if version_row is None:
                            self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)
                    collision = self._database.connection.execute(
                        "SELECT 1 FROM acceptance_records WHERE acceptance_id = ?",
                        (str(record.acceptance_id),),
                    ).fetchone()
                    if collision is not None:
                        self._raise(PlanningJobRepositoryErrorCode.IDENTIFIER_COLLISION)
                    self._database.connection.execute(
                        """
                        INSERT INTO acceptance_records(
                            acceptance_id, job_id, attempt, plan_version, case_id,
                            status, observed_at, environment, evidence_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(record.acceptance_id),
                            str(record.job_id),
                            record.attempt,
                            record.plan_version,
                            record.case_id,
                            record.status.value,
                            self._format_datetime(record.observed_at),
                            record.environment,
                            evidence_json,
                        ),
                    )
                    return record
            except PlanningJobRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError):
                self._raise(PlanningJobRepositoryErrorCode.RESULT_INVALID)

    def _insert_sources(
        self,
        job: PlanningJob,
        sources: tuple[SourceRecord, ...],
    ) -> None:
        for source in sources:
            source_payload = source.model_dump(mode="json")
            self._assert_safe_value(source_payload)
            self._database.connection.execute(
                """
                INSERT INTO source_records(
                    job_id, source_id, attempt, provider, source_type,
                    provider_record_id, fetched_at, valid_until, freshness,
                    reference_url, attributions_json, warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(job.job_id),
                    str(source.source_id),
                    job.attempt,
                    source.provider.value,
                    source.source_type,
                    source.provider_record_id,
                    self._format_datetime(source.fetched_at),
                    (
                        self._format_datetime(source.valid_until)
                        if source.valid_until is not None
                        else None
                    ),
                    source.freshness.value,
                    str(source.reference_url) if source.reference_url is not None else None,
                    self._dump_json(list(source.attributions)),
                    self._dump_json(list(source.warnings)),
                ),
            )

    def _insert_plan_version(
        self,
        job: PlanningJob,
        result: PlanningJobResult,
        created_at: datetime,
    ) -> int | None:
        if result.plan is None:
            return None
        row = self._database.connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS value FROM plan_versions WHERE job_id = ?",
            (str(job.job_id),),
        ).fetchone()
        if row is None:
            raise ValueError("plan_version_query_invalid")
        version_number = self._integer(row, "value") + 1
        plan_json = self._dump_json(result.plan.model_dump(mode="json"))
        self._database.connection.execute(
            """
            INSERT INTO plan_versions(
                job_id, version_number, plan_id, attempt, trace_id,
                status, plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job.job_id),
                version_number,
                str(result.plan.plan_id),
                job.attempt,
                str(job.trace_id),
                result.status.value,
                plan_json,
                self._format_datetime(created_at),
            ),
        )
        for source in result.sources:
            self._database.connection.execute(
                """
                INSERT INTO plan_version_sources(job_id, version_number, source_id)
                VALUES (?, ?, ?)
                """,
                (str(job.job_id), version_number, str(source.source_id)),
            )
        return version_number

    def _update_current_snapshot(
        self,
        current: PlanningJob,
        *,
        status: PlanningStatus,
        retryable: bool,
        updated_at: datetime,
        expected_version: int,
    ) -> None:
        self._database.connection.execute(
            """
            UPDATE planning_attempts
            SET status = ?, retryable = ?, updated_at = ?
            WHERE job_id = ? AND attempt = ?
            """,
            (
                status.value,
                int(retryable),
                self._format_datetime(updated_at),
                str(current.job_id),
                current.attempt,
            ),
        )
        self._update_job_row(
            current,
            status=status,
            retryable=retryable,
            updated_at=updated_at,
            expected_version=expected_version,
        )

    def _update_job_row(
        self,
        current: PlanningJob,
        *,
        status: PlanningStatus,
        retryable: bool,
        updated_at: datetime,
        expected_version: int,
    ) -> None:
        cursor = self._database.connection.execute(
            """
            UPDATE planning_jobs
            SET status = ?, retryable = ?, version = version + 1, updated_at = ?
            WHERE job_id = ? AND version = ?
            """,
            (
                status.value,
                int(retryable),
                self._format_datetime(updated_at),
                str(current.job_id),
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            self._raise(PlanningJobRepositoryErrorCode.VERSION_CONFLICT)

    def _hydrate_job(self, row: sqlite3.Row) -> PlanningJob:
        job_id = self._uuid(self._text(row, "job_id"))
        trace_id = self._uuid(self._text(row, "trace_id"))
        client_request_id = self._uuid(self._text(row, "client_request_id"))
        request = _PLANNING_REQUEST_ADAPTER.validate_python(
            self._load_json(self._text(row, "request_json"))
        )
        fingerprint = RequestFingerprint(digest=self._text(row, "request_fingerprint"))
        if request.client_request_id != client_request_id:
            raise ValueError("stored_client_request_id_mismatch")
        if request_fingerprint(request) != fingerprint:
            raise ValueError("stored_request_fingerprint_mismatch")

        status = PlanningStatus(self._text(row, "status"))
        attempt = self._integer(row, "attempt")
        retryable = self._boolean(row, "retryable")
        created_at = self._datetime(self._text(row, "created_at"))
        updated_at = self._datetime(self._text(row, "updated_at"))
        self._datetime(self._text(row, "expires_at"))
        attempt_row = self._database.connection.execute(
            "SELECT * FROM planning_attempts WHERE job_id = ? AND attempt = ?",
            (str(job_id), attempt),
        ).fetchone()
        if attempt_row is None:
            raise ValueError("stored_attempt_missing")
        if (
            self._uuid(self._text(attempt_row, "trace_id")) != trace_id
            or PlanningStatus(self._text(attempt_row, "status")) is not status
            or self._boolean(attempt_row, "retryable") is not retryable
            or self._datetime(self._text(attempt_row, "updated_at")) != updated_at
        ):
            raise ValueError("stored_attempt_snapshot_mismatch")
        started_at = self._datetime(self._text(attempt_row, "started_at"))
        if started_at > updated_at:
            raise ValueError("stored_attempt_timestamp_invalid")

        metadata_json = self._nullable_text(attempt_row, "result_metadata_json")
        plan_version = self._nullable_integer(attempt_row, "current_plan_version")
        result = self._hydrate_result(
            job_id=job_id,
            trace_id=trace_id,
            attempt=attempt,
            status=status,
            retryable=retryable,
            request=request,
            metadata_json=metadata_json,
            plan_version=plan_version,
        )
        return PlanningJob(
            job_id=job_id,
            trace_id=trace_id,
            client_request_id=client_request_id,
            request_fingerprint=fingerprint,
            request=request,
            status=status,
            attempt=attempt,
            version=self._integer(row, "version"),
            retryable=retryable,
            created_at=created_at,
            updated_at=updated_at,
            result=result,
        )

    def _hydrate_result(
        self,
        *,
        job_id: UUID,
        trace_id: UUID,
        attempt: int,
        status: PlanningStatus,
        retryable: bool,
        request: PlanningRequest,
        metadata_json: str | None,
        plan_version: int | None,
    ) -> PlanningJobResult | None:
        if status not in _TERMINAL_STATUSES:
            if metadata_json is not None or plan_version is not None:
                raise ValueError("stored_nonterminal_result_invalid")
            return None
        if metadata_json is None:
            raise ValueError("stored_terminal_metadata_missing")
        metadata = _StoredResultMetadata.model_validate(self._load_json(metadata_json))
        if len(set(metadata.source_ids)) != len(metadata.source_ids):
            raise ValueError("stored_result_source_duplicate")
        sources = self._hydrate_sources(job_id, attempt, metadata.source_ids)
        plan = self._hydrate_plan(
            job_id=job_id,
            trace_id=trace_id,
            attempt=attempt,
            status=status,
            request=request,
            plan_version=plan_version,
            expected_source_ids=metadata.source_ids,
        )
        return PlanningJobResult(
            status=status,
            resolved_destination=metadata.resolved_destination,
            plan=plan,
            violations=metadata.violations,
            warnings=metadata.warnings,
            uncertainties=metadata.uncertainties,
            sources=sources,
            errors=metadata.errors,
            retryable=retryable,
        )

    def _hydrate_sources(
        self,
        job_id: UUID,
        attempt: int,
        source_ids: tuple[UUID, ...],
    ) -> tuple[SourceRecord, ...]:
        if not source_ids:
            return ()
        placeholders = ", ".join("?" for _ in source_ids)
        rows = self._database.connection.execute(
            f"SELECT * FROM source_records WHERE job_id = ? AND source_id IN ({placeholders})",
            (str(job_id), *(str(source_id) for source_id in source_ids)),
        ).fetchall()
        by_id = {self._uuid(self._text(row, "source_id")): row for row in rows}
        if set(by_id) != set(source_ids):
            raise ValueError("stored_result_source_missing")
        hydrated: list[SourceRecord] = []
        for source_id in source_ids:
            row = by_id[source_id]
            if self._integer(row, "attempt") != attempt:
                raise ValueError("stored_result_source_attempt_mismatch")
            hydrated.append(
                SourceRecord.model_validate(
                    {
                        "source_id": str(source_id),
                        "provider": self._text(row, "provider"),
                        "source_type": self._text(row, "source_type"),
                        "provider_record_id": self._nullable_text(row, "provider_record_id"),
                        "fetched_at": self._text(row, "fetched_at"),
                        "valid_until": self._nullable_text(row, "valid_until"),
                        "freshness": self._text(row, "freshness"),
                        "reference_url": self._nullable_text(row, "reference_url"),
                        "attributions": self._load_json(self._text(row, "attributions_json")),
                        "warnings": self._load_json(self._text(row, "warnings_json")),
                    }
                )
            )
        return tuple(hydrated)

    def _hydrate_plan(
        self,
        *,
        job_id: UUID,
        trace_id: UUID,
        attempt: int,
        status: PlanningStatus,
        request: PlanningRequest,
        plan_version: int | None,
        expected_source_ids: tuple[UUID, ...],
    ) -> PlanningPlan | None:
        if plan_version is None:
            return None
        row = self._database.connection.execute(
            "SELECT * FROM plan_versions WHERE job_id = ? AND version_number = ?",
            (str(job_id), plan_version),
        ).fetchone()
        if row is None:
            raise ValueError("stored_plan_version_missing")
        if (
            self._integer(row, "attempt") != attempt
            or self._uuid(self._text(row, "trace_id")) != trace_id
            or PlanningStatus(self._text(row, "status")) is not status
        ):
            raise ValueError("stored_plan_version_mismatch")
        plan = _PLANNING_PLAN_ADAPTER.validate_python(self._load_json(self._text(row, "plan_json")))
        if isinstance(request, TripPlanRequestV2):
            if not isinstance(plan, TripPlanV2):
                raise ValueError("stored_plan_format_mismatch")
        elif type(plan) is not TripPlan:
            raise ValueError("stored_plan_format_mismatch")
        if self._uuid(self._text(row, "plan_id")) != plan.plan_id:
            raise ValueError("stored_plan_id_mismatch")
        linked_ids = {
            self._uuid(self._text(link, "source_id"))
            for link in self._database.connection.execute(
                """
                SELECT source_id FROM plan_version_sources
                WHERE job_id = ? AND version_number = ?
                """,
                (str(job_id), plan_version),
            ).fetchall()
        }
        if linked_ids != set(expected_source_ids):
            raise ValueError("stored_plan_source_link_mismatch")
        return plan

    def _job_row(self, job_id: UUID) -> sqlite3.Row:
        row = self._database.connection.execute(
            "SELECT * FROM planning_jobs WHERE job_id = ?",
            (str(job_id),),
        ).fetchone()
        if row is None:
            self._raise(PlanningJobRepositoryErrorCode.JOB_NOT_FOUND)
        return cast(sqlite3.Row, row)

    def _new_identifiers(self, count: int) -> tuple[UUID, ...]:
        values: list[UUID] = []
        for _ in range(count):
            identifier = self._id_factory()
            if not isinstance(identifier, UUID):
                self._raise(PlanningJobRepositoryErrorCode.IDENTIFIER_INVALID)
            if identifier in values or self._identifier_exists(identifier):
                self._raise(PlanningJobRepositoryErrorCode.IDENTIFIER_COLLISION)
            values.append(identifier)
        return tuple(values)

    def _identifier_exists(self, identifier: UUID) -> bool:
        value = str(identifier)
        row = self._database.connection.execute(
            """
            SELECT 1 FROM planning_jobs WHERE job_id = ? OR trace_id = ?
            UNION ALL
            SELECT 1 FROM planning_attempts WHERE trace_id = ?
            LIMIT 1
            """,
            (value, value, value),
        ).fetchone()
        return row is not None

    def _now(self, *, not_before: datetime | None = None) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            self._raise(PlanningJobRepositoryErrorCode.CLOCK_INVALID)
        if not_before is not None and value < not_before:
            self._raise(PlanningJobRepositoryErrorCode.CLOCK_INVALID)
        return value

    @staticmethod
    def _require_job_id(job_id: object) -> None:
        if not isinstance(job_id, UUID):
            SqlitePlanningJobRepository._raise(PlanningJobRepositoryErrorCode.JOB_NOT_FOUND)

    @staticmethod
    def _require_version(job: PlanningJob, expected_version: int) -> None:
        if type(expected_version) is not int or expected_version != job.version:
            SqlitePlanningJobRepository._raise(PlanningJobRepositoryErrorCode.VERSION_CONFLICT)

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise ValueError("stored_datetime_invalid")
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError("stored_datetime_invalid")
        return parsed

    @staticmethod
    def _uuid(value: str) -> UUID:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("stored_uuid_not_canonical")
        return parsed

    @staticmethod
    def _text(row: sqlite3.Row, key: str) -> str:
        value = row[key]
        if not isinstance(value, str):
            raise ValueError("stored_text_invalid")
        return value

    @staticmethod
    def _nullable_text(row: sqlite3.Row, key: str) -> str | None:
        value = row[key]
        if value is not None and not isinstance(value, str):
            raise ValueError("stored_text_invalid")
        return value

    @staticmethod
    def _integer(row: sqlite3.Row, key: str) -> int:
        value = row[key]
        if type(value) is not int:
            raise ValueError("stored_integer_invalid")
        return value

    @staticmethod
    def _nullable_integer(row: sqlite3.Row, key: str) -> int | None:
        value = row[key]
        if value is not None and type(value) is not int:
            raise ValueError("stored_integer_invalid")
        return value

    @classmethod
    def _boolean(cls, row: sqlite3.Row, key: str) -> bool:
        value = cls._integer(row, key)
        if value not in {0, 1}:
            raise ValueError("stored_boolean_invalid")
        return bool(value)

    @classmethod
    def _dump_json(cls, value: object) -> str:
        cls._assert_safe_value(value)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def _load_json(cls, value: str) -> object:
        parsed = json.loads(
            value,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("stored_json_constant_invalid")
            ),
        )
        cls._assert_safe_value(parsed)
        return parsed

    @classmethod
    def _assert_safe_value(cls, value: object) -> None:
        if isinstance(value, str):
            if _PRIVATE_MATERIAL.search(value) is not None:
                raise ValueError("private_material_not_allowed")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("stored_json_key_invalid")
                cls._assert_safe_value(key)
                cls._assert_safe_value(item)
            return
        if isinstance(value, list | tuple):
            for item in value:
                cls._assert_safe_value(item)

    @staticmethod
    def _raise(code: PlanningJobRepositoryErrorCode) -> NoReturn:
        raise PlanningJobRepositoryError(code)


class SqliteReplanRepository:
    """SQLite adapter for the independent F-003 replan aggregate."""

    def __init__(
        self,
        database: SqliteDatabase,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        if not isinstance(database, SqliteDatabase):
            raise TypeError("sqlite_database_invalid")
        self._database = database
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4
        self._lock = asyncio.Lock()

    async def reserve(
        self,
        job_id: UUID,
        replan_request_id: UUID,
        command: ReplanCommand,
        *,
        baseline_plan_id: UUID,
        baseline_plan_version: int | None = None,
        expected_job_version: int,
        trace_id: UUID | None = None,
    ) -> ReplanReservation:
        _require_replan_ids(job_id, replan_request_id, baseline_plan_id)
        _require_command(command)
        fingerprint = _command_fingerprint(command)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    existing = self._database.connection.execute(
                        "SELECT * FROM replan_requests WHERE job_id = ? AND replan_request_id = ?",
                        (str(job_id), str(replan_request_id)),
                    ).fetchone()
                    if existing is not None:
                        if existing["request_fingerprint"] != fingerprint.digest:
                            _raise_replan(ReplanRepositoryErrorCode.IDEMPOTENCY_CONFLICT)
                        if UUID(existing["baseline_plan_id"]) != baseline_plan_id:
                            _raise_replan(ReplanRepositoryErrorCode.BASELINE_CONFLICT)
                        return ReplanReservation(False, self._hydrate_replan(existing))
                    trace = trace_id or self._id_factory()
                    _require_replan_ids(trace)
                    self._require_current_job_version(
                        job_id,
                        expected_job_version,
                        captured_job_version=expected_job_version,
                    )
                    current_version_row = self._database.connection.execute(
                        """
                        SELECT current_plan_version FROM planning_attempts
                        WHERE job_id = ? AND attempt = (
                            SELECT attempt FROM planning_jobs WHERE job_id = ?
                        )
                        """,
                        (str(job_id), str(job_id)),
                    ).fetchone()
                    captured_version = (
                        int(current_version_row["current_plan_version"])
                        if current_version_row is not None
                        and current_version_row["current_plan_version"] is not None
                        else None
                    )
                    if baseline_plan_version is None:
                        baseline_plan_version = captured_version
                    if (
                        type(baseline_plan_version) is not int
                        or baseline_plan_version < 1
                        or captured_version != baseline_plan_version
                    ):
                        _raise_replan(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
                    baseline = self._database.connection.execute(
                        """
                        SELECT 1 FROM plan_versions
                        WHERE job_id = ? AND version_number = ? AND plan_id = ?
                        """,
                        (str(job_id), baseline_plan_version, str(baseline_plan_id)),
                    ).fetchone()
                    if baseline is None:
                        _raise_replan(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
                    now = self._now()
                    replan_id = self._next_id()
                    self._database.connection.execute(
                        """
                        INSERT INTO replan_requests(
                            replan_id, job_id, replan_request_id, request_fingerprint,
                            baseline_plan_id, baseline_plan_version, expected_job_version,
                            trace_id, operation, request_json, impact_json, status,
                            aggregate_version, decision_id, result_plan_version, error_code,
                            created_at, updated_at, expires_at, decided_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 1, NULL, NULL, NULL,
                            ?, ?, ?, NULL
                        )
                        """,
                        (
                            str(replan_id),
                            str(job_id),
                            str(replan_request_id),
                            fingerprint.digest,
                            str(baseline_plan_id),
                            baseline_plan_version,
                            expected_job_version,
                            str(trace),
                            command.operation.value,
                            _json_dump(_command_to_obj(command)),
                            ReplanStatus.ANALYZING.value,
                            _format_replan_datetime(now),
                            _format_replan_datetime(now),
                            _format_replan_datetime(now + timedelta(minutes=15)),
                        ),
                    )
                    return ReplanReservation(True, self._hydrate_replan_by_id(replan_id))
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)

    async def get(self, job_id: UUID, replan_id: UUID) -> ReplanRecord:
        _require_replan_ids(job_id, replan_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection, immediate=False):
                    return self._hydrate_replan_by_id(replan_id, job_id=job_id)
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)

    async def record_analysis(
        self,
        job_id: UUID,
        replan_id: UUID,
        impact: ImpactAnalysis,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord:
        _require_replan_ids(job_id, replan_id)
        if not isinstance(impact, ImpactAnalysis):
            _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    row = self._replan_row(replan_id, job_id)
                    _check_replan_version(row, expected_replan_version)
                    if row["status"] != ReplanStatus.ANALYZING.value:
                        _raise_replan(ReplanRepositoryErrorCode.INVALID_STATE)
                    attempt_row = self._database.connection.execute(
                        "SELECT attempt, trace_id FROM planning_jobs WHERE job_id = ?",
                        (str(job_id),),
                    ).fetchone()
                    if attempt_row is None:
                        _raise_replan(ReplanRepositoryErrorCode.JOB_NOT_FOUND)
                    decision_id = self._next_id()
                    now = self._now()
                    decision_status = (
                        ReplanDecisionStatus.AUTO_APPROVED
                        if impact.disposition is ImpactDisposition.AUTO
                        else ReplanDecisionStatus.REJECTED
                        if impact.disposition is ImpactDisposition.REJECT
                        else ReplanDecisionStatus.PENDING
                    )
                    decision_created = _format_replan_datetime(now)
                    decision_decided = (
                        decision_created
                        if decision_status is not ReplanDecisionStatus.PENDING
                        else None
                    )
                    self._database.connection.execute(
                        """
                        INSERT INTO decision_records(
                            decision_id, job_id, attempt, trace_id, plan_version, kind, status,
                            proposal_json, validation_json, user_choice_json, created_at, decided_at
                        ) VALUES (?, ?, ?, ?, ?, 'replan', ?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            str(decision_id),
                            str(job_id),
                            int(attempt_row["attempt"]),
                            str(row["trace_id"]),
                            int(row["baseline_plan_version"]),
                            decision_status.value,
                            _json_dump(_command_to_obj(_command_from_json(row["request_json"]))),
                            _json_dump(_impact_to_obj(impact)),
                            decision_created,
                            decision_decided,
                        ),
                    )
                    next_status = (
                        ReplanStatus.AWAITING_CONFIRMATION
                        if impact.disposition is ImpactDisposition.CONFIRM
                        else ReplanStatus.REPLANNING
                        if impact.disposition is ImpactDisposition.AUTO
                        else ReplanStatus.REJECTED
                    )
                    expires_at = (
                        _format_replan_datetime(now + timedelta(minutes=15))
                        if next_status is ReplanStatus.AWAITING_CONFIRMATION
                        else row["expires_at"]
                    )
                    self._database.connection.execute(
                        """
                        UPDATE replan_requests
                        SET impact_json = ?, status = ?, aggregate_version = aggregate_version + 1,
                            decision_id = ?, updated_at = ?, expires_at = ?, decided_at = ?
                        WHERE replan_id = ? AND job_id = ? AND aggregate_version = ?
                        """,
                        (
                            _json_dump(_impact_to_obj(impact)),
                            next_status.value,
                            str(decision_id),
                            decision_created,
                            expires_at,
                            decision_decided,
                            str(replan_id),
                            str(job_id),
                            expected_replan_version,
                        ),
                    )
                    if self._database.connection.execute("SELECT changes()").fetchone()[0] != 1:
                        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)
                    return self._hydrate_replan_by_id(replan_id, job_id=job_id)
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)

    async def decide(
        self,
        job_id: UUID,
        replan_id: UUID,
        choice: ReplanChoice,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        _require_replan_ids(job_id, replan_id)
        if not isinstance(choice, ReplanChoice):
            raise TypeError("replan_choice_invalid")
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    row = self._replan_row(replan_id, job_id)
                    decision_id = row["decision_id"]
                    if decision_id is None:
                        _raise_replan(ReplanRepositoryErrorCode.DECISION_CONFLICT)
                    existing_decision = self._database.connection.execute(
                        """
                        SELECT status, user_choice_json FROM decision_records
                        WHERE decision_id = ?
                        """,
                        (decision_id,),
                    ).fetchone()
                    if existing_decision is None:
                        _raise_replan(ReplanRepositoryErrorCode.DECISION_CONFLICT)
                    if existing_decision["user_choice_json"]:
                        existing_choice = ReplanChoice(
                            json.loads(existing_decision["user_choice_json"])["choice"]
                        )
                        if existing_choice is choice:
                            return self._hydrate_replan(row)
                        _raise_replan(ReplanRepositoryErrorCode.DECISION_CONFLICT)
                    _check_replan_version(row, expected_replan_version)
                    if row["status"] != ReplanStatus.AWAITING_CONFIRMATION.value:
                        _raise_replan(ReplanRepositoryErrorCode.INVALID_STATE)
                    self._require_current_job_version(
                        job_id,
                        expected_job_version,
                        captured_job_version=int(row["expected_job_version"]),
                    )
                    now = self._now()
                    if now >= _parse_replan_datetime(row["expires_at"]):
                        decided = _format_replan_datetime(now)
                        self._database.connection.execute(
                            """
                            UPDATE decision_records
                            SET status = ?, decided_at = ? WHERE decision_id = ?
                            """,
                            (ReplanDecisionStatus.EXPIRED.value, decided, decision_id),
                        )
                        self._database.connection.execute(
                            """
                            UPDATE replan_requests
                            SET status = ?, error_code = ?,
                                aggregate_version = aggregate_version + 1,
                                updated_at = ?, decided_at = ?
                            WHERE replan_id = ? AND job_id = ? AND aggregate_version = ?
                            """,
                            (
                                ReplanStatus.EXPIRED.value,
                                ReplanRepositoryErrorCode.CONFIRMATION_EXPIRED.value,
                                decided,
                                decided,
                                str(replan_id),
                                str(job_id),
                                expected_replan_version,
                            ),
                        )
                        return self._hydrate_replan_by_id(replan_id, job_id=job_id)
                    decision_status = (
                        ReplanDecisionStatus.APPROVED
                        if choice is ReplanChoice.APPROVE
                        else ReplanDecisionStatus.CANCELLED
                    )
                    next_status = (
                        ReplanStatus.REPLANNING
                        if choice is ReplanChoice.APPROVE
                        else ReplanStatus.CANCELLED
                    )
                    decided = _format_replan_datetime(now)
                    self._database.connection.execute(
                        """
                        UPDATE decision_records
                        SET status = ?, user_choice_json = ?, decided_at = ?
                        WHERE decision_id = ?
                        """,
                        (
                            decision_status.value,
                            _json_dump({"choice": choice.value}),
                            decided,
                            decision_id,
                        ),
                    )
                    self._database.connection.execute(
                        """
                        UPDATE replan_requests
                        SET status = ?, aggregate_version = aggregate_version + 1,
                            updated_at = ?, decided_at = ?
                        WHERE replan_id = ? AND job_id = ? AND aggregate_version = ?
                        """,
                        (
                            next_status.value,
                            decided,
                            decided,
                            str(replan_id),
                            str(job_id),
                            expected_replan_version,
                        ),
                    )
                    if self._database.connection.execute("SELECT changes()").fetchone()[0] != 1:
                        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)
                    return self._hydrate_replan_by_id(replan_id, job_id=job_id)
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)

    async def begin_execution(
        self,
        job_id: UUID,
        replan_id: UUID,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanRecord:
        _require_replan_ids(job_id, replan_id)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection, immediate=False):
                    row = self._replan_row(replan_id, job_id)
                    _check_replan_version(row, expected_replan_version)
                    self._require_current_job_version(
                        job_id,
                        expected_job_version,
                        captured_job_version=int(row["expected_job_version"]),
                    )
                    if row["status"] not in {
                        ReplanStatus.REPLANNING.value,
                    }:
                        _raise_replan(ReplanRepositoryErrorCode.INVALID_STATE)
                    decision = self._database.connection.execute(
                        "SELECT status FROM decision_records WHERE decision_id = ?",
                        (row["decision_id"],),
                    ).fetchone()
                    if decision is None or decision["status"] not in {
                        ReplanDecisionStatus.AUTO_APPROVED.value,
                        ReplanDecisionStatus.APPROVED.value,
                    }:
                        _raise_replan(ReplanRepositoryErrorCode.DECISION_CONFLICT)
                    return self._hydrate_replan(row)
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)

    async def record_outcome(
        self,
        job_id: UUID,
        replan_id: UUID,
        outcome: ReplanOutcome,
        *,
        expected_replan_version: int,
    ) -> ReplanRecord:
        _require_replan_ids(job_id, replan_id)
        if not isinstance(outcome, ReplanOutcome):
            _raise_replan(ReplanRepositoryErrorCode.OUTCOME_INVALID)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    row = self._replan_row(replan_id, job_id)
                    _check_replan_version(row, expected_replan_version)
                    if row["status"] not in {
                        ReplanStatus.ANALYZING.value,
                        ReplanStatus.REPLANNING.value,
                    }:
                        _raise_replan(ReplanRepositoryErrorCode.INVALID_STATE)
                    now = _format_replan_datetime(self._now())
                    cursor = self._database.connection.execute(
                        """
                        UPDATE replan_requests
                        SET status = ?, error_code = ?, aggregate_version = aggregate_version + 1,
                            updated_at = ?
                        WHERE replan_id = ? AND job_id = ? AND aggregate_version = ?
                        """,
                        (
                            outcome.status.value,
                            outcome.error_code,
                            now,
                            str(replan_id),
                            str(job_id),
                            expected_replan_version,
                        ),
                    )
                    if cursor.rowcount != 1:
                        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)
                    return self._hydrate_replan_by_id(replan_id, job_id=job_id)
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.OUTCOME_INVALID)

    async def commit(
        self,
        job_id: UUID,
        replan_id: UUID,
        commit: ReplanCommit,
        *,
        expected_replan_version: int,
        expected_job_version: int,
    ) -> ReplanCommitResult:
        _require_replan_ids(job_id, replan_id)
        if not isinstance(commit, ReplanCommit):
            _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
        async with self._lock:
            try:
                with sqlite_transaction(self._database.connection):
                    row = self._replan_row(replan_id, job_id)
                    _check_replan_version(row, expected_replan_version)
                    if row["status"] != ReplanStatus.REPLANNING.value:
                        _raise_replan(ReplanRepositoryErrorCode.INVALID_STATE)
                    self._require_current_job_version(
                        job_id,
                        expected_job_version,
                        captured_job_version=int(row["expected_job_version"]),
                    )
                    planning = SqlitePlanningJobRepository(
                        self._database, clock=self._clock, id_factory=self._id_factory
                    )
                    current = planning._hydrate_job(planning._job_row(job_id))
                    if (
                        current.result is None
                        or current.result.plan is None
                        or current.result.plan.plan_id != UUID(row["baseline_plan_id"])
                        or commit.change_set.baseline_plan_id != UUID(row["baseline_plan_id"])
                    ):
                        _raise_replan(ReplanRepositoryErrorCode.BASELINE_CONFLICT)
                    attempt = self._database.connection.execute(
                        """
                        SELECT current_plan_version FROM planning_attempts
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (str(job_id), current.attempt),
                    ).fetchone()
                    if attempt is None or int(attempt["current_plan_version"] or 0) != int(
                        row["baseline_plan_version"]
                    ):
                        _raise_replan(ReplanRepositoryErrorCode.BASELINE_CONFLICT)
                    if not result_matches_request(commit.result, current.request):
                        _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
                    decision = self._database.connection.execute(
                        "SELECT status FROM decision_records WHERE decision_id = ?",
                        (row["decision_id"],),
                    ).fetchone()
                    if decision is None or decision["status"] not in {
                        ReplanDecisionStatus.AUTO_APPROVED.value,
                        ReplanDecisionStatus.APPROVED.value,
                    }:
                        _raise_replan(ReplanRepositoryErrorCode.DECISION_CONFLICT)

                    now = self._now()
                    self._backfill_legacy_replan_lineage(
                        current, plan_version=int(attempt["current_plan_version"])
                    )
                    self._insert_replan_sources(current, commit.result.sources)
                    plan_version = self._insert_replan_plan_version(
                        current,
                        commit,
                        trace_id=current.trace_id,
                        created_at=now,
                    )
                    metadata = _StoredResultMetadata(
                        resolved_destination=commit.result.resolved_destination,
                        violations=commit.result.violations,
                        warnings=commit.result.warnings,
                        uncertainties=commit.result.uncertainties,
                        errors=commit.result.errors,
                        source_ids=tuple(source.source_id for source in commit.result.sources),
                    )
                    metadata_json = _json_dump(metadata.model_dump(mode="json"))
                    formatted_now = _format_replan_datetime(now)
                    self._database.connection.execute(
                        """
                        INSERT INTO plan_version_lineage(
                            job_id, child_version, parent_version, replan_id,
                            decision_id, change_set_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(job_id),
                            plan_version,
                            int(row["baseline_plan_version"]),
                            str(replan_id),
                            row["decision_id"],
                            _json_dump(
                                {
                                    "change_set": _change_set_to_obj(commit.change_set),
                                    "result_metadata": metadata.model_dump(mode="json"),
                                    "retryable": commit.result.retryable,
                                }
                            ),
                            formatted_now,
                        ),
                    )
                    self._database.connection.execute(
                        """
                        UPDATE planning_attempts
                        SET status = ?, retryable = ?, updated_at = ?,
                            current_plan_version = ?, result_metadata_json = ?
                        WHERE job_id = ? AND attempt = ?
                        """,
                        (
                            commit.result.status.value,
                            int(commit.result.retryable),
                            formatted_now,
                            plan_version,
                            metadata_json,
                            str(job_id),
                            current.attempt,
                        ),
                    )
                    job_cursor = self._database.connection.execute(
                        """
                        UPDATE planning_jobs
                        SET status = ?, retryable = ?, version = version + 1, updated_at = ?
                        WHERE job_id = ? AND version = ?
                        """,
                        (
                            commit.result.status.value,
                            int(commit.result.retryable),
                            formatted_now,
                            str(job_id),
                            expected_job_version,
                        ),
                    )
                    if job_cursor.rowcount != 1:
                        _raise_replan(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
                    replan_cursor = self._database.connection.execute(
                        """
                        UPDATE replan_requests
                        SET status = 'completed', result_plan_version = ?, error_code = NULL,
                            aggregate_version = aggregate_version + 1, updated_at = ?
                        WHERE replan_id = ? AND job_id = ? AND aggregate_version = ?
                        """,
                        (
                            plan_version,
                            formatted_now,
                            str(replan_id),
                            str(job_id),
                            expected_replan_version,
                        ),
                    )
                    if replan_cursor.rowcount != 1:
                        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)
                    completed = self._hydrate_replan_by_id(replan_id, job_id=job_id)
                    return ReplanCommitResult(
                        replan=completed,
                        job_version=expected_job_version + 1,
                        plan_version=plan_version,
                    )
            except ReplanRepositoryError:
                raise
            except (sqlite3.Error, RuntimeError, TypeError, ValueError, KeyError):
                _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)

    def _require_current_job_version(
        self,
        job_id: UUID,
        expected_job_version: int,
        *,
        captured_job_version: int,
    ) -> None:
        if (
            type(expected_job_version) is not int
            or type(captured_job_version) is not int
            or expected_job_version < 1
            or expected_job_version != captured_job_version
        ):
            _raise_replan(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)
        row = self._database.connection.execute(
            "SELECT version FROM planning_jobs WHERE job_id = ?", (str(job_id),)
        ).fetchone()
        if row is None:
            _raise_replan(ReplanRepositoryErrorCode.JOB_NOT_FOUND)
        if int(row["version"]) != captured_job_version:
            _raise_replan(ReplanRepositoryErrorCode.JOB_VERSION_CONFLICT)

    def _insert_replan_sources(self, job: PlanningJob, sources: tuple[SourceRecord, ...]) -> None:
        planning = SqlitePlanningJobRepository(
            self._database, clock=self._clock, id_factory=self._id_factory
        )
        current_sources = (
            {source.source_id: source for source in job.result.sources}
            if job.result is not None
            else {}
        )
        for source in sources:
            existing = self._database.connection.execute(
                "SELECT 1 FROM source_records WHERE job_id = ? AND source_id = ?",
                (str(job.job_id), str(source.source_id)),
            ).fetchone()
            if existing is not None:
                if current_sources.get(source.source_id) != source:
                    _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
                continue
            planning._insert_sources(job, (source,))

    def _insert_replan_plan_version(
        self,
        job: PlanningJob,
        commit: ReplanCommit,
        *,
        trace_id: UUID,
        created_at: datetime,
    ) -> int:
        row = self._database.connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS value FROM plan_versions WHERE job_id = ?",
            (str(job.job_id),),
        ).fetchone()
        if row is None:
            _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
        version_number = int(row["value"]) + 1
        plan = commit.result.plan
        if plan is None:
            _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
        self._database.connection.execute(
            """
            INSERT INTO plan_versions(
                job_id, version_number, plan_id, attempt, trace_id,
                status, plan_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(job.job_id),
                version_number,
                str(plan.plan_id),
                job.attempt,
                str(trace_id),
                commit.result.status.value,
                _json_dump(plan.model_dump(mode="json")),
                _format_replan_datetime(created_at),
            ),
        )
        for source in commit.result.sources:
            self._database.connection.execute(
                """
                INSERT INTO plan_version_sources(job_id, version_number, source_id)
                VALUES (?, ?, ?)
                """,
                (str(job.job_id), version_number, str(source.source_id)),
            )
        return version_number

    def _replan_row(self, replan_id: UUID, job_id: UUID) -> sqlite3.Row:
        row = self._database.connection.execute(
            "SELECT * FROM replan_requests WHERE replan_id = ? AND job_id = ?",
            (str(replan_id), str(job_id)),
        ).fetchone()
        if row is None:
            _raise_replan(ReplanRepositoryErrorCode.REPLAN_NOT_FOUND)
        return cast(sqlite3.Row, row)

    def _hydrate_replan_by_id(self, replan_id: UUID, *, job_id: UUID | None = None) -> ReplanRecord:
        if job_id is None:
            row = self._database.connection.execute(
                "SELECT * FROM replan_requests WHERE replan_id = ?", (str(replan_id),)
            ).fetchone()
            if row is None:
                _raise_replan(ReplanRepositoryErrorCode.REPLAN_NOT_FOUND)
        else:
            row = self._replan_row(replan_id, job_id)
        return self._hydrate_replan(row)

    def _hydrate_replan(self, row: sqlite3.Row) -> ReplanRecord:
        command = _command_from_json(row["request_json"])
        impact = _impact_from_json(row["impact_json"]) if row["impact_json"] else None
        change_set = None
        result = None
        if row["result_plan_version"] is not None:
            historical_metadata = None
            historical_retryable = None
            lineage = self._database.connection.execute(
                """
                SELECT change_set_json FROM plan_version_lineage
                WHERE job_id = ? AND child_version = ? AND replan_id = ?
                """,
                (row["job_id"], row["result_plan_version"], row["replan_id"]),
            ).fetchone()
            if lineage is not None:
                change_set, historical_metadata, historical_retryable = _replan_lineage_from_json(
                    lineage["change_set_json"]
                )
            planning = SqlitePlanningJobRepository(
                self._database, clock=self._clock, id_factory=self._id_factory
            )
            current = planning._hydrate_job(planning._job_row(UUID(row["job_id"])))
            if current.result is None:
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
            plan_version = int(row["result_plan_version"])
            plan_row = self._database.connection.execute(
                "SELECT * FROM plan_versions WHERE job_id = ? AND version_number = ?",
                (row["job_id"], plan_version),
            ).fetchone()
            if plan_row is None:
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
            linked_source_ids = tuple(
                UUID(link["source_id"])
                for link in self._database.connection.execute(
                    """
                    SELECT source_id FROM plan_version_sources
                    WHERE job_id = ? AND version_number = ? ORDER BY source_id
                    """,
                    (row["job_id"], plan_version),
                ).fetchall()
            )
            metadata = historical_metadata or _StoredResultMetadata(
                resolved_destination=current.result.resolved_destination,
                violations=current.result.violations,
                warnings=current.result.warnings,
                uncertainties=current.result.uncertainties,
                errors=current.result.errors,
                source_ids=linked_source_ids,
            )
            if historical_metadata is None and (
                current.result.plan is None
                or current.result.plan.plan_id != UUID(plan_row["plan_id"])
            ):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
            source_ids = metadata.source_ids
            if set(source_ids) != set(linked_source_ids):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
            plan_status = PlanningStatus(plan_row["status"])
            result = PlanningJobResult(
                status=plan_status,
                resolved_destination=metadata.resolved_destination,
                plan=planning._hydrate_plan(
                    job_id=UUID(row["job_id"]),
                    trace_id=UUID(plan_row["trace_id"]),
                    attempt=int(plan_row["attempt"]),
                    status=plan_status,
                    request=current.request,
                    plan_version=plan_version,
                    expected_source_ids=source_ids,
                ),
                violations=metadata.violations,
                warnings=metadata.warnings,
                uncertainties=metadata.uncertainties,
                sources=planning._hydrate_sources(
                    UUID(row["job_id"]), int(plan_row["attempt"]), source_ids
                ),
                errors=metadata.errors,
                retryable=(
                    historical_retryable
                    if historical_retryable is not None
                    else current.result.retryable
                ),
            )
        decision = None
        if row["decision_id"]:
            drow = self._database.connection.execute(
                "SELECT * FROM decision_records WHERE decision_id = ?", (row["decision_id"],)
            ).fetchone()
            if drow is not None and impact is not None:
                choice = None
                if drow["user_choice_json"]:
                    choice = ReplanChoice(json.loads(drow["user_choice_json"])["choice"])
                decision = ReplanDecisionRecord(
                    decision_id=UUID(drow["decision_id"]),
                    job_id=UUID(drow["job_id"]),
                    attempt=int(drow["attempt"]),
                    trace_id=UUID(drow["trace_id"]),
                    baseline_plan_version=int(drow["plan_version"] or row["baseline_plan_version"]),
                    kind=str(drow["kind"]),
                    status=ReplanDecisionStatus(drow["status"]),
                    command=command,
                    impact=impact,
                    choice=choice,
                    created_at=_parse_replan_datetime(drow["created_at"]),
                    decided_at=(
                        _parse_replan_datetime(drow["decided_at"]) if drow["decided_at"] else None
                    ),
                )
        return ReplanRecord(
            replan_id=UUID(row["replan_id"]),
            job_id=UUID(row["job_id"]),
            replan_request_id=UUID(row["replan_request_id"]),
            request_fingerprint=RequestFingerprint(row["request_fingerprint"]),
            baseline_plan_id=UUID(row["baseline_plan_id"]),
            baseline_plan_version=int(row["baseline_plan_version"]),
            expected_job_version=int(row["expected_job_version"]),
            trace_id=UUID(row["trace_id"]),
            operation=ReplanOperation(row["operation"]),
            command=command,
            impact=impact,
            status=ReplanStatus(row["status"]),
            aggregate_version=int(row["aggregate_version"]),
            decision=decision,
            result_plan_version=(
                int(row["result_plan_version"]) if row["result_plan_version"] is not None else None
            ),
            result=result,
            change_set=change_set,
            error_code=row["error_code"],
            created_at=_parse_replan_datetime(row["created_at"]),
            updated_at=_parse_replan_datetime(row["updated_at"]),
            expires_at=_parse_replan_datetime(row["expires_at"]),
            decided_at=(_parse_replan_datetime(row["decided_at"]) if row["decided_at"] else None),
        )

    def _next_id(self) -> UUID:
        identifier = self._id_factory()
        _require_replan_ids(identifier)
        return identifier

    def _backfill_legacy_replan_lineage(self, current: PlanningJob, *, plan_version: int) -> None:
        if current.result is None:
            _raise_replan(ReplanRepositoryErrorCode.COMMIT_INVALID)
        metadata = _StoredResultMetadata(
            resolved_destination=current.result.resolved_destination,
            violations=current.result.violations,
            warnings=current.result.warnings,
            uncertainties=current.result.uncertainties,
            errors=current.result.errors,
            source_ids=tuple(source.source_id for source in current.result.sources),
        )
        rows = self._database.connection.execute(
            """
            SELECT replan_id, change_set_json FROM plan_version_lineage
            WHERE job_id = ? AND child_version = ?
            """,
            (str(current.job_id), plan_version),
        ).fetchall()
        for lineage in rows:
            payload = json.loads(lineage["change_set_json"])
            if not isinstance(payload, dict):
                _raise_replan(ReplanRepositoryErrorCode.JSON_INVALID)
            if "change_set" in payload:
                continue
            change_set = _change_set_from_obj(payload)
            self._database.connection.execute(
                """
                UPDATE plan_version_lineage SET change_set_json = ?
                WHERE job_id = ? AND child_version = ? AND replan_id = ?
                """,
                (
                    _json_dump(
                        {
                            "change_set": _change_set_to_obj(change_set),
                            "result_metadata": metadata.model_dump(mode="json"),
                            "retryable": current.result.retryable,
                        }
                    ),
                    str(current.job_id),
                    plan_version,
                    lineage["replan_id"],
                ),
            )

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("replan_clock_invalid")
        return now


def _require_replan_ids(*identifiers: UUID) -> None:
    if any(not isinstance(identifier, UUID) for identifier in identifiers):
        raise ReplanRepositoryError(ReplanRepositoryErrorCode.IDENTIFIER_INVALID)


def _require_command(command: ReplanCommand) -> None:
    if not isinstance(
        command, (ReplaceActivity, DeleteActivity, AdjustActivityTime, ReorderActivities)
    ):
        raise ReplanRepositoryError(ReplanRepositoryErrorCode.JSON_INVALID)


def _raise_replan(code: ReplanRepositoryErrorCode) -> NoReturn:
    raise ReplanRepositoryError(code)


def _check_replan_version(row: sqlite3.Row, expected: int) -> None:
    if type(expected) is not int or expected < 1:
        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)
    if int(row["aggregate_version"]) != expected:
        _raise_replan(ReplanRepositoryErrorCode.VERSION_CONFLICT)


def _command_fingerprint(command: ReplanCommand) -> RequestFingerprint:
    return RequestFingerprint(
        hashlib.sha256(_json_dump(_command_to_obj(command)).encode("utf-8")).hexdigest()
    )


def _command_to_obj(command: ReplanCommand) -> dict[str, object]:
    if isinstance(command, ReplaceActivity):
        return {
            "operation": command.operation.value,
            "target_activity_id": str(command.target_activity_id),
            "replacement_categories": list(command.replacement_categories),
            "reason_code": command.reason_code,
        }
    if isinstance(command, DeleteActivity):
        return {
            "operation": command.operation.value,
            "target_activity_id": str(command.target_activity_id),
            "reason_code": command.reason_code,
        }
    if isinstance(command, AdjustActivityTime):
        return {
            "operation": command.operation.value,
            "target_activity_id": str(command.target_activity_id),
            "start_time": command.start_time.isoformat(),
            "end_time": command.end_time.isoformat(),
            "reason_code": command.reason_code,
        }
    return {
        "operation": command.operation.value,
        "local_date": command.local_date.isoformat(),
        "ordered_activity_ids": [str(value) for value in command.ordered_activity_ids],
        "reason_code": command.reason_code,
    }


def _command_from_json(raw: str) -> ReplanCommand:
    payload = json.loads(raw)
    operation = ReplanOperation(payload["operation"])
    if operation is ReplanOperation.REPLACE_ACTIVITY:
        return ReplaceActivity(
            UUID(payload["target_activity_id"]),
            tuple(payload["replacement_categories"]),
            payload.get("reason_code"),
        )
    if operation is ReplanOperation.DELETE_ACTIVITY:
        return DeleteActivity(UUID(payload["target_activity_id"]), payload.get("reason_code"))
    if operation is ReplanOperation.ADJUST_ACTIVITY_TIME:
        return AdjustActivityTime(
            UUID(payload["target_activity_id"]),
            time.fromisoformat(payload["start_time"]),
            time.fromisoformat(payload["end_time"]),
            payload.get("reason_code"),
        )
    return ReorderActivities(
        date.fromisoformat(payload["local_date"]),
        tuple(UUID(value) for value in payload["ordered_activity_ids"]),
        payload.get("reason_code"),
    )


def _impact_to_obj(impact: ImpactAnalysis) -> dict[str, object]:
    return {
        "categories": [value.value for value in impact.categories],
        "disposition": impact.disposition.value,
        "direct_refs": [str(value) for value in impact.direct_refs],
        "transitive_refs": [str(value) for value in impact.transitive_refs],
        "affected_dates": [value.isoformat() for value in impact.affected_dates],
        "route_refs": [str(value) for value in impact.route_refs],
        "source_actions": [
            {
                "source_id": str(value.source_id),
                "action": value.action.value,
                "freshness": value.freshness.value,
                "reason": value.reason.value,
            }
            for value in impact.source_actions
        ],
        "required_validations": list(impact.required_validations),
        "confirmation_required": impact.confirmation_required,
    }


def _impact_from_json(raw: str) -> ImpactAnalysis:
    payload = json.loads(raw)
    return ImpactAnalysis(
        categories=tuple(ImpactCategory(value) for value in payload["categories"]),
        disposition=ImpactDisposition(payload["disposition"]),
        direct_refs=tuple(UUID(value) for value in payload["direct_refs"]),
        transitive_refs=tuple(UUID(value) for value in payload["transitive_refs"]),
        affected_dates=tuple(date.fromisoformat(value) for value in payload["affected_dates"]),
        route_refs=tuple(UUID(value) for value in payload["route_refs"]),
        source_actions=tuple(
            SourceActionRecord(
                source_id=UUID(value["source_id"]),
                action=SourceAction(value["action"]),
                freshness=DataFreshness(value["freshness"]),
                reason=SourceActionReason(value["reason"]),
            )
            for value in payload["source_actions"]
        ),
        required_validations=tuple(payload["required_validations"]),
        confirmation_required=bool(payload["confirmation_required"]),
    )


def _change_set_to_obj(change_set: PlanChangeSet) -> dict[str, object]:
    return {
        "baseline_plan_id": str(change_set.baseline_plan_id),
        "result_plan_id": str(change_set.result_plan_id),
        "added_refs": [str(value) for value in change_set.added_refs],
        "removed_refs": [str(value) for value in change_set.removed_refs],
        "changed_refs": [str(value) for value in change_set.changed_refs],
        "added_origins": [[str(added), str(origin)] for added, origin in change_set.added_origins],
        "change_codes": list(change_set.change_codes),
    }


def _change_set_from_json(raw: str) -> PlanChangeSet:
    payload = json.loads(raw)
    return _change_set_from_obj(payload)


def _change_set_from_obj(payload: object) -> PlanChangeSet:
    if not isinstance(payload, dict):
        raise ValueError("replan_change_set_invalid")
    return PlanChangeSet(
        baseline_plan_id=UUID(payload["baseline_plan_id"]),
        result_plan_id=UUID(payload["result_plan_id"]),
        added_refs=tuple(UUID(value) for value in payload["added_refs"]),
        removed_refs=tuple(UUID(value) for value in payload["removed_refs"]),
        changed_refs=tuple(UUID(value) for value in payload["changed_refs"]),
        added_origins=tuple((UUID(value[0]), UUID(value[1])) for value in payload["added_origins"]),
        change_codes=tuple(payload["change_codes"]),
    )


def _replan_lineage_from_json(
    raw: str,
) -> tuple[PlanChangeSet, _StoredResultMetadata | None, bool | None]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("replan_lineage_invalid")
    if "change_set" not in payload:
        return _change_set_from_obj(payload), None, None
    if set(payload) != {"change_set", "result_metadata", "retryable"}:
        raise ValueError("replan_lineage_invalid")
    retryable = payload["retryable"]
    if type(retryable) is not bool:
        raise ValueError("replan_lineage_retryable_invalid")
    return (
        _change_set_from_obj(payload["change_set"]),
        _StoredResultMetadata.model_validate(payload["result_metadata"]),
        retryable,
    )


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_replan_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_replan_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("replan_timestamp_invalid")
    return parsed
