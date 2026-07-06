from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from docurapi.core.settings import settings
from docurapi.db.audit_repository import list_audit_logs
from docurapi.db.connection import connect, utc_now
from docurapi.db.jobs_repository import mark_job_expired


def ensure_admin_secret(secret: str) -> None:
    if secret != settings.ADMIN_APPROVAL_SECRET:
        raise HTTPException(status_code=403, detail="Secret admin tidak valid.")


def scalar(query: str, params: tuple = ()) -> int:
    with connect() as connection:
        row = connection.execute(query, params).fetchone()

    return int(row[0] or 0)


def rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect() as connection:
        result = connection.execute(query, params).fetchall()

    return [dict(row) for row in result]


def get_admin_overview(secret: str) -> dict[str, Any]:
    ensure_admin_secret(secret)

    return {
        "success": True,
        "generated_at": utc_now(),
        "jobs": {
            "total": scalar("SELECT COUNT(*) FROM jobs"),
            "completed": scalar("SELECT COUNT(*) FROM jobs WHERE status = 'completed'"),
            "failed": scalar("SELECT COUNT(*) FROM jobs WHERE status = 'failed'"),
        },
        "payments": {
            "unpaid": scalar("SELECT COUNT(*) FROM jobs WHERE payment_status = 'unpaid'"),
            "pending_verification": scalar("SELECT COUNT(*) FROM jobs WHERE payment_status = 'pending_verification'"),
            "paid": scalar("SELECT COUNT(*) FROM jobs WHERE payment_status = 'paid'"),
            "rejected": scalar("SELECT COUNT(*) FROM jobs WHERE payment_status = 'rejected'"),
            "expired": scalar("SELECT COUNT(*) FROM jobs WHERE payment_status = 'expired'"),
            "revenue_paid": scalar("SELECT COALESCE(SUM(amount), 0) FROM jobs WHERE payment_status = 'paid'"),
        },
        "processing_modes": rows(
            """
            SELECT mode, COUNT(*) AS total
            FROM jobs
            GROUP BY mode
            ORDER BY total DESC
            """
        ),
        "recent_jobs": rows(
            """
            SELECT job_id, original_name, mode, preset, status, payment_status,
                   amount, base_amount, unique_code, invoice_expires_at,
                   created_at, updated_at
            FROM jobs
            ORDER BY created_at DESC
            LIMIT 10
            """
        ),
        "recent_audit_logs": list_audit_logs(limit=10),
    }


def list_pending_admin_payments(secret: str, limit: int = 50) -> dict[str, Any]:
    ensure_admin_secret(secret)

    safe_limit = max(1, min(int(limit), 100))

    data = rows(
        """
        SELECT job_id, original_name, mode, preset, payment_status,
               amount, base_amount, unique_code, invoice_expires_at,
               payment_reference, updated_at
        FROM jobs
        WHERE payment_status = 'pending_verification'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (safe_limit,),
    )

    return {
        "success": True,
        "total": len(data),
        "jobs": data,
    }


def list_expired_admin_invoices(secret: str, limit: int = 50) -> dict[str, Any]:
    ensure_admin_secret(secret)

    safe_limit = max(1, min(int(limit), 100))

    data = rows(
        """
        SELECT job_id, original_name, mode, preset, payment_status,
               amount, base_amount, unique_code, invoice_expires_at,
               updated_at
        FROM jobs
        WHERE payment_status = 'expired'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (safe_limit,),
    )

    return {
        "success": True,
        "total": len(data),
        "jobs": data,
    }


def expire_overdue_invoices(secret: str) -> dict[str, Any]:
    ensure_admin_secret(secret)

    now = datetime.now(timezone.utc).isoformat()

    overdue_jobs = rows(
        """
        SELECT job_id
        FROM jobs
        WHERE invoice_expires_at IS NOT NULL
          AND invoice_expires_at < ?
          AND payment_status IN ('unpaid', 'rejected')
        """,
        (now,),
    )

    for job in overdue_jobs:
        mark_job_expired(job["job_id"])

    return {
        "success": True,
        "expired_count": len(overdue_jobs),
        "expired_job_ids": [job["job_id"] for job in overdue_jobs],
    }


def get_audit_logs(secret: str, limit: int = 50) -> dict[str, Any]:
    ensure_admin_secret(secret)

    logs = list_audit_logs(limit=limit)

    return {
        "success": True,
        "total": len(logs),
        "audit_logs": logs,
    }
