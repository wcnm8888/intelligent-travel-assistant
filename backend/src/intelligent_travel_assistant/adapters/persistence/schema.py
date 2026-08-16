"""Initial F-002 SQLite schema statements."""

from __future__ import annotations

INITIAL_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE planning_jobs (
        job_id TEXT PRIMARY KEY CHECK (length(job_id) = 36 AND job_id = lower(job_id)),
        trace_id TEXT NOT NULL CHECK (length(trace_id) = 36 AND trace_id = lower(trace_id)),
        client_request_id TEXT NOT NULL CHECK (
            length(client_request_id) = 36 AND client_request_id = lower(client_request_id)
        ),
        request_fingerprint TEXT NOT NULL CHECK (
            length(request_fingerprint) = 64 AND request_fingerprint = lower(request_fingerprint)
        ),
        request_json TEXT NOT NULL CHECK (length(request_json) > 0),
        status TEXT NOT NULL CHECK (status IN (
            'draft', 'normalizing', 'needs_input', 'collecting', 'planning',
            'enriching_routes', 'validating', 'ready', 'partial', 'conflict', 'failed'
        )),
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        version INTEGER NOT NULL CHECK (version >= 1),
        retryable INTEGER NOT NULL CHECK (retryable IN (0, 1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE plan_versions (
        job_id TEXT NOT NULL,
        version_number INTEGER NOT NULL CHECK (version_number >= 1),
        plan_id TEXT NOT NULL CHECK (length(plan_id) = 36 AND plan_id = lower(plan_id)),
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        trace_id TEXT NOT NULL CHECK (length(trace_id) = 36 AND trace_id = lower(trace_id)),
        status TEXT NOT NULL CHECK (status IN ('ready', 'partial', 'conflict')),
        plan_json TEXT NOT NULL CHECK (length(plan_json) > 0),
        created_at TEXT NOT NULL,
        PRIMARY KEY (job_id, version_number),
        UNIQUE (job_id, plan_id),
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE planning_attempts (
        job_id TEXT NOT NULL,
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        trace_id TEXT NOT NULL CHECK (length(trace_id) = 36 AND trace_id = lower(trace_id)),
        status TEXT NOT NULL CHECK (status IN (
            'draft', 'normalizing', 'needs_input', 'collecting', 'planning',
            'enriching_routes', 'validating', 'ready', 'partial', 'conflict', 'failed'
        )),
        retryable INTEGER NOT NULL CHECK (retryable IN (0, 1)),
        started_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        current_plan_version INTEGER,
        result_metadata_json TEXT CHECK (
            result_metadata_json IS NULL OR length(result_metadata_json) > 0
        ),
        PRIMARY KEY (job_id, attempt),
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE source_records (
        job_id TEXT NOT NULL,
        source_id TEXT NOT NULL CHECK (length(source_id) = 36 AND source_id = lower(source_id)),
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        provider TEXT NOT NULL CHECK (
            provider IN ('deepseek', 'amap', 'qweather', 'user', 'system')
        ),
        source_type TEXT NOT NULL CHECK (length(source_type) > 0),
        provider_record_id TEXT,
        fetched_at TEXT NOT NULL,
        valid_until TEXT,
        freshness TEXT NOT NULL CHECK (
            freshness IN ('fresh', 'stale', 'unknown_validity')
        ),
        reference_url TEXT,
        attributions_json TEXT NOT NULL CHECK (length(attributions_json) > 0),
        warnings_json TEXT NOT NULL CHECK (length(warnings_json) > 0),
        PRIMARY KEY (job_id, source_id),
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE plan_version_sources (
        job_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        source_id TEXT NOT NULL,
        PRIMARY KEY (job_id, version_number, source_id),
        FOREIGN KEY (job_id, version_number)
            REFERENCES plan_versions(job_id, version_number) ON DELETE CASCADE,
        FOREIGN KEY (job_id, source_id)
            REFERENCES source_records(job_id, source_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE decision_records (
        decision_id TEXT PRIMARY KEY CHECK (
            length(decision_id) = 36 AND decision_id = lower(decision_id)
        ),
        job_id TEXT NOT NULL,
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        trace_id TEXT NOT NULL CHECK (length(trace_id) = 36 AND trace_id = lower(trace_id)),
        plan_version INTEGER,
        kind TEXT NOT NULL CHECK (length(kind) > 0),
        status TEXT NOT NULL CHECK (length(status) > 0),
        proposal_json TEXT NOT NULL CHECK (length(proposal_json) > 0),
        validation_json TEXT NOT NULL CHECK (length(validation_json) > 0),
        user_choice_json TEXT CHECK (
            user_choice_json IS NULL OR length(user_choice_json) > 0
        ),
        created_at TEXT NOT NULL,
        decided_at TEXT,
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE acceptance_records (
        acceptance_id TEXT PRIMARY KEY CHECK (
            length(acceptance_id) = 36 AND acceptance_id = lower(acceptance_id)
        ),
        job_id TEXT NOT NULL,
        attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
        plan_version INTEGER,
        case_id TEXT NOT NULL CHECK (length(case_id) > 0),
        status TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'partial', 'not_run')),
        observed_at TEXT NOT NULL,
        environment TEXT NOT NULL CHECK (length(environment) > 0),
        evidence_json TEXT NOT NULL CHECK (length(evidence_json) > 0),
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE
    )
    """,
    "CREATE UNIQUE INDEX uq_planning_jobs_client_request_id ON planning_jobs(client_request_id)",
    "CREATE INDEX ix_planning_jobs_expires_at ON planning_jobs(expires_at)",
    "CREATE INDEX ix_planning_jobs_updated_at ON planning_jobs(updated_at)",
    "CREATE INDEX ix_planning_jobs_status ON planning_jobs(status)",
    "CREATE INDEX ix_planning_attempts_job_attempt ON planning_attempts(job_id, attempt)",
    "CREATE INDEX ix_plan_versions_job_created ON plan_versions(job_id, created_at)",
    (
        "CREATE INDEX ix_source_records_job_freshness "
        "ON source_records(job_id, freshness, valid_until)"
    ),
    "CREATE INDEX ix_decision_records_job_created ON decision_records(job_id, created_at)",
    "CREATE INDEX ix_acceptance_records_job_observed ON acceptance_records(job_id, observed_at)",
)


REPLAN_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE UNIQUE INDEX uq_plan_versions_job_version_plan
    ON plan_versions(job_id, version_number, plan_id)
    """,
    """
    CREATE TABLE replan_requests (
        replan_id TEXT PRIMARY KEY CHECK (length(replan_id) = 36 AND replan_id = lower(replan_id)),
        job_id TEXT NOT NULL,
        replan_request_id TEXT NOT NULL CHECK (
            length(replan_request_id) = 36 AND replan_request_id = lower(replan_request_id)
        ),
        request_fingerprint TEXT NOT NULL CHECK (
            length(request_fingerprint) = 64 AND request_fingerprint = lower(request_fingerprint)
        ),
        baseline_plan_id TEXT NOT NULL CHECK (
            length(baseline_plan_id) = 36 AND baseline_plan_id = lower(baseline_plan_id)
        ),
        baseline_plan_version INTEGER NOT NULL CHECK (baseline_plan_version >= 1),
        expected_job_version INTEGER NOT NULL CHECK (expected_job_version >= 1),
        trace_id TEXT NOT NULL CHECK (length(trace_id) = 36 AND trace_id = lower(trace_id)),
        operation TEXT NOT NULL CHECK (operation IN (
            'replace_activity', 'delete_activity', 'adjust_activity_time', 'reorder_activities'
        )),
        request_json TEXT NOT NULL CHECK (length(request_json) > 0),
        impact_json TEXT,
        status TEXT NOT NULL CHECK (status IN (
            'analyzing', 'awaiting_confirmation', 'replanning', 'completed',
            'needs_input', 'conflict', 'failed', 'cancelled', 'expired', 'rejected'
        )),
        aggregate_version INTEGER NOT NULL CHECK (aggregate_version >= 1),
        decision_id TEXT UNIQUE CHECK (
            decision_id IS NULL OR (length(decision_id) = 36 AND decision_id = lower(decision_id))
        ),
        result_plan_version INTEGER CHECK (result_plan_version IS NULL OR result_plan_version >= 1),
        error_code TEXT CHECK (error_code IS NULL OR length(error_code) > 0),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        decided_at TEXT,
        UNIQUE (job_id, replan_request_id),
        FOREIGN KEY (job_id) REFERENCES planning_jobs(job_id) ON DELETE CASCADE,
        FOREIGN KEY (job_id, baseline_plan_version, baseline_plan_id)
            REFERENCES plan_versions(job_id, version_number, plan_id),
        FOREIGN KEY (job_id, result_plan_version)
            REFERENCES plan_versions(job_id, version_number),
        FOREIGN KEY (decision_id) REFERENCES decision_records(decision_id)
    )
    """,
    """
    CREATE TABLE plan_version_lineage (
        job_id TEXT NOT NULL,
        child_version INTEGER NOT NULL CHECK (child_version >= 1),
        parent_version INTEGER NOT NULL CHECK (parent_version >= 1),
        replan_id TEXT NOT NULL UNIQUE,
        decision_id TEXT UNIQUE,
        change_set_json TEXT NOT NULL CHECK (length(change_set_json) > 0),
        created_at TEXT NOT NULL,
        PRIMARY KEY (job_id, child_version),
        CHECK (child_version > parent_version),
        FOREIGN KEY (job_id, child_version)
            REFERENCES plan_versions(job_id, version_number) ON DELETE CASCADE,
        FOREIGN KEY (job_id, parent_version)
            REFERENCES plan_versions(job_id, version_number),
        FOREIGN KEY (replan_id) REFERENCES replan_requests(replan_id) ON DELETE CASCADE,
        FOREIGN KEY (decision_id) REFERENCES decision_records(decision_id)
    )
    """,
    "CREATE INDEX ix_replan_requests_job_status ON replan_requests(job_id, status, updated_at)",
    "CREATE INDEX ix_replan_requests_expires_at ON replan_requests(expires_at)",
    "CREATE INDEX ix_replan_requests_job_trace ON replan_requests(job_id, trace_id)",
    "CREATE INDEX ix_plan_version_lineage_parent ON plan_version_lineage(job_id, parent_version)",
)
