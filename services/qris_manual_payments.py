"""PostgreSQL persistence for DocuRapi manual QRIS payments."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from services.postgres_worker_queue import connect


class QrisPaymentError(RuntimeError):
    pass


class QrisPaymentNotFoundError(QrisPaymentError):
    pass


class QrisPaymentOwnershipError(QrisPaymentError):
    pass


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    return value


def normalize_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise QrisPaymentError("Nominal pembayaran tidak valid.") from exc
    if amount <= 0:
        raise QrisPaymentError("Nominal pembayaran harus lebih dari nol.")
    return amount


def detect_proof_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"
    raise QrisPaymentError("Bukti pembayaran harus PNG, JPG, WEBP, atau PDF.")


def initialize_qris_schema() -> None:
    statements = (
        "CREATE SCHEMA IF NOT EXISTS billing",
        """
        CREATE TABLE IF NOT EXISTS billing.qris_manual_payments
        (
            payment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            buyer_email TEXT,
            product_code TEXT,
            amount NUMERIC(18,2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'prepared',
            proof_reference TEXT,
            proof_filename TEXT,
            proof_content_type TEXT,
            proof_size BIGINT,
            payer_name TEXT,
            payment_note TEXT,
            submitted_at TIMESTAMPTZ,
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            rejection_reason TEXT,
            activation_response JSONB,
            worker_job_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT qris_manual_payments_status_check
            CHECK (status IN ('prepared','submitted','approved','rejected','canceled'))
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_qris_manual_payments_status
        ON billing.qris_manual_payments(status, updated_at)
        """,
        """
        CREATE TABLE IF NOT EXISTS billing.qris_manual_payment_events
        (
            event_id BIGSERIAL PRIMARY KEY,
            payment_id TEXT NOT NULL REFERENCES billing.qris_manual_payments(payment_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_id TEXT,
            message TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
    )
    with connect() as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)


def _event(cursor: Any, payment_id: str, event_type: str, actor_id: str | None = None,
           message: str | None = None, metadata: Mapping[str, Any] | None = None) -> None:
    cursor.execute(
        """
        INSERT INTO billing.qris_manual_payment_events
        (payment_id, event_type, actor_id, message, metadata_json)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (
            payment_id,
            event_type,
            actor_id,
            message,
            json.dumps(dict(metadata or {}), ensure_ascii=False, separators=(",", ":"), default=str),
        ),
    )


def prepare_payment(*, order_id: str, user_id: str, buyer_email: str | None,
                    amount: Any, product_code: str | None = None) -> dict[str, Any]:
    initialize_qris_schema()
    order_id = str(order_id).strip()
    user_id = str(user_id).strip()
    normalized_amount = normalize_amount(amount)
    if not order_id or not user_id:
        raise QrisPaymentError("order_id dan user_id wajib tersedia.")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM billing.qris_manual_payments WHERE order_id = %s FOR UPDATE",
                (order_id,),
            )
            existing = cursor.fetchone()
            if existing is None:
                payment_id = "qris_" + uuid.uuid4().hex
                cursor.execute(
                    """
                    INSERT INTO billing.qris_manual_payments
                    (payment_id, order_id, user_id, buyer_email, product_code, amount, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'prepared')
                    RETURNING *
                    """,
                    (payment_id, order_id, user_id, buyer_email, product_code, normalized_amount),
                )
                row = cursor.fetchone()
                _event(cursor, payment_id, "prepared", user_id, "Pembayaran QRIS disiapkan.",
                       {"amount": str(normalized_amount)})
            else:
                if str(existing["user_id"]) != user_id:
                    raise QrisPaymentOwnershipError("Order dimiliki pengguna lain.")
                if str(existing["status"]) == "approved":
                    return serialize(dict(existing))
                next_status = "submitted" if existing.get("proof_reference") else "prepared"
                cursor.execute(
                    """
                    UPDATE billing.qris_manual_payments
                    SET buyer_email = %s, product_code = %s, amount = %s, status = %s,
                        reviewed_by = NULL, reviewed_at = NULL, rejection_reason = NULL,
                        updated_at = NOW()
                    WHERE payment_id = %s
                    RETURNING *
                    """,
                    (buyer_email, product_code, normalized_amount, next_status, existing["payment_id"]),
                )
                row = cursor.fetchone()
                _event(cursor, str(existing["payment_id"]), "prepared_again", user_id,
                       "Pembayaran QRIS diperbarui.", {"amount": str(normalized_amount)})

    if row is None:
        raise QrisPaymentError("Pembayaran QRIS gagal disiapkan.")
    return serialize(dict(row))


def get_payment_by_order(order_id: str) -> dict[str, Any] | None:
    initialize_qris_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM billing.qris_manual_payments WHERE order_id = %s LIMIT 1",
                (str(order_id),),
            )
            row = cursor.fetchone()
    return serialize(dict(row)) if row is not None else None


def attach_proof(*, order_id: str, user_id: str, proof_reference: str,
                 proof_filename: str, proof_content_type: str, proof_size: int,
                 payer_name: str | None = None, payment_note: str | None = None) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM billing.qris_manual_payments WHERE order_id = %s FOR UPDATE",
                (str(order_id),),
            )
            current = cursor.fetchone()
            if current is None:
                raise QrisPaymentNotFoundError(str(order_id))
            if str(current["user_id"]) != str(user_id):
                raise QrisPaymentOwnershipError("Pembayaran dimiliki pengguna lain.")
            if str(current["status"]) in {"approved", "canceled"}:
                raise QrisPaymentError("Bukti tidak dapat diubah pada status saat ini.")

            cursor.execute(
                """
                UPDATE billing.qris_manual_payments
                SET proof_reference = %s, proof_filename = %s, proof_content_type = %s,
                    proof_size = %s, payer_name = %s, payment_note = %s,
                    status = 'submitted', submitted_at = NOW(), reviewed_by = NULL,
                    reviewed_at = NULL, rejection_reason = NULL, updated_at = NOW()
                WHERE payment_id = %s
                RETURNING *
                """,
                (proof_reference, proof_filename, proof_content_type, int(proof_size),
                 payer_name, payment_note, current["payment_id"]),
            )
            row = cursor.fetchone()
            _event(cursor, str(current["payment_id"]), "proof_submitted", str(user_id),
                   "Bukti pembayaran diunggah.", {"proof_reference": proof_reference})

    if row is None:
        raise QrisPaymentError("Bukti pembayaran gagal disimpan.")
    return serialize(dict(row))


def list_payments(*, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    initialize_qris_schema()
    limit = max(1, min(500, int(limit)))
    with connect() as connection:
        with connection.cursor() as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM billing.qris_manual_payments WHERE status = %s ORDER BY updated_at DESC LIMIT %s",
                    (str(status), limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM billing.qris_manual_payments ORDER BY updated_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cursor.fetchall()
    return [serialize(dict(row)) for row in rows]


def mark_approved(*, order_id: str, reviewer_id: str,
                  activation_response: Mapping[str, Any], worker_job_id: str | None) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM billing.qris_manual_payments WHERE order_id = %s FOR UPDATE",
                (str(order_id),),
            )
            current = cursor.fetchone()
            if current is None:
                raise QrisPaymentNotFoundError(str(order_id))
            if str(current["status"]) == "approved":
                return serialize(dict(current))
            if str(current["status"]) != "submitted":
                raise QrisPaymentError("Hanya pembayaran submitted yang dapat disetujui.")

            cursor.execute(
                """
                UPDATE billing.qris_manual_payments
                SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(),
                    rejection_reason = NULL, activation_response = %s::jsonb,
                    worker_job_id = %s, updated_at = NOW()
                WHERE payment_id = %s
                RETURNING *
                """,
                (
                    str(reviewer_id),
                    json.dumps(dict(activation_response), ensure_ascii=False,
                               separators=(",", ":"), default=str),
                    worker_job_id,
                    current["payment_id"],
                ),
            )
            row = cursor.fetchone()
            _event(cursor, str(current["payment_id"]), "approved", str(reviewer_id),
                   "Pembayaran QRIS disetujui.", {"worker_job_id": worker_job_id})

    if row is None:
        raise QrisPaymentError("Pembayaran gagal disetujui.")
    return serialize(dict(row))


def mark_rejected(*, order_id: str, reviewer_id: str, reason: str) -> dict[str, Any]:
    reason = str(reason).strip()
    if not reason:
        raise QrisPaymentError("Alasan penolakan wajib diisi.")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM billing.qris_manual_payments WHERE order_id = %s FOR UPDATE",
                (str(order_id),),
            )
            current = cursor.fetchone()
            if current is None:
                raise QrisPaymentNotFoundError(str(order_id))
            if str(current["status"]) == "approved":
                raise QrisPaymentError("Pembayaran yang sudah disetujui tidak dapat ditolak.")

            cursor.execute(
                """
                UPDATE billing.qris_manual_payments
                SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(),
                    rejection_reason = %s, updated_at = NOW()
                WHERE payment_id = %s
                RETURNING *
                """,
                (str(reviewer_id), reason, current["payment_id"]),
            )
            row = cursor.fetchone()
            _event(cursor, str(current["payment_id"]), "rejected", str(reviewer_id), reason)

    if row is None:
        raise QrisPaymentError("Pembayaran gagal ditolak.")
    return serialize(dict(row))


def delete_payment(order_id: str) -> bool:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM billing.qris_manual_payments WHERE order_id = %s",
                (str(order_id),),
            )
            return cursor.rowcount == 1


def qris_health() -> dict[str, Any]:
    initialize_qris_schema()
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, COUNT(*) AS total FROM billing.qris_manual_payments GROUP BY status"
            )
            rows = cursor.fetchall()
    return {
        "status": "ready",
        "mode": "manual_verification",
        "provider_webhook": False,
        "proof_required": True,
        "admin_review_required": True,
        "billing_activation_bridge": "existing_simulate_pay_route",
        "counts": {str(row["status"]): int(row["total"]) for row in rows},
    }
