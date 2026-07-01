CREATE SCHEMA IF NOT EXISTS background;

CREATE TABLE IF NOT EXISTS background.worker_runtime_jobs
(
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    lock_token TEXT,
    worker_id TEXT,
    heartbeat_at TIMESTAMPTZ,
    cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
    result_json JSONB,
    error_message TEXT,
    artifact_reference TEXT,
    artifact_filename TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_worker_runtime_jobs_claim
ON background.worker_runtime_jobs
(
    status,
    available_at,
    priority,
    created_at
);

CREATE TABLE IF NOT EXISTS background.worker_runtime_events
(
    event_id BIGSERIAL PRIMARY KEY,

    job_id TEXT NOT NULL
        REFERENCES background.worker_runtime_jobs(job_id)
        ON DELETE CASCADE,

    event_type TEXT NOT NULL,
    message TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_runtime_events_job
ON background.worker_runtime_events
(
    job_id,
    created_at
);

CREATE TABLE IF NOT EXISTS background.worker_runtime_workers
(
    worker_id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    current_job_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ
);
