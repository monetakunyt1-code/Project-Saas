from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from docurapi.db.connection import connect, utc_now


def create_audit_log(
    event_type: str,
    actor: str,
    message: str,
    job_id: str | None = None,
    payment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit_id = uuid4().hex
    created_at = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (
                audit_id, event_type, actor, job_id, payment_id,
                message, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                event_type,
                actor,
                job_id,
                payment_id,
                message,
                json.dumps(metadata or {}, ensure_ascii=False),
                created_at,
            ),
        )
        connection.commit()

    return {
        "audit_id": audit_id,
        "event_type": event_type,
        "actor": actor,
        "job_id": job_id,
        "payment_id": payment_id,
        "message": message,
        "metadata": metadata or {},
        "created_at": created_at,
    }


def list_audit_logs(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_audit_logs_by_job(job_id: str, limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 200))

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM audit_logs
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (job_id, safe_limit),
        ).fetchall()

    return [dict(row) for row in rows]
