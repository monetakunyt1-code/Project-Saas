from __future__ import annotations

from pathlib import Path
from typing import Any

from docurapi.core.settings import settings
from docurapi.db.connection import connect, utc_now


def create_job(
    job_id: str,
    original_name: str,
    mode: str,
    preset: str,
    input_size: int = 0,
    amount: int = 0,
    access_token: str | None = None,
    base_amount: int = 0,
    unique_code: int = 0,
    invoice_expires_at: str | None = None,
) -> None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                job_id, original_name, mode, preset, status,
                input_size, amount, base_amount, unique_code,
                invoice_expires_at, payment_status, access_token,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                original_name,
                mode,
                preset,
                "processing",
                input_size,
                amount,
                base_amount,
                unique_code,
                invoice_expires_at,
                "unpaid",
                access_token,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()


def complete_job(job_id: str, output_name: str, output_path: str, report_path: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, output_name = ?, output_path = ?,
                report_path = ?, error_message = NULL, updated_at = ?
            WHERE job_id = ?
            """,
            ("completed", output_name, output_path, report_path, utc_now(), job_id),
        )
        connection.commit()


def fail_job(job_id: str, error_message: str) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET status = ?, error_message = ?, updated_at = ?
            WHERE job_id = ?
            """,
            ("failed", error_message[:2000], utc_now(), job_id),
        )
        connection.commit()


def mark_job_paid(job_id: str, payment_reference: str) -> None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET payment_status = ?, payment_reference = ?, paid_at = ?,
                rejected_at = NULL, rejection_reason = NULL, updated_at = ?
            WHERE job_id = ?
            """,
            ("paid", payment_reference, timestamp, timestamp, job_id),
        )
        connection.commit()


def mark_job_pending_verification(job_id: str, payment_reference: str | None = None) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET payment_status = ?, payment_reference = COALESCE(?, payment_reference), updated_at = ?
            WHERE job_id = ?
            """,
            ("pending_verification", payment_reference, utc_now(), job_id),
        )
        connection.commit()


def mark_job_rejected(job_id: str, reason: str = "Pembayaran ditolak admin.") -> None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            UPDATE jobs
            SET payment_status = ?, rejected_at = ?, rejection_reason = ?, updated_at = ?
            WHERE job_id = ?
            """,
            ("rejected", timestamp, reason[:1000], timestamp, job_id),
        )
        connection.commit()


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    return dict(row) if row else None


def list_jobs(limit: int = settings.DEFAULT_HISTORY_LIMIT) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), settings.MAX_HISTORY_LIMIT))

    with connect() as connection:
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


def list_jobs_by_payment_status(
    payment_status: str,
    limit: int = settings.DEFAULT_HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), settings.MAX_HISTORY_LIMIT))

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE payment_status = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (payment_status, safe_limit),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_job(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)

    if not job:
        return None

    with connect() as connection:
        connection.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        connection.commit()

    return job


def clear_job_history() -> list[dict[str, Any]]:
    jobs = list_jobs(limit=settings.MAX_HISTORY_LIMIT)

    with connect() as connection:
        connection.execute("DELETE FROM jobs")
        connection.commit()

    return jobs


def remove_job_files(job: dict[str, Any]) -> None:
    for field in ("output_path", "report_path"):
        raw_path = job.get(field)

        if not raw_path:
            continue

        path = Path(raw_path)

        try:
            path.relative_to(settings.STORAGE_DIR)
        except ValueError:
            continue

        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
