"""PostgreSQL-backed background worker queue untuk DocuRapi."""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row


DATABASE_ENVIRONMENT_NAMES = (
    "DOCURAPI_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
)

TERMINAL_STATUSES = frozenset({
    "succeeded",
    "failed",
    "canceled",
    "timed_out",
})

ACTIVE_STATUSES = frozenset({
    "queued",
    "retrying",
    "running",
})


class WorkerQueueError(
    RuntimeError
):
    """Kesalahan pada background worker queue."""


class WorkerJobNotFoundError(
    WorkerQueueError
):
    """Job tidak ditemukan."""


class WorkerJobLockError(
    WorkerQueueError
):
    """Lock job tidak valid atau sudah tidak aktif."""


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_postgres_url(
    value: str,
) -> str:
    url = value.strip()

    replacements = (
        (
            "postgresql+psycopg://",
            "postgresql://",
        ),
        (
            "postgres+psycopg://",
            "postgresql://",
        ),
        (
            "postgres://",
            "postgresql://",
        ),
    )

    for source, destination in replacements:
        if url.startswith(source):
            return (
                destination
                + url[len(source):]
            )

    return url


def resolve_database_url() -> str:
    for name in DATABASE_ENVIRONMENT_NAMES:
        value = os.environ.get(
            name,
            "",
        ).strip()

        if value:
            normalized = (
                normalize_postgres_url(
                    value
                )
            )

            if not normalized.startswith(
                "postgresql://"
            ):
                raise WorkerQueueError(
                    f"{name} bukan URL PostgreSQL."
                )

            return normalized

    raise WorkerQueueError(
        "URL PostgreSQL belum tersedia."
    )


def connect() -> psycopg.Connection:
    return psycopg.connect(
        resolve_database_url(),
        row_factory=dict_row,
    )


def json_text(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        default=str,
    )


def calculate_retry_delay(
    attempt: int,
) -> int:
    normalized_attempt = max(
        1,
        int(attempt),
    )

    return min(
        300,
        5 * (
            2 ** (
                normalized_attempt - 1
            )
        ),
    )


def initialize_worker_schema() -> None:
    statements = (
        """
        CREATE SCHEMA IF NOT EXISTS background
        """,
        """
        CREATE TABLE IF NOT EXISTS
            background.worker_runtime_jobs
        (
            job_id TEXT PRIMARY KEY,

            job_type TEXT NOT NULL,

            payload_json JSONB
                NOT NULL
                DEFAULT '{}'::jsonb,

            status TEXT
                NOT NULL
                DEFAULT 'queued',

            priority INTEGER
                NOT NULL
                DEFAULT 100,

            attempts INTEGER
                NOT NULL
                DEFAULT 0,

            max_attempts INTEGER
                NOT NULL
                DEFAULT 3,

            timeout_seconds INTEGER
                NOT NULL
                DEFAULT 300,

            available_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW(),

            locked_at TIMESTAMPTZ,

            lock_token TEXT,

            worker_id TEXT,

            heartbeat_at TIMESTAMPTZ,

            cancel_requested BOOLEAN
                NOT NULL
                DEFAULT FALSE,

            result_json JSONB,

            error_message TEXT,

            artifact_reference TEXT,

            artifact_filename TEXT,

            created_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW(),

            updated_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW(),

            started_at TIMESTAMPTZ,

            finished_at TIMESTAMPTZ,

            CONSTRAINT
                worker_runtime_jobs_status_check
            CHECK (
                status IN (
                    'queued',
                    'retrying',
                    'running',
                    'succeeded',
                    'failed',
                    'canceled',
                    'timed_out'
                )
            ),

            CONSTRAINT
                worker_runtime_jobs_attempts_check
            CHECK (
                attempts >= 0
                AND max_attempts >= 1
            ),

            CONSTRAINT
                worker_runtime_jobs_timeout_check
            CHECK (
                timeout_seconds >= 1
            )
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_worker_runtime_jobs_claim
        ON background.worker_runtime_jobs
        (
            status,
            available_at,
            priority,
            created_at
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_worker_runtime_jobs_worker
        ON background.worker_runtime_jobs
        (
            worker_id,
            status
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_worker_runtime_jobs_heartbeat
        ON background.worker_runtime_jobs
        (
            status,
            heartbeat_at
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS
            background.worker_runtime_events
        (
            event_id BIGSERIAL PRIMARY KEY,

            job_id TEXT
                NOT NULL
                REFERENCES
                    background.worker_runtime_jobs(
                        job_id
                    )
                ON DELETE CASCADE,

            event_type TEXT
                NOT NULL,

            message TEXT,

            metadata_json JSONB
                NOT NULL
                DEFAULT '{}'::jsonb,

            created_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_worker_runtime_events_job
        ON background.worker_runtime_events
        (
            job_id,
            created_at
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS
            background.worker_runtime_workers
        (
            worker_id TEXT PRIMARY KEY,

            hostname TEXT
                NOT NULL,

            process_id INTEGER
                NOT NULL,

            status TEXT
                NOT NULL,

            current_job_id TEXT,

            started_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW(),

            heartbeat_at TIMESTAMPTZ
                NOT NULL
                DEFAULT NOW(),

            stopped_at TIMESTAMPTZ
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS
            idx_worker_runtime_workers_heartbeat
        ON background.worker_runtime_workers
        (
            status,
            heartbeat_at
        )
        """,
    )

    with connect() as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(
                    statement
                )


