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
    proof_file_name: str | None = None,
    proof_path: str | None = None,
    proof_content_type: str | None = None,
) -> dict[str, Any]:
    payment_id = uuid4().hex
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO payments (
                payment_id, job_id, provider, amount, status,
                external_reference, checkout_url, raw_payload,
                proof_file_name, proof_path, proof_content_type,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                proof_file_name,
                proof_path,
                proof_content_type,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()

    payment = get_payment(payment_id)

    if not payment:
        raise RuntimeError("Payment record gagal dibuat.")

    return payment


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


def update_latest_payment_for_job(
    job_id: str,
    status: str,
    external_reference: str | None = None,
    raw_payload: dict[str, Any] | None = None,
    rejection_reason: str | None = None,
    proof_file_name: str | None = None,
    proof_path: str | None = None,
    proof_content_type: str | None = None,
) -> dict[str, Any] | None:
    payment = get_latest_payment_for_job(job_id)

    if not payment:
        return None

    timestamp = utc_now()
    paid_at = timestamp if status == "paid" else payment.get("paid_at")
    rejected_at = timestamp if status == "rejected" else payment.get("rejected_at")

    with connect() as connection:
        connection.execute(
            """
            UPDATE payments
            SET status = ?,
                external_reference = COALESCE(?, external_reference),
                raw_payload = ?,
                paid_at = ?,
                rejected_at = ?,
                rejection_reason = COALESCE(?, rejection_reason),
                proof_file_name = COALESCE(?, proof_file_name),
                proof_path = COALESCE(?, proof_path),
                proof_content_type = COALESCE(?, proof_content_type),
                updated_at = ?
            WHERE payment_id = ?
            """,
            (
                status,
                external_reference,
                json.dumps(raw_payload or {}, ensure_ascii=False),
                paid_at,
                rejected_at,
                rejection_reason,
                proof_file_name,
                proof_path,
                proof_content_type,
                timestamp,
                payment["payment_id"],
            ),
        )
        connection.commit()

    return get_payment(payment["payment_id"])
