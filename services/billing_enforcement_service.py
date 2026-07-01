from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from billing_database import (
    connect,
    initialize_billing_database,
)
from services.billing_service import (
    create_order,
    complete_order_payment,
)


OPERATION_SERVICE_MAP = {
    "format": "format_academic",
    "formatter": "format_academic",
    "format-document": "format_academic",
    "format_document": "format_academic",
    "format-academic": "format_academic",
    "format_academic": "format_academic",
    "academic-format": "format_academic",
    "academic_format": "format_academic",
    "skripsi": "format_academic",
    "thesis": "format_academic",

    "format-simple": "format_simple",
    "format_simple": "format_simple",
    "simple-format": "format_simple",
    "simple_format": "format_simple",

    "audit": "academic_audit",
    "academic-audit": "academic_audit",
    "academic_audit": "academic_audit",
    "audit-document": "academic_audit",
    "audit_document": "academic_audit",

    "journal": "journal_conversion",
    "journal-conversion": "journal_conversion",
    "journal_conversion": "journal_conversion",
    "convert-journal": "journal_conversion",
    "convert_journal": "journal_conversion",

    "template": "template_format",
    "template-format": "template_format",
    "template_format": "template_format",
    "format-template": "template_format",
    "format_template": "template_format",

    "batch": "batch_processing",
    "batch-processing": "batch_processing",
    "batch_processing": "batch_processing",
    "batch-format": "batch_processing",
    "batch_format": "batch_processing",
}


DIRECT_PATH_SERVICE_MAP = {
    "/api/format": "format_academic",
    "/api/format-document": "format_academic",
    "/api/document/format": "format_academic",

    "/api/audit/run": "academic_audit",
    "/api/academic-audit/run": "academic_audit",

    "/api/journal/convert": "journal_conversion",
    "/api/journal/transform": "journal_conversion",

    "/api/template/format": "template_format",

    "/api/batch/process": "batch_processing",
    "/api/batch/format": "batch_processing",
}


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def utc_now_text() -> str:
    return utc_now().isoformat()


def enforcement_mode() -> str:
    mode = os.getenv(
        "DOCURAPI_BILLING_ENFORCEMENT",
        "enabled",
    ).strip().lower()

    valid_modes = {
        "disabled",
        "monitor",
        "enabled",
        "strict",
    }

    if mode not in valid_modes:
        return "enabled"

    return mode


def admin_bypass_enabled() -> bool:
    return os.getenv(
        "DOCURAPI_BILLING_ADMIN_BYPASS",
        "1",
    ).strip() == "1"


def reservation_ttl_minutes() -> int:
    raw_value = os.getenv(
        "DOCURAPI_BILLING_RESERVATION_TTL",
        "30",
    )

    try:
        value = int(raw_value)
    except ValueError:
        value = 30

    return max(
        5,
        min(value, 180),
    )


