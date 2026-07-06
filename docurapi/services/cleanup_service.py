from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from docurapi.core.settings import settings
from docurapi.db.connection import connect
from docurapi.db.payments_repository import list_payments_for_job
from docurapi.services.audit_service import log_event


def ensure_admin_secret(secret: str) -> None:
    if secret != settings.ADMIN_APPROVAL_SECRET:
        raise HTTPException(status_code=403, detail="Secret admin tidak valid.")


def cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def is_safe_storage_path(raw_path: str | None) -> bool:
    if not raw_path:
        return False

    path = Path(raw_path)

    try:
        path.resolve().relative_to(settings.STORAGE_DIR.resolve())
    except ValueError:
        return False

    return True


def remove_file(raw_path: str | None, dry_run: bool) -> dict[str, Any] | None:
    if not raw_path:
        return None

    path = Path(raw_path)

    if not is_safe_storage_path(raw_path):
        return {
            "path": raw_path,
            "removed": False,
            "reason": "unsafe_path",
        }

    if not path.exists():
        return {
            "path": raw_path,
            "removed": False,
            "reason": "not_found",
        }

    if dry_run:
        return {
            "path": raw_path,
            "removed": False,
            "reason": "dry_run",
        }

    if path.is_file():
        path.unlink(missing_ok=True)
        return {
            "path": raw_path,
            "removed": True,
            "reason": "deleted",
        }

    return {
        "path": raw_path,
        "removed": False,
        "reason": "not_file",
    }


def fetch_cleanup_candidates() -> list[dict[str, Any]]:
    failed_cutoff = cutoff_iso(settings.RETENTION_FAILED_DAYS)
    unpaid_cutoff = cutoff_iso(settings.RETENTION_UNPAID_DAYS)
    rejected_cutoff = cutoff_iso(settings.RETENTION_REJECTED_DAYS)
    expired_cutoff = cutoff_iso(settings.RETENTION_EXPIRED_DAYS)

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE
                (status = 'failed' AND updated_at < ?)
                OR (payment_status = 'unpaid' AND updated_at < ?)
                OR (payment_status = 'rejected' AND updated_at < ?)
                OR (payment_status = 'expired' AND updated_at < ?)
            ORDER BY updated_at ASC
            """,
            (
                failed_cutoff,
                unpaid_cutoff,
                rejected_cutoff,
                expired_cutoff,
            ),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_job_row(job_id: str) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        connection.commit()


def cleanup_audit_logs(dry_run: bool) -> dict[str, Any]:
    cutoff = cutoff_iso(settings.RETENTION_AUDIT_LOG_DAYS)

    with connect() as connection:
        count_row = connection.execute(
            "SELECT COUNT(*) AS total FROM audit_logs WHERE created_at < ?",
            (cutoff,),
        ).fetchone()

        total = int(count_row["total"] or 0)

        if not dry_run:
            connection.execute(
                "DELETE FROM audit_logs WHERE created_at < ?",
                (cutoff,),
            )
            connection.commit()

    return {
        "retention_days": settings.RETENTION_AUDIT_LOG_DAYS,
        "cutoff": cutoff,
        "deleted": 0 if dry_run else total,
        "matched": total,
        "dry_run": dry_run,
    }


def run_storage_cleanup(secret: str, dry_run: bool = True) -> dict[str, Any]:
    ensure_admin_secret(secret)

    candidates = fetch_cleanup_candidates()
    job_results: list[dict[str, Any]] = []

    total_files_matched = 0
    total_files_removed = 0

    for job in candidates:
        file_results = []

        for field in ("output_path", "report_path"):
            result = remove_file(job.get(field), dry_run=dry_run)
            if result:
                file_results.append(result)
                total_files_matched += 1
                if result["removed"]:
                    total_files_removed += 1

        payments = list_payments_for_job(job["job_id"])

        for payment in payments:
            result = remove_file(payment.get("proof_path"), dry_run=dry_run)
            if result:
                file_results.append(result)
                total_files_matched += 1
                if result["removed"]:
                    total_files_removed += 1

        if not dry_run:
            delete_job_row(job["job_id"])

        job_results.append(
            {
                "job_id": job["job_id"],
                "status": job.get("status"),
                "payment_status": job.get("payment_status"),
                "updated_at": job.get("updated_at"),
                "deleted_job_row": not dry_run,
                "files": file_results,
            }
        )

    audit_cleanup = cleanup_audit_logs(dry_run=dry_run)

    log_event(
        event_type="cleanup_run",
        actor="admin",
        message="Cleanup policy dijalankan.",
        metadata={
            "dry_run": dry_run,
            "candidate_jobs": len(candidates),
            "files_matched": total_files_matched,
            "files_removed": total_files_removed,
            "audit_cleanup": audit_cleanup,
        },
    )

    return {
        "success": True,
        "dry_run": dry_run,
        "retention_policy": {
            "failed_days": settings.RETENTION_FAILED_DAYS,
            "unpaid_days": settings.RETENTION_UNPAID_DAYS,
            "rejected_days": settings.RETENTION_REJECTED_DAYS,
            "expired_days": settings.RETENTION_EXPIRED_DAYS,
            "audit_log_days": settings.RETENTION_AUDIT_LOG_DAYS,
        },
        "summary": {
            "candidate_jobs": len(candidates),
            "deleted_jobs": 0 if dry_run else len(candidates),
            "files_matched": total_files_matched,
            "files_removed": total_files_removed,
            "audit_logs_matched": audit_cleanup["matched"],
            "audit_logs_deleted": audit_cleanup["deleted"],
        },
        "jobs": job_results,
        "audit_cleanup": audit_cleanup,
    }