def _event(
    cursor: psycopg.Cursor,
    *,
    job_id: str,
    event_type: str,
    message: str | None = None,
    metadata: Mapping[
        str,
        Any,
    ] | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO
            background.worker_runtime_events
        (
            job_id,
            event_type,
            message,
            metadata_json
        )
        VALUES (
            %s,
            %s,
            %s,
            %s::jsonb
        )
        """,
        (
            job_id,
            event_type,
            message,
            json_text(
                dict(
                    metadata
                    or {}
                )
            ),
        ),
    )


def enqueue_job(
    job_type: str,
    payload: Mapping[
        str,
        Any,
    ] | None = None,
    *,
    priority: int = 100,
    max_attempts: int = 3,
    timeout_seconds: int = 300,
    delay_seconds: int = 0,
    job_id: str | None = None,
) -> dict[str, Any]:
    initialize_worker_schema()

    normalized_type = str(
        job_type
    ).strip()

    if not normalized_type:
        raise WorkerQueueError(
            "job_type tidak boleh kosong."
        )

    normalized_attempts = int(
        max_attempts
    )

    normalized_timeout = int(
        timeout_seconds
    )

    if normalized_attempts < 1:
        raise WorkerQueueError(
            "max_attempts minimal 1."
        )

    if normalized_timeout < 1:
        raise WorkerQueueError(
            "timeout_seconds minimal 1."
        )

    identifier = (
        str(job_id)
        if job_id is not None
        else uuid.uuid4().hex
    )

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO
                    background.worker_runtime_jobs
                (
                    job_id,
                    job_type,
                    payload_json,
                    status,
                    priority,
                    max_attempts,
                    timeout_seconds,
                    available_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s::jsonb,
                    'queued',
                    %s,
                    %s,
                    %s,
                    NOW()
                    + (
                        %s
                        * INTERVAL '1 second'
                    )
                )
                RETURNING *
                """,
                (
                    identifier,
                    normalized_type,
                    json_text(
                        dict(
                            payload
                            or {}
                        )
                    ),
                    int(priority),
                    normalized_attempts,
                    normalized_timeout,
                    max(
                        0,
                        int(
                            delay_seconds
                        ),
                    ),
                ),
            )

            row = cursor.fetchone()

            _event(
                cursor,
                job_id=identifier,
                event_type="queued",
                message="Job masuk antrean.",
                metadata={
                    "job_type":
                        normalized_type,
                },
            )

    if row is None:
        raise WorkerQueueError(
            "Job gagal masuk antrean."
        )

    return dict(row)


