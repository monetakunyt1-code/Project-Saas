from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from docurapi.db.connection import connect, utc_now


def create_payment_record(
    job_id: str,
    provider: str,
    amount: int,
    status: str = "pending",
    external_reference: str | None = None,
    checkout_url: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payment_id = uuid4().hex
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO payments (
                payment_id, job_id, provider, amount, status,
                external_reference, checkout_url, raw_payload,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment_id,
                job_id,
                provider,
                amount,
                status,
                external_reference,
                checkout_url,
                json.dumps(raw_payload or {}, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        connection.commit()

    return get_payment(payment_id)


def get_payment(payment_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM payments WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()

    return dict(row) if row else None


def get_latest_payment_for_job(job_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM payments
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()

    return dict(row) if row else None


def list_payments_for_job(job_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM payments
            WHERE job_id = ?
            ORDER BY created_at DESC
            """,
            (job_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def mark_payment_paid(
    payment_id: str,
    external_reference: str,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            UPDATE payments
            SET status = ?, external_reference = ?, raw_payload = ?,
                paid_at = ?, updated_at = ?
            WHERE payment_id = ?
            """,
            (
                "paid",
                external_reference,
                json.dumps(raw_payload or {}, ensure_ascii=False),
                timestamp,
                timestamp,
                payment_id,
            ),
        )
        connection.commit()

    return get_payment(payment_id)


def mark_latest_payment_paid_for_job(
    job_id: str,
    external_reference: str,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payment = get_latest_payment_for_job(job_id)

    if not payment:
        return None

    return mark_payment_paid(
        payment_id=payment["payment_id"],
        external_reference=external_reference,
        raw_payload=raw_payload,
    )


def mark_payment_failed(
    payment_id: str,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            UPDATE payments
            SET status = ?, raw_payload = ?, updated_at = ?
            WHERE payment_id = ?
            """,
            (
                "failed",
                json.dumps(raw_payload or {}, ensure_ascii=False),
                timestamp,
                payment_id,
            ),
        )
        connection.commit()

    return get_payment(payment_id)
