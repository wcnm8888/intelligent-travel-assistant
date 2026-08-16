"""SQLite implementation of the application-owned planning-job repository port."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import NoReturn, cast
from uuid import UUID, uuid4

from pydantic import Field

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
    PlanningStatus,
    ResolvedDestination,
    SourceRecord,
    TripPlan,
    TripPlanRequest,
    Uncertainty,
)
from intelligent_travel_assistant.contracts.base import ContractModel

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

    async def get_or_create(self, request: TripPlanRequest) -> PlanningJobReservation:
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
        request = TripPlanRequest.model_validate(self._load_json(self._text(row, "request_json")))
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
        plan_version: int | None,
        expected_source_ids: tuple[UUID, ...],
    ) -> TripPlan | None:
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
        plan = TripPlan.model_validate(self._load_json(self._text(row, "plan_json")))
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