def claim_job(
    worker_id: str,
) -> dict[str, Any] | None:
    lock_token = uuid.uuid4().hex

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS
                (
                    SELECT
                        job_id
                    FROM
                        background.worker_runtime_jobs
                    WHERE
                        status IN (
                            'queued',
                            'retrying'
                        )
                        AND available_at <= NOW()
                        AND cancel_requested = FALSE
                    ORDER BY
                        priority ASC,
                        created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )

                UPDATE
                    background.worker_runtime_jobs
                    AS job
                SET
                    status = 'running',

                    attempts =
                        job.attempts + 1,

                    locked_at = NOW(),

                    lock_token = %s,

                    worker_id = %s,

                    heartbeat_at = NOW(),

                    started_at =
                        COALESCE(
                            job.started_at,
                            NOW()
                        ),

                    updated_at = NOW(),

                    error_message = NULL

                FROM candidate

                WHERE
                    job.job_id =
                        candidate.job_id

                RETURNING job.*
                """,
                (
                    lock_token,
                    worker_id,
                ),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            _event(
                cursor,
                job_id=str(
                    row["job_id"]
                ),
                event_type="claimed",
                message=(
                    "Job diklaim worker."
                ),
                metadata={
                    "worker_id":
                        worker_id,
                    "attempt":
                        int(
                            row["attempts"]
                        ),
                },
            )

    return dict(row)


def heartbeat_job(
    job_id: str,
    lock_token: str,
) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_jobs
                SET
                    heartbeat_at = NOW(),
                    updated_at = NOW()
                WHERE
                    job_id = %s
                    AND lock_token = %s
                    AND status = 'running'
                """,
                (
                    job_id,
                    lock_token,
                ),
            )

            return cursor.rowcount == 1


def complete_job(
    job_id: str,
    lock_token: str,
    *,
    result: Mapping[
        str,
        Any,
    ] | None = None,
    artifact_reference: str | None = None,
    artifact_filename: str | None = None,
) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_jobs
                SET
                    status = 'succeeded',

                    result_json = %s::jsonb,

                    artifact_reference = %s,

                    artifact_filename = %s,

                    error_message = NULL,

                    lock_token = NULL,

                    locked_at = NULL,

                    heartbeat_at = NOW(),

                    updated_at = NOW(),

                    finished_at = NOW()

                WHERE
                    job_id = %s
                    AND lock_token = %s
                    AND status = 'running'

                RETURNING *
                """,
                (
                    json_text(
                        dict(
                            result
                            or {}
                        )
                    ),
                    artifact_reference,
                    artifact_filename,
                    job_id,
                    lock_token,
                ),
            )

            row = cursor.fetchone()

            if row is None:
                raise WorkerJobLockError(
                    "Job tidak dapat diselesaikan "
                    "karena lock tidak valid."
                )

            _event(
                cursor,
                job_id=job_id,
                event_type="succeeded",
                message="Job selesai.",
                metadata={
                    "artifact_reference":
                        artifact_reference,
                },
            )

    return dict(row)


def fail_job(
    job_id: str,
    lock_token: str,
    error_message: str,
    *,
    retryable: bool = True,
    timed_out: bool = False,
) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM
                    background.worker_runtime_jobs
                WHERE
                    job_id = %s
                    AND lock_token = %s
                    AND status = 'running'
                FOR UPDATE
                """,
                (
                    job_id,
                    lock_token,
                ),
            )

            current = cursor.fetchone()

            if current is None:
                raise WorkerJobLockError(
                    "Job tidak dapat digagalkan "
                    "karena lock tidak valid."
                )

            attempts = int(
                current["attempts"]
            )

            max_attempts = int(
                current["max_attempts"]
            )

            should_retry = (
                bool(retryable)
                and attempts < max_attempts
            )

            if should_retry:
                status = "retrying"

                delay_seconds = (
                    calculate_retry_delay(
                        attempts
                    )
                )

                finished_at_sql = "NULL"

                event_type = "retrying"

            else:
                status = (
                    "timed_out"
                    if timed_out
                    else "failed"
                )

                delay_seconds = 0

                finished_at_sql = "NOW()"

                event_type = status

            cursor.execute(
                f"""
                UPDATE
                    background.worker_runtime_jobs
                SET
                    status = %s,

                    error_message = %s,

                    available_at =
                        NOW()
                        + (
                            %s
                            * INTERVAL '1 second'
                        ),

                    lock_token = NULL,

                    locked_at = NULL,

                    worker_id = NULL,

                    heartbeat_at = NULL,

                    updated_at = NOW(),

                    finished_at =
                        {finished_at_sql}

                WHERE
                    job_id = %s

                RETURNING *
                """,
                (
                    status,
                    str(
                        error_message
                    )[:10000],
                    delay_seconds,
                    job_id,
                ),
            )

            row = cursor.fetchone()

            _event(
                cursor,
                job_id=job_id,
                event_type=event_type,
                message=str(
                    error_message
                )[:2000],
                metadata={
                    "attempts":
                        attempts,
                    "max_attempts":
                        max_attempts,
                    "delay_seconds":
                        delay_seconds,
                },
            )

    if row is None:
        raise WorkerQueueError(
            "Status gagal diperbarui."
        )

    return dict(row)


