from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from billing_database import (
    BILLING_DATABASE_PATH,
    connect,
    initialize_billing_database,
    row_to_dict,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def utc_now_text() -> str:
    return utc_now().isoformat()


def payment_mode() -> str:
    return os.getenv(
        "DOCURAPI_PAYMENT_MODE",
        "simulation",
    ).strip().lower()


def tax_percent() -> int:
    raw_value = os.getenv(
        "DOCURAPI_BILLING_TAX_PERCENT",
        "0",
    )

    try:
        value = int(raw_value)
    except ValueError:
        value = 0

    return max(
        0,
        min(value, 100),
    )


def format_idr(
    amount: int,
) -> str:
    return (
        "Rp"
        + f"{int(amount):,}".replace(
            ",",
            ".",
        )
    )


def generate_reference(
    prefix: str,
) -> str:
    date_part = utc_now().strftime(
        "%Y%m%d"
    )

    random_part = secrets.token_hex(
        4
    ).upper()

    return (
        f"{prefix}-{date_part}-"
        f"{random_part}"
    )


def notify_user(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: str | None = None,
) -> None:
    try:
        from services.notification_service import (
            create_notification,
        )

        create_notification(
            user_id=str(user_id),
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
        )
    except Exception:
        return


def get_catalog(
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    initialize_billing_database()

    with connect() as connection:
        if include_inactive:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_products
                ORDER BY sort_order, name
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_products
                WHERE active = 1
                ORDER BY sort_order, name
                """
            ).fetchall()

    products = []

    for row in rows:
        item = dict(row)

        item["active"] = bool(
            item["active"]
        )

        item["formatted_price"] = format_idr(
            item["price_idr"]
        )

        products.append(item)

    return products


def get_product(
    product_code: str,
    active_only: bool = True,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    own_connection = connection is None

    database = (
        connection
        if connection is not None
        else connect()
    )

    try:
        if active_only:
            row = database.execute(
                """
                SELECT *
                FROM billing_products
                WHERE product_code = ?
                  AND active = 1
                """,
                (product_code,),
            ).fetchone()
        else:
            row = database.execute(
                """
                SELECT *
                FROM billing_products
                WHERE product_code = ?
                """,
                (product_code,),
            ).fetchone()

        result = dict(row) if row else None

        if result:
            result["active"] = bool(
                result["active"]
            )

        return result

    finally:
        if own_connection:
            database.close()


def create_quote(
    product_code: str,
    quantity: int = 1,
) -> dict[str, Any]:
    safe_quantity = max(
        1,
        min(int(quantity), 100),
    )

    product = get_product(
        product_code
    )

    if not product:
        raise ValueError(
            "Produk tidak ditemukan atau tidak aktif."
        )

    subtotal = (
        int(product["price_idr"])
        * safe_quantity
    )

    discount = 0

    calculated_tax = round(
        subtotal
        * tax_percent()
        / 100
    )

    total = (
        subtotal
        - discount
        + calculated_tax
    )

    return {
        "product": product,
        "quantity": safe_quantity,
        "currency": "IDR",
        "subtotal": subtotal,
        "discount": discount,
        "tax": calculated_tax,
        "tax_percent": tax_percent(),
        "total": total,
        "formatted_subtotal": format_idr(
            subtotal
        ),
        "formatted_tax": format_idr(
            calculated_tax
        ),
        "formatted_total": format_idr(
            total
        ),
    }


def get_order(
    order_id: str,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    own_connection = connection is None

    database = (
        connection
        if connection is not None
        else connect()
    )

    try:
        row = database.execute(
            """
            SELECT *
            FROM billing_orders
            WHERE order_id = ?
            """,
            (order_id,),
        ).fetchone()

        order = row_to_dict(row)

        if not order:
            return None

        item_rows = database.execute(
            """
            SELECT *
            FROM billing_order_items
            WHERE order_id = ?
            ORDER BY created_at
            """,
            (order_id,),
        ).fetchall()

        payment_rows = database.execute(
            """
            SELECT *
            FROM billing_payments
            WHERE order_id = ?
            ORDER BY created_at
            """,
            (order_id,),
        ).fetchall()

        order["items"] = [
            row_to_dict(item)
            for item in item_rows
        ]

        order["payments"] = [
            row_to_dict(payment)
            for payment in payment_rows
        ]

        order["formatted_total"] = format_idr(
            order["total"]
        )

        return order

    finally:
        if own_connection:
            database.close()


def create_order(
    user_id: str,
    user_email: str | None,
    product_code: str,
    quantity: int = 1,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_billing_database()

    safe_user_id = str(user_id)

    safe_idempotency_key = (
        idempotency_key.strip()
        if idempotency_key
        else uuid4().hex
    )

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT order_id
            FROM billing_orders
            WHERE user_id = ?
              AND idempotency_key = ?
            """,
            (
                safe_user_id,
                safe_idempotency_key,
            ),
        ).fetchone()

        if existing:
            return get_order(
                existing["order_id"],
                connection,
            )

        product = get_product(
            product_code,
            connection=connection,
        )

        if not product:
            raise ValueError(
                "Produk tidak ditemukan atau tidak aktif."
            )

        quote = create_quote(
            product_code,
            quantity,
        )

        order_id = uuid4().hex
        order_item_id = uuid4().hex

        order_number = generate_reference(
            "ORD"
        )

        invoice_number = generate_reference(
            "INV"
        )

        current_time = utc_now_text()

        expires_at = (
            utc_now()
            + timedelta(hours=2)
        ).isoformat()

        connection.execute(
            """
            INSERT INTO billing_orders (
                order_id,
                order_number,
                invoice_number,
                user_id,
                user_email,
                status,
                currency,
                subtotal,
                discount,
                tax,
                total,
                payment_mode,
                idempotency_key,
                metadata_json,
                expires_at,
                paid_at,
                canceled_at,
                refunded_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, 'pending',
                'IDR', ?, ?, ?, ?, ?, ?, ?,
                ?, NULL, NULL, NULL, ?, ?
            )
            """,
            (
                order_id,
                order_number,
                invoice_number,
                safe_user_id,
                user_email,
                quote["subtotal"],
                quote["discount"],
                quote["tax"],
                quote["total"],
                payment_mode(),
                safe_idempotency_key,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
                expires_at,
                current_time,
                current_time,
            ),
        )

        connection.execute(
            """
            INSERT INTO billing_order_items (
                order_item_id,
                order_id,
                product_code,
                product_name,
                product_type,
                service_code,
                quantity,
                unit_price,
                line_total,
                credit_cost,
                credit_amount,
                snapshot_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_item_id,
                order_id,
                product["product_code"],
                product["name"],
                product["product_type"],
                product["service_code"],
                quote["quantity"],
                product["price_idr"],
                quote["subtotal"],
                product["credit_cost"],
                product["credit_amount"],
                json.dumps(
                    product,
                    ensure_ascii=False,
                ),
                current_time,
            ),
        )

        connection.commit()

    return get_order(
        order_id
    )


def ensure_wallet(
    user_id: str,
    connection: sqlite3.Connection,
) -> int:
    row = connection.execute(
        """
        SELECT credit_balance
        FROM billing_wallets
        WHERE user_id = ?
        """,
        (str(user_id),),
    ).fetchone()

    if row:
        return int(
            row["credit_balance"]
        )

    connection.execute(
        """
        INSERT INTO billing_wallets (
            user_id,
            credit_balance,
            updated_at
        )
        VALUES (?, 0, ?)
        """,
        (
            str(user_id),
            utc_now_text(),
        ),
    )

    return 0


def record_credit_change(
    connection: sqlite3.Connection,
    user_id: str,
    amount: int,
    entry_type: str,
    reference_type: str | None,
    reference_id: str | None,
    description: str,
) -> int:
    current_balance = ensure_wallet(
        user_id,
        connection,
    )

    new_balance = (
        current_balance
        + int(amount)
    )

    if new_balance < 0:
        raise ValueError(
            "Saldo kredit tidak mencukupi."
        )

    current_time = utc_now_text()

    connection.execute(
        """
        UPDATE billing_wallets
        SET
            credit_balance = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (
            new_balance,
            current_time,
            str(user_id),
        ),
    )

    connection.execute(
        """
        INSERT INTO billing_credit_ledger (
            ledger_id,
            user_id,
            amount,
            balance_after,
            entry_type,
            reference_type,
            reference_id,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid4().hex,
            str(user_id),
            int(amount),
            new_balance,
            entry_type,
            reference_type,
            reference_id,
            description,
            current_time,
        ),
    )

    return new_balance


def issue_processing_entitlements(
    connection: sqlite3.Connection,
    order: dict[str, Any],
) -> int:
    issued = 0

    for item in order["items"]:
        if item["product_type"] != "processing":
            continue

        quantity = int(
            item["quantity"]
        )

        for _ in range(quantity):
            connection.execute(
                """
                INSERT INTO billing_entitlements (
                    entitlement_id,
                    order_id,
                    order_item_id,
                    user_id,
                    service_code,
                    status,
                    source_type,
                    source_reference,
                    expires_at,
                    consumed_at,
                    consumed_reference,
                    refunded_at,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, 'available',
                    'direct_payment', ?, NULL,
                    NULL, NULL, NULL, ?
                )
                """,
                (
                    uuid4().hex,
                    order["order_id"],
                    item["order_item_id"],
                    order["user_id"],
                    item["service_code"],
                    order["order_number"],
                    utc_now_text(),
                ),
            )

            issued += 1

    return issued


def issue_credit_pack(
    connection: sqlite3.Connection,
    order: dict[str, Any],
) -> int:
    credit_total = 0

    for item in order["items"]:
        if item["product_type"] != "credit_pack":
            continue

        credit_total += (
            int(item["credit_amount"])
            * int(item["quantity"])
        )

    if credit_total <= 0:
        return 0

    record_credit_change(
        connection=connection,
        user_id=order["user_id"],
        amount=credit_total,
        entry_type="purchase",
        reference_type="order",
        reference_id=order["order_id"],
        description=(
            f"Pembelian kredit melalui "
            f"{order['order_number']}"
        ),
    )

    return credit_total


def complete_order_payment(
    order_id: str,
    provider: str,
    transaction_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    initialize_billing_database()

    notification_payload = None

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        order = get_order(
            order_id,
            connection,
        )

        if not order:
            raise ValueError(
                "Pesanan tidak ditemukan."
            )

        if order["status"] == "paid":
            connection.commit()

            order["idempotent"] = True

            return order

        if order["status"] != "pending":
            raise ValueError(
                (
                    "Pesanan tidak dapat dibayar "
                    f"dari status {order['status']}."
                )
            )

        if order.get("expires_at"):
            expires_at = datetime.fromisoformat(
                order["expires_at"]
            )

            if expires_at <= utc_now():
                connection.execute(
                    """
                    UPDATE billing_orders
                    SET
                        status = 'expired',
                        updated_at = ?
                    WHERE order_id = ?
                    """,
                    (
                        utc_now_text(),
                        order_id,
                    ),
                )

                connection.commit()

                raise ValueError(
                    "Pesanan sudah kedaluwarsa."
                )

        current_time = utc_now_text()

        connection.execute(
            """
            INSERT OR IGNORE INTO billing_payments (
                payment_id,
                order_id,
                provider,
                transaction_id,
                status,
                amount,
                currency,
                provider_payload_json,
                paid_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, 'paid', ?, 'IDR',
                ?, ?, ?, ?
            )
            """,
            (
                uuid4().hex,
                order_id,
                provider,
                transaction_id,
                order["total"],
                json.dumps(
                    payload or {},
                    ensure_ascii=False,
                ),
                current_time,
                current_time,
                current_time,
            ),
        )

        connection.execute(
            """
            UPDATE billing_orders
            SET
                status = 'paid',
                paid_at = ?,
                updated_at = ?
            WHERE order_id = ?
            """,
            (
                current_time,
                current_time,
                order_id,
            ),
        )

        issued_entitlements = (
            issue_processing_entitlements(
                connection,
                order,
            )
        )

        issued_credits = issue_credit_pack(
            connection,
            order,
        )

        connection.commit()

        notification_payload = {
            "user_id": order["user_id"],
            "order_number": order["order_number"],
            "issued_entitlements": (
                issued_entitlements
            ),
            "issued_credits": issued_credits,
        }

    notify_user(
        user_id=notification_payload[
            "user_id"
        ],
        title="Pembayaran berhasil",
        message=(
            f"Pembayaran pesanan "
            f"{notification_payload['order_number']} "
            "telah diterima."
        ),
        notification_type="success",
        action_url="/billing",
    )

    result = get_order(
        order_id
    )

    result["issued_entitlements"] = (
        notification_payload[
            "issued_entitlements"
        ]
    )

    result["issued_credits"] = (
        notification_payload[
            "issued_credits"
        ]
    )

    result["idempotent"] = False

    return result


def simulate_payment(
    order_id: str,
    user_id: str,
) -> dict[str, Any]:
    if payment_mode() != "simulation":
        raise ValueError(
            (
                "Pembayaran simulasi hanya tersedia "
                "ketika DOCURAPI_PAYMENT_MODE=simulation."
            )
        )

    order = get_order(
        order_id
    )

    if not order:
        raise ValueError(
            "Pesanan tidak ditemukan."
        )

    if str(order["user_id"]) != str(user_id):
        raise PermissionError(
            "Pesanan bukan milik pengguna ini."
        )

    return complete_order_payment(
        order_id=order_id,
        provider="simulated",
        transaction_id=(
            "SIM-"
            + uuid4().hex.upper()
        ),
        payload={
            "mode": "simulation",
            "source": "local_checkout",
        },
    )


def cancel_order(
    order_id: str,
    user_id: str,
) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        order = get_order(
            order_id,
            connection,
        )

        if not order:
            raise ValueError(
                "Pesanan tidak ditemukan."
            )

        if str(order["user_id"]) != str(user_id):
            raise PermissionError(
                "Pesanan bukan milik pengguna ini."
            )

        if order["status"] != "pending":
            raise ValueError(
                "Hanya pesanan pending yang dapat dibatalkan."
            )

        current_time = utc_now_text()

        connection.execute(
            """
            UPDATE billing_orders
            SET
                status = 'canceled',
                canceled_at = ?,
                updated_at = ?
            WHERE order_id = ?
            """,
            (
                current_time,
                current_time,
                order_id,
            ),
        )

        connection.commit()

    return get_order(
        order_id
    )


def list_user_orders(
    user_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM billing_orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (
                str(user_id),
                safe_limit,
            ),
        ).fetchall()

    orders = []

    for row in rows:
        order = row_to_dict(row)

        order["formatted_total"] = (
            format_idr(
                order["total"]
            )
        )

        orders.append(order)

    return orders


def list_all_orders(
    limit: int = 200,
    status: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 1000),
    )

    with connect() as connection:
        if status:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_orders
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
                FROM billing_orders
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

    results = []

    for row in rows:
        order = row_to_dict(row)

        order["formatted_total"] = format_idr(
            order["total"]
        )

        results.append(order)

    return results


def wallet_summary(
    user_id: str,
) -> dict[str, Any]:
    with connect() as connection:
        balance = ensure_wallet(
            user_id,
            connection,
        )

        rows = connection.execute(
            """
            SELECT *
            FROM billing_credit_ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (str(user_id),),
        ).fetchall()

        connection.commit()

    return {
        "user_id": str(user_id),
        "credit_balance": int(
            balance
        ),
        "ledger": [
            dict(row)
            for row in rows
        ],
    }


def list_entitlements(
    user_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with connect() as connection:
        if status:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_entitlements
                WHERE user_id = ?
                  AND status = ?
                ORDER BY created_at DESC
                """,
                (
                    str(user_id),
                    status,
                ),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM billing_entitlements
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (str(user_id),),
            ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def redeem_credits(
    user_id: str,
    product_code: str,
    quantity: int = 1,
) -> dict[str, Any]:
    safe_quantity = max(
        1,
        min(int(quantity), 100),
    )

    notification_message = None

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        product = get_product(
            product_code,
            connection=connection,
        )

        if not product:
            raise ValueError(
                "Produk tidak ditemukan."
            )

        if product["product_type"] != "processing":
            raise ValueError(
                "Kredit hanya dapat digunakan untuk layanan pemrosesan."
            )

        credit_cost = (
            int(product["credit_cost"])
            * safe_quantity
        )

        if credit_cost <= 0:
            raise ValueError(
                "Produk ini tidak mendukung pembayaran kredit."
            )

        reference_id = uuid4().hex

        new_balance = record_credit_change(
            connection=connection,
            user_id=str(user_id),
            amount=-credit_cost,
            entry_type="redemption",
            reference_type="credit_redemption",
            reference_id=reference_id,
            description=(
                f"Penukaran kredit untuk "
                f"{product['name']}"
            ),
        )

        entitlement_ids = []

        for _ in range(safe_quantity):
            entitlement_id = uuid4().hex

            connection.execute(
                """
                INSERT INTO billing_entitlements (
                    entitlement_id,
                    order_id,
                    order_item_id,
                    user_id,
                    service_code,
                    status,
                    source_type,
                    source_reference,
                    expires_at,
                    consumed_at,
                    consumed_reference,
                    refunded_at,
                    created_at
                )
                VALUES (
                    ?, NULL, NULL, ?, ?,
                    'available', 'credit_redemption',
                    ?, NULL, NULL, NULL, NULL, ?
                )
                """,
                (
                    entitlement_id,
                    str(user_id),
                    product["service_code"],
                    reference_id,
                    utc_now_text(),
                ),
            )

            entitlement_ids.append(
                entitlement_id
            )

        connection.commit()

        notification_message = (
            f"{credit_cost} kredit digunakan "
            f"untuk {safe_quantity} layanan "
            f"{product['name']}."
        )

    notify_user(
        user_id=str(user_id),
        title="Kredit berhasil digunakan",
        message=notification_message,
        notification_type="success",
        action_url="/billing",
    )

    return {
        "success": True,
        "product": product,
        "quantity": safe_quantity,
        "credits_used": credit_cost,
        "credit_balance": new_balance,
        "entitlement_ids": entitlement_ids,
    }


def consume_entitlement(
    user_id: str,
    service_code: str,
    consumed_reference: str,
) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        row = connection.execute(
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
                utc_now_text(),
            ),
        ).fetchone()

        if not row:
            raise ValueError(
                (
                    "Hak pemrosesan tidak tersedia. "
                    "Silakan melakukan pembayaran terlebih dahulu."
                )
            )

        entitlement = dict(row)

        current_time = utc_now_text()

        connection.execute(
            """
            UPDATE billing_entitlements
            SET
                status = 'consumed',
                consumed_at = ?,
                consumed_reference = ?
            WHERE entitlement_id = ?
            """,
            (
                current_time,
                consumed_reference,
                entitlement["entitlement_id"],
            ),
        )

        connection.commit()

        entitlement["status"] = "consumed"
        entitlement["consumed_at"] = (
            current_time
        )

        entitlement[
            "consumed_reference"
        ] = consumed_reference

        return entitlement


def has_processing_access(
    user_id: str,
    service_code: str,
) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM billing_entitlements
            WHERE user_id = ?
              AND service_code = ?
              AND status = 'available'
              AND (
                    expires_at IS NULL
                    OR expires_at > ?
              )
            LIMIT 1
            """,
            (
                str(user_id),
                service_code,
                utc_now_text(),
            ),
        ).fetchone()

    return row is not None


def update_product(
    product_code: str,
    name: str,
    description: str,
    price_idr: int,
    credit_cost: int,
    active: bool,
) -> dict[str, Any]:
    safe_price = max(
        0,
        int(price_idr),
    )

    safe_credit_cost = max(
        0,
        int(credit_cost),
    )

    with connect() as connection:
        existing = get_product(
            product_code,
            active_only=False,
            connection=connection,
        )

        if not existing:
            raise ValueError(
                "Produk tidak ditemukan."
            )

        connection.execute(
            """
            UPDATE billing_products
            SET
                name = ?,
                description = ?,
                price_idr = ?,
                credit_cost = ?,
                active = ?,
                updated_at = ?
            WHERE product_code = ?
            """,
            (
                name.strip(),
                description.strip(),
                safe_price,
                safe_credit_cost,
                1 if active else 0,
                utc_now_text(),
                product_code,
            ),
        )

        connection.commit()

    return get_product(
        product_code,
        active_only=False,
    )


def refund_order(
    order_id: str,
) -> dict[str, Any]:
    notification_payload = None

    with connect() as connection:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        order = get_order(
            order_id,
            connection,
        )

        if not order:
            raise ValueError(
                "Pesanan tidak ditemukan."
            )

        if order["status"] == "refunded":
            connection.commit()
            return order

        if order["status"] != "paid":
            raise ValueError(
                "Hanya pesanan paid yang dapat direfund."
            )

        processing_items = [
            item
            for item in order["items"]
            if item["product_type"]
            == "processing"
        ]

        credit_items = [
            item
            for item in order["items"]
            if item["product_type"]
            == "credit_pack"
        ]

        if processing_items:
            consumed_count = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM billing_entitlements
                WHERE order_id = ?
                  AND status = 'consumed'
                """,
                (order_id,),
            ).fetchone()["total"]

            if int(consumed_count) > 0:
                raise ValueError(
                    (
                        "Refund ditolak karena sebagian "
                        "hak pemrosesan sudah digunakan."
                    )
                )

            connection.execute(
                """
                UPDATE billing_entitlements
                SET
                    status = 'refunded',
                    refunded_at = ?
                WHERE order_id = ?
                  AND status = 'available'
                """,
                (
                    utc_now_text(),
                    order_id,
                ),
            )

        if credit_items:
            purchased_credits = sum(
                int(item["credit_amount"])
                * int(item["quantity"])
                for item in credit_items
            )

            balance = ensure_wallet(
                order["user_id"],
                connection,
            )

            if balance < purchased_credits:
                raise ValueError(
                    (
                        "Refund ditolak karena kredit "
                        "dari pesanan sudah digunakan."
                    )
                )

            record_credit_change(
                connection=connection,
                user_id=order["user_id"],
                amount=-purchased_credits,
                entry_type="refund",
                reference_type="order",
                reference_id=order_id,
                description=(
                    f"Refund pesanan "
                    f"{order['order_number']}"
                ),
            )

        current_time = utc_now_text()

        connection.execute(
            """
            UPDATE billing_orders
            SET
                status = 'refunded',
                refunded_at = ?,
                updated_at = ?
            WHERE order_id = ?
            """,
            (
                current_time,
                current_time,
                order_id,
            ),
        )

        connection.execute(
            """
            UPDATE billing_payments
            SET
                status = 'refunded',
                updated_at = ?
            WHERE order_id = ?
            """,
            (
                current_time,
                order_id,
            ),
        )

        connection.commit()

        notification_payload = {
            "user_id": order["user_id"],
            "order_number": order["order_number"],
        }

    notify_user(
        user_id=notification_payload[
            "user_id"
        ],
        title="Pesanan direfund",
        message=(
            f"Pesanan "
            f"{notification_payload['order_number']} "
            "telah direfund."
        ),
        notification_type="warning",
        action_url="/billing",
    )

    return get_order(
        order_id
    )


def process_webhook(
    event_id: str,
    order_id: str,
    event_type: str,
    signature: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    secret = os.getenv(
        "DOCURAPI_PAYMENT_WEBHOOK_SECRET",
        "local-development-secret",
    )

    signing_value = (
        f"{event_id}:{order_id}:{event_type}"
    )

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        signing_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        signature,
    ):
        raise PermissionError(
            "Signature webhook tidak valid."
        )

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT *
            FROM billing_webhook_events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()

        if existing:
            result = dict(existing)
            result["idempotent"] = True
            return result

        connection.execute(
            """
            INSERT INTO billing_webhook_events (
                event_id,
                provider,
                event_type,
                order_id,
                payload_json,
                processing_status,
                error_message,
                created_at,
                processed_at
            )
            VALUES (
                ?, 'simulated_webhook', ?, ?, ?,
                'processing', NULL, ?, NULL
            )
            """,
            (
                event_id,
                event_type,
                order_id,
                json.dumps(
                    payload or {},
                    ensure_ascii=False,
                ),
                utc_now_text(),
            ),
        )

        connection.commit()

    try:
        if event_type == "payment.paid":
            completed_order = complete_order_payment(
                order_id=order_id,
                provider="simulated_webhook",
                transaction_id=(
                    "WEBHOOK-"
                    + event_id
                ),
                payload=payload,
            )
        else:
            completed_order = get_order(
                order_id
            )

        with connect() as connection:
            connection.execute(
                """
                UPDATE billing_webhook_events
                SET
                    processing_status = 'processed',
                    processed_at = ?
                WHERE event_id = ?
                """,
                (
                    utc_now_text(),
                    event_id,
                ),
            )

            connection.commit()

        return {
            "event_id": event_id,
            "status": "processed",
            "order": completed_order,
            "idempotent": False,
        }

    except Exception as exc:
        with connect() as connection:
            connection.execute(
                """
                UPDATE billing_webhook_events
                SET
                    processing_status = 'failed',
                    error_message = ?,
                    processed_at = ?
                WHERE event_id = ?
                """,
                (
                    str(exc),
                    utc_now_text(),
                    event_id,
                ),
            )

            connection.commit()

        raise


def billing_health() -> dict[str, Any]:
    initialize_billing_database()

    with connect() as connection:
        quick_check = connection.execute(
            "PRAGMA quick_check"
        ).fetchone()

        product_count = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM billing_products
            """
        ).fetchone()["total"]

    return {
        "status": (
            "ok"
            if quick_check
            and quick_check[0] == "ok"
            else "degraded"
        ),
        "payment_mode": payment_mode(),
        "currency": "IDR",
        "database": str(
            BILLING_DATABASE_PATH
        ),
        "products": int(
            product_count
        ),
        "pay_per_use": True,
        "subscription_enabled": False,
    }


