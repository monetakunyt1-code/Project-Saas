from __future__ import annotations

import json
from services import database_adapter as sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import STORAGE_DIR


BACKGROUND_DIRECTORY = (
    STORAGE_DIR
    / "background"
)

BACKGROUND_DATABASE_PATH = (
    BACKGROUND_DIRECTORY
    / "background_jobs.db"
)

BACKGROUND_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        BACKGROUND_DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def initialize_background_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                target_path TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL,
                request_summary_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,
                error_message TEXT,
                artifact_path TEXT,
                artifact_filename TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_background_workspace
            ON background_jobs(
                workspace_id,
                created_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_background_user
            ON background_jobs(
                user_id,
                created_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_background_status
            ON background_jobs(status);
            """
        )

        connection.commit()


def create_background_job(
    job_id: str,
    user_id: str,
    workspace_id: str,
    operation: str,
    target_path: str,
    request_summary: dict[str, Any],
) -> dict[str, Any]:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO background_jobs (
                job_id,
                user_id,
                workspace_id,
                operation,
                target_path,
                status,
                progress,
                message,
                request_summary_json,
                result_json,
                error_message,
                artifact_path,
                artifact_filename,
                cancel_requested,
                created_at,
                started_at,
                finished_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                'queued',
                0,
                'Menunggu antrean...',
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                0,
                ?,
                NULL,
                NULL,
                ?
            )
            """,
            (
                job_id,
                user_id,
                workspace_id,
                operation,
                target_path,
                json.dumps(
                    request_summary,
                    ensure_ascii=False,
                ),
                timestamp,
                timestamp,
            ),
        )

        connection.commit()

    result = get_background_job(
        job_id
    )

    if not result:
        raise RuntimeError(
            "Background job gagal dibuat."
        )

    return result


def update_background_job(
    job_id: str,
    **values: Any,
) -> dict[str, Any] | None:
    allowed_fields = {
        "status",
        "progress",
        "message",
        "result_json",
        "error_message",
        "artifact_path",
        "artifact_filename",
        "cancel_requested",
        "started_at",
        "finished_at",
    }

    updates: list[str] = []
    parameters: list[Any] = []

    for key, value in values.items():
        if key not in allowed_fields:
            continue

        if key == "result_json":
            if value is not None and not isinstance(
                value,
                str,
            ):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                )

        updates.append(
            f"{key} = ?"
        )
        parameters.append(value)

    if not updates:
        return get_background_job(
            job_id
        )

    updates.append(
        "updated_at = ?"
    )

    parameters.append(
        utc_now()
    )

    parameters.append(
        job_id
    )

    with connect() as connection:
        connection.execute(
            f"""
            UPDATE background_jobs
            SET {", ".join(updates)}
            WHERE job_id = ?
            """,
            tuple(parameters),
        )

        connection.commit()

    return get_background_job(
        job_id
    )


def parse_job_row(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if not row:
        return None

    result = dict(row)

    try:
        result["request_summary"] = json.loads(
            result.pop(
                "request_summary_json"
            )
            or "{}"
        )
    except json.JSONDecodeError:
        result["request_summary"] = {}

    raw_result = result.pop(
        "result_json"
    )

    if raw_result:
        try:
            result["result"] = json.loads(
                raw_result
            )
        except json.JSONDecodeError:
            result["result"] = None
    else:
        result["result"] = None

    result["cancel_requested"] = bool(
        result["cancel_requested"]
    )

    return result


def get_background_job(
    job_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM background_jobs
            WHERE job_id = ?
            """,
            (
                job_id,
            ),
        ).fetchone()

    return parse_job_row(row)


def list_background_jobs(
    workspace_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM background_jobs
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                workspace_id,
                safe_limit,
            ),
        ).fetchall()

    return [
        parse_job_row(row)
        for row in rows
    ]


def request_job_cancellation(
    job_id: str,
) -> dict[str, Any] | None:
    return update_background_job(
        job_id,
        cancel_requested=1,
        message=(
            "Permintaan pembatalan diterima..."
        ),
    )


def is_job_cancellation_requested(
    job_id: str,
) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT cancel_requested
            FROM background_jobs
            WHERE job_id = ?
            """,
            (
                job_id,
            ),
        ).fetchone()

    return bool(
        row
        and row["cancel_requested"]
    )


def delete_background_job(
    job_id: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            DELETE FROM background_jobs
            WHERE job_id = ?
            """,
            (
                job_id,
            ),
        )

        connection.commit()


def mark_interrupted_jobs() -> int:
    timestamp = utc_now()

    interrupted_message = (
        "Pekerjaan terhenti karena server dimulai ulang."
    )

    runtime_error_message = (
        "Runtime pekerjaan sudah tidak tersedia."
    )

    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE background_jobs
            SET
                status = 'failed',
                progress = 100,
                message = ?,
                error_message = ?,
                finished_at = ?,
                updated_at = ?
            WHERE status IN (
                'queued',
                'running',
                'canceling'
            )
            """,
            (
                interrupted_message,
                runtime_error_message,
                timestamp,
                timestamp,
            ),
        )

        connection.commit()

    return int(
        cursor.rowcount
    )

initialize_background_database()


# DOCURAPI_OBJECT_STORAGE_RUNTIME_MIRROR
from services.runtime_file_mirror import (
    install_module_file_mirroring as
        _install_docurapi_file_mirroring,
)

_DOCURAPI_STORAGE_MIRRORED_FUNCTIONS = (
    _install_docurapi_file_mirroring(
        globals(),
        module_name=__name__,
    )
)

del _install_docurapi_file_mirroring