def request_cancel(
    job_id: str,
) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM
                    background.worker_runtime_jobs
                WHERE
                    job_id = %s
                FOR UPDATE
                """,
                (
                    job_id,
                ),
            )

            current = cursor.fetchone()

            if current is None:
                raise WorkerJobNotFoundError(
                    job_id
                )

            current_status = str(
                current["status"]
            )

            if current_status in TERMINAL_STATUSES:
                return dict(current)

            if current_status in {
                "queued",
                "retrying",
            }:
                next_status = "canceled"

                finished_at = True

            else:
                next_status = current_status

                finished_at = False

            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_jobs
                SET
                    cancel_requested = TRUE,

                    status = %s,

                    updated_at = NOW(),

                    finished_at =
                        CASE
                            WHEN %s
                            THEN NOW()
                            ELSE finished_at
                        END

                WHERE
                    job_id = %s

                RETURNING *
                """,
                (
                    next_status,
                    finished_at,
                    job_id,
                ),
            )

            row = cursor.fetchone()

            _event(
                cursor,
                job_id=job_id,
                event_type="cancel_requested",
                message=(
                    "Permintaan pembatalan diterima."
                ),
            )

    assert row is not None

    return dict(row)


def is_cancel_requested(
    job_id: str,
    lock_token: str,
) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    cancel_requested
                FROM
                    background.worker_runtime_jobs
                WHERE
                    job_id = %s
                    AND lock_token = %s
                    AND status = 'running'
                """,
                (
                    job_id,
                    lock_token,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return True

    return bool(
        row["cancel_requested"]
    )


def mark_canceled(
    job_id: str,
    lock_token: str,
    *,
    message: str = "Job dibatalkan.",
) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_jobs
                SET
                    status = 'canceled',

                    cancel_requested = TRUE,

                    error_message = %s,

                    lock_token = NULL,

                    locked_at = NULL,

                    worker_id = NULL,

                    heartbeat_at = NULL,

                    updated_at = NOW(),

                    finished_at = NOW()

                WHERE
                    job_id = %s
                    AND lock_token = %s
                    AND status = 'running'

                RETURNING *
                """,
                (
                    message,
                    job_id,
                    lock_token,
                ),
            )

            row = cursor.fetchone()

            if row is None:
                raise WorkerJobLockError(
                    "Job tidak dapat dibatalkan "
                    "karena lock tidak valid."
                )

            _event(
                cursor,
                job_id=job_id,
                event_type="canceled",
                message=message,
            )

    return dict(row)