def initialize_enforcement_database() -> None:
    initialize_billing_database()

    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                billing_access_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    reservation_token TEXT NOT NULL UNIQUE,
                    entitlement_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    service_code TEXT NOT NULL,
                    operation TEXT,
                    request_reference TEXT,
                    processing_reference TEXT,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    failure_reason TEXT,
                    created_at TEXT NOT NULL,
                    finalized_at TEXT,
                    released_at TEXT,
                    FOREIGN KEY(entitlement_id)
                        REFERENCES billing_entitlements(
                            entitlement_id
                        )
                        ON DELETE CASCADE
                );

            CREATE INDEX IF NOT EXISTS
                idx_billing_reservation_user
            ON billing_access_reservations(
                user_id,
                created_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_reservation_status
            ON billing_access_reservations(
                status,
                expires_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_reservation_entitlement
            ON billing_access_reservations(
                entitlement_id,
                status
            );
            """
        )

        connection.commit()


def normalize_operation(
    operation: str,
) -> str:
    return (
        str(operation)
        .strip()
        .lower()
        .replace(" ", "-")
    )


def service_code_for_operation(
    operation: str,
) -> str | None:
    normalized = normalize_operation(
        operation
    )

    return OPERATION_SERVICE_MAP.get(
        normalized
    )


def service_code_for_path(
    path: str,
) -> str | None:
    normalized_path = (
        str(path)
        .strip()
        .lower()
        .rstrip("/")
    )

    if normalized_path.startswith(
        "/api/background/submit/"
    ):
        operation = normalized_path.rsplit(
            "/",
            1,
        )[-1]

        return service_code_for_operation(
            operation
        )

    return DIRECT_PATH_SERVICE_MAP.get(
        normalized_path
    )


def operation_from_path(
    path: str,
) -> str | None:
    normalized_path = (
        str(path)
        .strip()
        .lower()
        .rstrip("/")
    )

    if normalized_path.startswith(
        "/api/background/submit/"
    ):
        return normalized_path.rsplit(
            "/",
            1,
        )[-1]

    if normalized_path in DIRECT_PATH_SERVICE_MAP:
        return normalized_path

    return None


def cleanup_expired_reservations() -> int:
    initialize_enforcement_database()

    now_text = utc_now_text()

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        expired_rows = connection.execute(
            """
            SELECT
                reservation_id,
                entitlement_id
            FROM billing_access_reservations
            WHERE status = 'reserved'
              AND expires_at <= ?
            """,
            (now_text,),
        ).fetchall()

        for row in expired_rows:
            connection.execute(
                """
                UPDATE billing_entitlements
                SET status = 'available'
                WHERE entitlement_id = ?
                  AND status = 'reserved'
                """,
                (
                    row["entitlement_id"],
                ),
            )

            connection.execute(
                """
                UPDATE billing_access_reservations
                SET
                    status = 'expired',
                    failure_reason = 'reservation_timeout',
                    released_at = ?
                WHERE reservation_id = ?
                """,
                (
                    now_text,
                    row["reservation_id"],
                ),
            )

        connection.commit()

    return len(
        expired_rows
    )


def available_entitlement_count(
    user_id: str,
    service_code: str,
) -> int:
    cleanup_expired_reservations()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM billing_entitlements
            WHERE user_id = ?
              AND service_code = ?
              AND status = 'available'
              AND (
                    expires_at IS NULL
                    OR expires_at > ?
              )
            """,
            (
                str(user_id),
                service_code,
                utc_now_text(),
            ),
        ).fetchone()

    return int(
        row["total"]
        if row
        else 0
    )


def check_access(
    user_id: str,
    operation: str,
) -> dict[str, Any]:
    service_code = service_code_for_operation(
        operation
    )

    if not service_code:
        return {
            "mapped": False,
            "operation": operation,
            "service_code": None,
            "available": False,
            "available_count": 0,
            "checkout_url": "/billing",
        }

    count = available_entitlement_count(
        user_id=user_id,
        service_code=service_code,
    )

    return {
        "mapped": True,
        "operation": operation,
        "service_code": service_code,
        "available": count > 0,
        "available_count": count,
        "checkout_url": (
            "/billing?service="
            + service_code
        ),
    }


def reserve_processing_access(
    user_id: str,
    service_code: str,
    operation: str | None = None,
    request_reference: str | None = None,
) -> dict[str, Any]:
    initialize_enforcement_database()
    cleanup_expired_reservations()

    reservation_id = uuid4().hex
    reservation_token = uuid4().hex

    created_at = utc_now()
    expires_at = (
        created_at
        + timedelta(
            minutes=reservation_ttl_minutes()
        )
    )

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        entitlement = connection.execute(
            """
            SELECT *
            FROM billing_entitlements
            WHERE user_id = ?
              AND service_code = ?
              AND status = 'available'
              AND (
                    expires_at IS NULL
                    OR expires_at > ?
              )
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (
                str(user_id),
                service_code,
                created_at.isoformat(),
            ),
        ).fetchone()

        if not entitlement:
            connection.rollback()

            raise ValueError(
                (
                    "Hak pemrosesan tidak tersedia "
                    "untuk layanan ini."
                )
            )

        entitlement_id = entitlement[
            "entitlement_id"
        ]

        updated = connection.execute(
            """
            UPDATE billing_entitlements
            SET status = 'reserved'
            WHERE entitlement_id = ?
              AND status = 'available'
            """,
            (
                entitlement_id,
            ),
        )

        if updated.rowcount != 1:
            connection.rollback()

            raise RuntimeError(
                (
                    "Entitlement sedang digunakan "
                    "oleh proses lain."
                )
            )

        connection.execute(
            """
            INSERT INTO billing_access_reservations (
                reservation_id,
                reservation_token,
                entitlement_id,
                user_id,
                service_code,
                operation,
                request_reference,
                processing_reference,
                status,
                expires_at,
                failure_reason,
                created_at,
                finalized_at,
                released_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, NULL,
                'reserved', ?, NULL, ?, NULL, NULL
            )
            """,
            (
                reservation_id,
                reservation_token,
                entitlement_id,
                str(user_id),
                service_code,
                operation,
                request_reference,
                expires_at.isoformat(),
                created_at.isoformat(),
            ),
        )

        connection.commit()

    return {
        "reservation_id": reservation_id,
        "reservation_token": reservation_token,
        "entitlement_id": entitlement_id,
        "user_id": str(user_id),
        "service_code": service_code,
        "operation": operation,
        "status": "reserved",
        "expires_at": expires_at.isoformat(),
    }


def get_reservation(
    reservation_token: str,
) -> dict[str, Any] | None:
    initialize_enforcement_database()

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM billing_access_reservations
            WHERE reservation_token = ?
            """,
            (
                reservation_token,
            ),
        ).fetchone()

    return dict(row) if row else None


def finalize_processing_access(
    reservation_token: str,
    processing_reference: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    initialize_enforcement_database()

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        reservation = connection.execute(
            """
            SELECT *
            FROM billing_access_reservations
            WHERE reservation_token = ?
            """,
            (
                reservation_token,
            ),
        ).fetchone()

        if not reservation:
            connection.rollback()

            raise ValueError(
                "Reservasi billing tidak ditemukan."
            )

        reservation_data = dict(
            reservation
        )

        if (
            user_id is not None
            and str(
                reservation_data["user_id"]
            )
            != str(user_id)
        ):
            connection.rollback()

            raise PermissionError(
                "Reservasi bukan milik pengguna ini."
            )

        if reservation_data["status"] == "consumed":
            connection.commit()

            reservation_data["idempotent"] = True

            return reservation_data

        if reservation_data["status"] != "reserved":
            connection.rollback()

            raise ValueError(
                (
                    "Reservasi tidak dapat diselesaikan "
                    f"dari status "
                    f"{reservation_data['status']}."
                )
            )

        if datetime.fromisoformat(
            reservation_data["expires_at"]
        ) <= utc_now():
            connection.execute(
                """
                UPDATE billing_entitlements
                SET status = 'available'
                WHERE entitlement_id = ?
                  AND status = 'reserved'
                """,
                (
                    reservation_data[
                        "entitlement_id"
                    ],
                ),
            )

            connection.execute(
                """
                UPDATE billing_access_reservations
                SET
                    status = 'expired',
                    failure_reason = 'reservation_timeout',
                    released_at = ?
                WHERE reservation_token = ?
                """,
                (
                    utc_now_text(),
                    reservation_token,
                ),
            )

            connection.commit()

            raise ValueError(
                "Reservasi billing sudah kedaluwarsa."
            )

        current_time = utc_now_text()

        updated = connection.execute(
            """
            UPDATE billing_entitlements
            SET
                status = 'consumed',
                consumed_at = ?,
                consumed_reference = ?
            WHERE entitlement_id = ?
              AND status = 'reserved'
            """,
            (
                current_time,
                processing_reference,
                reservation_data[
                    "entitlement_id"
                ],
            ),
        )

        if updated.rowcount != 1:
            connection.rollback()

            raise RuntimeError(
                "Entitlement gagal dikonsumsi."
            )

        connection.execute(
            """
            UPDATE billing_access_reservations
            SET
                status = 'consumed',
                processing_reference = ?,
                finalized_at = ?
            WHERE reservation_token = ?
            """,
            (
                processing_reference,
                current_time,
                reservation_token,
            ),
        )

        connection.commit()

    result = get_reservation(
        reservation_token
    )

    result["idempotent"] = False

    return result


def release_processing_access(
    reservation_token: str,
    reason: str = "processing_failed",
    user_id: str | None = None,
) -> dict[str, Any]:
    initialize_enforcement_database()

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        reservation = connection.execute(
            """
            SELECT *
            FROM billing_access_reservations
            WHERE reservation_token = ?
            """,
            (
                reservation_token,
            ),
        ).fetchone()

        if not reservation:
            connection.rollback()

            raise ValueError(
                "Reservasi billing tidak ditemukan."
            )

        reservation_data = dict(
            reservation
        )

        if (
            user_id is not None
            and str(
                reservation_data["user_id"]
            )
            != str(user_id)
        ):
            connection.rollback()

            raise PermissionError(
                "Reservasi bukan milik pengguna ini."
            )

        if reservation_data["status"] in {
            "released",
            "expired",
        }:
            connection.commit()

            reservation_data["idempotent"] = True

            return reservation_data

        if reservation_data["status"] == "consumed":
            connection.rollback()

            raise ValueError(
                (
                    "Reservasi sudah dikonsumsi "
                    "dan tidak dapat dilepas."
                )
            )

        current_time = utc_now_text()

        connection.execute(
            """
            UPDATE billing_entitlements
            SET status = 'available'
            WHERE entitlement_id = ?
              AND status = 'reserved'
            """,
            (
                reservation_data[
                    "entitlement_id"
                ],
            ),
        )

        connection.execute(
            """
            UPDATE billing_access_reservations
            SET
                status = 'released',
                failure_reason = ?,
                released_at = ?
            WHERE reservation_token = ?
            """,
            (
                reason[:1000],
                current_time,
                reservation_token,
            ),
        )

        connection.commit()

    result = get_reservation(
        reservation_token
    )

    result["idempotent"] = False

    return result


def list_user_reservations(
    user_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cleanup_expired_reservations()

    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM billing_access_reservations
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                str(user_id),
                safe_limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def list_all_reservations(
    limit: int = 200,
    status: str | None = None,
) -> list[dict[str, Any]]:
    cleanup_expired_reservations()

    safe_limit = max(
        1,
        min(int(limit), 1000),
    )

    with connect() as connection:
        if status:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_access_reservations
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    status,
                    safe_limit,
                ),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_access_reservations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    safe_limit,
                ),
            ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def enforcement_health() -> dict[str, Any]:
    initialize_enforcement_database()

    expired_cleaned = (
        cleanup_expired_reservations()
    )

    with connect() as connection:
        quick_check = connection.execute(
            "PRAGMA quick_check"
        ).fetchone()

        active_reservations = (
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM billing_access_reservations
                WHERE status = 'reserved'
                """
            ).fetchone()["total"]
        )

    return {
        "status": (
            "ok"
            if quick_check
            and quick_check[0] == "ok"
            else "degraded"
        ),
        "mode": enforcement_mode(),
        "admin_bypass": (
            admin_bypass_enabled()
        ),
        "reservation_ttl_minutes": (
            reservation_ttl_minutes()
        ),
        "active_reservations": int(
            active_reservations
        ),
        "expired_cleaned": int(
            expired_cleaned
        ),
        "mapped_operations": len(
            OPERATION_SERVICE_MAP
        ),
        "mapped_direct_paths": len(
            DIRECT_PATH_SERVICE_MAP
        ),
    }


def run_enforcement_self_test() -> dict[str, Any]:
    initialize_enforcement_database()

    test_user_id = (
        "__billing_enforcement_test__"
        + uuid4().hex
    )

    order_id = None

    try:
        order = create_order(
            user_id=test_user_id,
            user_email=(
                "billing-enforcement@local.invalid"
            ),
            product_code="format_simple",
            quantity=1,
            idempotency_key=uuid4().hex,
            metadata={
                "enforcement_self_test": True,
            },
        )

        order_id = order["order_id"]

        paid_order = complete_order_payment(
            order_id=order_id,
            provider="enforcement_self_test",
            transaction_id=(
                "ENFORCEMENT-"
                + uuid4().hex
            ),
            payload={
                "enforcement_self_test": True,
            },
        )

        first_reservation = (
            reserve_processing_access(
                user_id=test_user_id,
                service_code="format_simple",
                operation="format-simple",
                request_reference="release-test",
            )
        )

        released = release_processing_access(
            reservation_token=(
                first_reservation[
                    "reservation_token"
                ]
            ),
            reason="self_test_release",
            user_id=test_user_id,
        )

        second_reservation = (
            reserve_processing_access(
                user_id=test_user_id,
                service_code="format_simple",
                operation="format-simple",
                request_reference="consume-test",
            )
        )

        consumed = finalize_processing_access(
            reservation_token=(
                second_reservation[
                    "reservation_token"
                ]
            ),
            processing_reference=(
                "self-test-processing"
            ),
            user_id=test_user_id,
        )

        if paid_order["status"] != "paid":
            raise RuntimeError(
                "Order self-test tidak berstatus paid."
            )

        if released["status"] != "released":
            raise RuntimeError(
                "Reservasi self-test tidak dapat dilepas."
            )

        if consumed["status"] != "consumed":
            raise RuntimeError(
                "Reservasi self-test tidak dapat dikonsumsi."
            )

        return {
            "status": "passed",
            "payment_status": (
                paid_order["status"]
            ),
            "release_status": (
                released["status"]
            ),
            "consume_status": (
                consumed["status"]
            ),
        }

    finally:
        with connect() as connection:
            connection.execute(
                """
                DELETE FROM billing_access_reservations
                WHERE user_id = ?
                """,
                (
                    test_user_id,
                ),
            )

            connection.execute(
                """
                DELETE FROM billing_credit_ledger
                WHERE user_id = ?
                """,
                (
                    test_user_id,
                ),
            )

            connection.execute(
                """
                DELETE FROM billing_wallets
                WHERE user_id = ?
                """,
                (
                    test_user_id,
                ),
            )

            connection.execute(
                """
                DELETE FROM billing_entitlements
                WHERE user_id = ?
                """,
                (
                    test_user_id,
                ),
            )

            if order_id:
                connection.execute(
                    """
                    DELETE FROM billing_orders
                    WHERE order_id = ?
                    """,
                    (
                        order_id,
                    ),
                )

            connection.commit()


initialize_enforcement_database()
