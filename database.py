from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATABASE_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                mode TEXT NOT NULL,
                preset TEXT NOT NULL,
                status TEXT NOT NULL,
                input_size INTEGER DEFAULT 0,
                output_name TEXT,
                output_path TEXT,
                report_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                template_id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                institution_name TEXT,
                document_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at
            ON jobs(created_at DESC)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_jobs_status
            ON jobs(status)
            """
        )

        connection.commit()


def create_job(
    job_id: str,
    original_name: str,
    mode: str,
    preset: str,
    input_size: int = 0,
) -> None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_id,
                original_name,
                mode,
                preset,
                status,
                input_size,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                original_name,
                mode,
                preset,
                "processing",
                input_size,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()


def complete_job(
    job_id: str,
    output_name: str,
    output_path: str,
    report_path: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                output_name = ?,
                output_path = ?,
                report_path = ?,
                error_message = NULL,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                "completed",
                output_name,
                output_path,
                report_path,
                utc_now(),
                job_id,
            ),
        )
        connection.commit()


def fail_job(
    job_id: str,
    error_message: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET
                status = ?,
                error_message = ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                "failed",
                error_message[:2000],
                utc_now(),
                job_id,
            ),
        )
        connection.commit()


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

    return dict(row) if row else None


def list_jobs(
    limit: int = 25,
    status: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))

    with connect() as connection:
        if status:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status, safe_limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

    return [dict(row) for row in rows]


def delete_job(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)

    if not job:
        return None

    with connect() as connection:
        connection.execute(
            """
            DELETE FROM jobs
            WHERE job_id = ?
            """,
            (job_id,),
        )
        connection.commit()

    return job


def clear_job_history() -> list[dict[str, Any]]:
    jobs = list_jobs(limit=100)

    with connect() as connection:
        connection.execute("DELETE FROM jobs")
        connection.commit()

    return jobs


def register_template(
    template_id: str,
    template_name: str,
    institution_name: str,
    document_type: str,
    file_name: str,
    file_path: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO templates (
                template_id,
                template_name,
                institution_name,
                document_type,
                file_name,
                file_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                template_name,
                institution_name,
                document_type,
                file_name,
                file_path,
                utc_now(),
            ),
        )
        connection.commit()


def list_templates() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM templates
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_template(template_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        ).fetchone()

    return dict(row) if row else None


def delete_template(
    template_id: str,
) -> dict[str, Any] | None:
    template = get_template(template_id)

    if not template:
        return None

    with connect() as connection:
        connection.execute(
            """
            DELETE FROM templates
            WHERE template_id = ?
            """,
            (template_id,),
        )
        connection.commit()

    return template


def remove_job_files(job: dict[str, Any]) -> None:
    for field in ("output_path", "report_path"):
        raw_path = job.get(field)

        if not raw_path:
            continue

        path = Path(raw_path)

        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)