def recover_stale_jobs(
    stale_after_seconds: int = 90,
) -> dict[str, int]:
    stale_seconds = max(
        10,
        int(
            stale_after_seconds
        ),
    )

    retried = 0
    failed = 0

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM
                    background.worker_runtime_jobs
                WHERE
                    status = 'running'
                    AND COALESCE(
                        heartbeat_at,
                        locked_at,
                        updated_at
                    )
                    <
                    NOW()
                    - (
                        %s
                        * INTERVAL '1 second'
                    )
                FOR UPDATE SKIP LOCKED
                """,
                (
                    stale_seconds,
                ),
            )

            rows = cursor.fetchall()

            for row in rows:
                job_id = str(
                    row["job_id"]
                )

                attempts = int(
                    row["attempts"]
                )

                max_attempts = int(
                    row["max_attempts"]
                )

                if attempts < max_attempts:
                    status = "retrying"

                    delay = (
                        calculate_retry_delay(
                            attempts
                        )
                    )

                    finished_at = False

                    retried += 1

                else:
                    status = "failed"

                    delay = 0

                    finished_at = True

                    failed += 1

                cursor.execute(
                    """
                    UPDATE
                        background.worker_runtime_jobs
                    SET
                        status = %s,

                        available_at =
                            NOW()
                            + (
                                %s
                                * INTERVAL '1 second'
                            ),

                        error_message =
                            'Recovered stale worker job.',

                        worker_id = NULL,

                        lock_token = NULL,

                        locked_at = NULL,

                        heartbeat_at = NULL,

                        updated_at = NOW(),

                        finished_at =
                            CASE
                                WHEN %s
                                THEN NOW()
                                ELSE NULL
                            END

                    WHERE
                        job_id = %s
                    """,
                    (
                        status,
                        delay,
                        finished_at,
                        job_id,
                    ),
                )

                _event(
                    cursor,
                    job_id=job_id,
                    event_type=(
                        "stale_recovered"
                    ),
                    message=(
                        "Job dipulihkan karena "
                        "worker heartbeat terhenti."
                    ),
                    metadata={
                        "next_status":
                            status,
                    },
                )

    return {
        "retried": retried,
        "failed": failed,
    }


def register_worker(
    worker_id: str,
    process_id: int,
) -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO
                    background.worker_runtime_workers
                (
                    worker_id,
                    hostname,
                    process_id,
                    status,
                    current_job_id,
                    started_at,
                    heartbeat_at,
                    stopped_at
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'running',
                    NULL,
                    NOW(),
                    NOW(),
                    NULL
                )

                ON CONFLICT(worker_id)
                DO UPDATE SET
                    hostname =
                        EXCLUDED.hostname,

                    process_id =
                        EXCLUDED.process_id,

                    status = 'running',

                    current_job_id = NULL,

                    started_at = NOW(),

                    heartbeat_at = NOW(),

                    stopped_at = NULL
                """,
                (
                    worker_id,
                    socket.gethostname(),
                    int(process_id),
                ),
            )


def heartbeat_worker(
    worker_id: str,
    *,
    current_job_id: str | None = None,
) -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_workers
                SET
                    heartbeat_at = NOW(),

                    status = 'running',

                    current_job_id = %s

                WHERE
                    worker_id = %s
                """,
                (
                    current_job_id,
                    worker_id,
                ),
            )


def stop_worker(
    worker_id: str,
) -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE
                    background.worker_runtime_workers
                SET
                    status = 'stopped',

                    current_job_id = NULL,

                    heartbeat_at = NOW(),

                    stopped_at = NOW()

                WHERE
                    worker_id = %s
                """,
                (
                    worker_id,
                ),
            )