def run_billing_self_test() -> dict[str, Any]:
    test_user_id = (
        "__billing_self_test__"
        + uuid4().hex
    )

    order_id = None

    try:
        order = create_order(
            user_id=test_user_id,
            user_email=(
                "billing-self-test@local.invalid"
            ),
            product_code="format_simple",
            quantity=1,
            idempotency_key=uuid4().hex,
            metadata={
                "self_test": True
            },
        )

        order_id = order["order_id"]

        paid_order = complete_order_payment(
            order_id=order_id,
            provider="self_test",
            transaction_id=(
                "SELFTEST-"
                + uuid4().hex
            ),
            payload={
                "self_test": True
            },
        )

        access_available = (
            has_processing_access(
                test_user_id,
                "format_simple",
            )
        )

        consumed = consume_entitlement(
            user_id=test_user_id,
            service_code="format_simple",
            consumed_reference=(
                "self-test-document"
            ),
        )

        if paid_order["status"] != "paid":
            raise RuntimeError(
                "Order self-test tidak berstatus paid."
            )

        if not access_available:
            raise RuntimeError(
                "Entitlement self-test tidak tersedia."
            )

        if consumed["status"] != "consumed":
            raise RuntimeError(
                "Entitlement self-test tidak dapat dikonsumsi."
            )

        return {
            "status": "passed",
            "order_status": (
                paid_order["status"]
            ),
            "entitlement_status": (
                consumed["status"]
            ),
        }

    finally:
        with connect() as connection:
            connection.execute(
                """
                DELETE FROM billing_credit_ledger
                WHERE user_id = ?
                """,
                (test_user_id,),
            )

            connection.execute(
                """
                DELETE FROM billing_wallets
                WHERE user_id = ?
                """,
                (test_user_id,),
            )

            connection.execute(
                """
                DELETE FROM billing_entitlements
                WHERE user_id = ?
                """,
                (test_user_id,),
            )

            if order_id:
                connection.execute(
                    """
                    DELETE FROM billing_orders
                    WHERE order_id = ?
                    """,
                    (order_id,),
                )

            connection.commit()