def get_job(
    job_id: str,
) -> dict[str, Any] | None:
    initialize_worker_schema()

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM
                    background.worker_runtime_jobs
                WHERE
                    job_id = %s
                LIMIT 1
                """,
                (
                    job_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row is not None
        else None
    )


def list_jobs(
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    initialize_worker_schema()

    normalized_limit = min(
        200,
        max(
            1,
            int(limit),
        ),
    )

    with connect() as connection:
        with connection.cursor() as cursor:
            if status:
                cursor.execute(
                    """
                    SELECT *
                    FROM
                        background.worker_runtime_jobs
                    WHERE
                        status = %s
                    ORDER BY
                        created_at DESC
                    LIMIT %s
                    """,
                    (
                        status,
                        normalized_limit,
                    ),
                )
            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM
                        background.worker_runtime_jobs
                    ORDER BY
                        created_at DESC
                    LIMIT %s
                    """,
                    (
                        normalized_limit,
                    ),
                )

            rows = cursor.fetchall()

    return [
        dict(row)
        for row in rows
    ]


def delete_job(
    job_id: str,
) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM
                    background.worker_runtime_jobs
                WHERE
                    job_id = %s
                    AND status IN (
                        'succeeded',
                        'failed',
                        'canceled',
                        'timed_out'
                    )
                """,
                (
                    job_id,
                ),
            )

            return cursor.rowcount == 1


def queue_health(
    worker_stale_seconds: int = 90,
) -> dict[str, Any]:
    initialize_worker_schema()

    stale_seconds = max(
        10,
        int(
            worker_stale_seconds
        ),
    )

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    status,
                    COUNT(*) AS total
                FROM
                    background.worker_runtime_jobs
                GROUP BY
                    status
                ORDER BY
                    status
                """
            )

            status_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS active_workers
                FROM
                    background.worker_runtime_workers
                WHERE
                    status = 'running'
                    AND heartbeat_at
                        >= NOW()
                        - (
                            %s
                            * INTERVAL '1 second'
                        )
                """,
                (
                    stale_seconds,
                ),
            )

            workers = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    EXTRACT(
                        EPOCH FROM (
                            NOW()
                            - MIN(created_at)
                        )
                    ) AS oldest_queued_seconds
                FROM
                    background.worker_runtime_jobs
                WHERE
                    status IN (
                        'queued',
                        'retrying'
                    )
                """
            )

            oldest = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    worker_id,
                    hostname,
                    process_id,
                    status,
                    current_job_id,
                    started_at,
                    heartbeat_at,
                    stopped_at
                FROM
                    background.worker_runtime_workers
                ORDER BY
                    heartbeat_at DESC
                LIMIT 20
                """
            )

            worker_rows = cursor.fetchall()

    counts = {
        str(row["status"]):
            int(row["total"])
        for row in status_rows
    }

    active_workers = int(
        workers["active_workers"]
        if workers is not None
        else 0
    )

    oldest_seconds_value = (
        oldest["oldest_queued_seconds"]
        if oldest is not None
        else None
    )

    oldest_seconds = (
        float(oldest_seconds_value)
        if oldest_seconds_value
        is not None
        else None
    )

    pending = (
        counts.get(
            "queued",
            0,
        )
        + counts.get(
            "retrying",
            0,
        )
    )

    status = (
        "ready"
        if active_workers > 0
        else (
            "idle"
            if pending == 0
            else "degraded"
        )
    )

    return {
        "status":
            status,

        "active_workers":
            active_workers,

        "pending_jobs":
            pending,

        "running_jobs":
            counts.get(
                "running",
                0,
            ),

        "oldest_queued_seconds":
            oldest_seconds,

        "counts":
            counts,

        "workers": [
            dict(row)
            for row in worker_rows
        ],
    }
