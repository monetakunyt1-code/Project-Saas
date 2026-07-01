from __future__ import annotations

import json
from services import database_adapter as sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    __file__
).resolve().parent

BILLING_DIRECTORY = (
    BASE_DIR
    / "storage"
    / "billing"
)

BILLING_DATABASE_PATH = (
    BILLING_DIRECTORY
    / "billing.db"
)

BILLING_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


DEFAULT_PRODUCTS = [
    {
        "product_code": "format_simple",
        "name": "Format Dokumen Sederhana",
        "description": (
            "Pemformatan dasar font, margin, "
            "spasi, paragraf, dan heading."
        ),
        "product_type": "processing",
        "service_code": "format_simple",
        "price_idr": 5000,
        "credit_cost": 1,
        "credit_amount": 0,
        "sort_order": 10,
    },
    {
        "product_code": "format_academic",
        "name": "Format Skripsi Lengkap",
        "description": (
            "Pemformatan lengkap dokumen akademik "
            "beserta daftar isi dan penomoran."
        ),
        "product_type": "processing",
        "service_code": "format_academic",
        "price_idr": 10000,
        "credit_cost": 2,
        "credit_amount": 0,
        "sort_order": 20,
    },
    {
        "product_code": "academic_audit",
        "name": "Academic Audit",
        "description": (
            "Pemeriksaan struktur, format, "
            "sitasi, dan konsistensi akademik."
        ),
        "product_type": "processing",
        "service_code": "academic_audit",
        "price_idr": 7500,
        "credit_cost": 2,
        "credit_amount": 0,
        "sort_order": 30,
    },
    {
        "product_code": "journal_conversion",
        "name": "Konversi ke Jurnal",
        "description": (
            "Konversi dokumen akademik menjadi "
            "format artikel jurnal."
        ),
        "product_type": "processing",
        "service_code": "journal_conversion",
        "price_idr": 12500,
        "credit_cost": 3,
        "credit_amount": 0,
        "sort_order": 40,
    },
    {
        "product_code": "template_format",
        "name": "Format Berdasarkan Template",
        "description": (
            "Pemformatan dokumen mengikuti "
            "template Word yang diberikan."
        ),
        "product_type": "processing",
        "service_code": "template_format",
        "price_idr": 10000,
        "credit_cost": 2,
        "credit_amount": 0,
        "sort_order": 50,
    },
    {
        "product_code": "batch_processing",
        "name": "Batch Processing",
        "description": (
            "Pemrosesan beberapa dokumen dalam "
            "satu transaksi."
        ),
        "product_type": "processing",
        "service_code": "batch_processing",
        "price_idr": 8000,
        "credit_cost": 2,
        "credit_amount": 0,
        "sort_order": 60,
    },
    {
        "product_code": "credit_pack_10",
        "name": "Paket 10 Kredit",
        "description": (
            "Pembelian sekali bayar untuk "
            "10 kredit pemrosesan."
        ),
        "product_type": "credit_pack",
        "service_code": None,
        "price_idr": 45000,
        "credit_cost": 0,
        "credit_amount": 10,
        "sort_order": 110,
    },
    {
        "product_code": "credit_pack_25",
        "name": "Paket 25 Kredit",
        "description": (
            "Pembelian sekali bayar untuk "
            "25 kredit pemrosesan."
        ),
        "product_type": "credit_pack",
        "service_code": None,
        "price_idr": 100000,
        "credit_cost": 0,
        "credit_amount": 25,
        "sort_order": 120,
    },
    {
        "product_code": "credit_pack_60",
        "name": "Paket 60 Kredit",
        "description": (
            "Pembelian sekali bayar untuk "
            "60 kredit pemrosesan."
        ),
        "product_type": "credit_pack",
        "service_code": None,
        "price_idr": 210000,
        "credit_cost": 0,
        "credit_amount": 60,
        "sort_order": 130,
    },
]


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        BILLING_DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def initialize_billing_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS billing_products (
                product_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                product_type TEXT NOT NULL,
                service_code TEXT,
                price_idr INTEGER NOT NULL,
                credit_cost INTEGER NOT NULL DEFAULT 0,
                credit_amount INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 100,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_orders (
                order_id TEXT PRIMARY KEY,
                order_number TEXT NOT NULL UNIQUE,
                invoice_number TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                user_email TEXT,
                status TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'IDR',
                subtotal INTEGER NOT NULL,
                discount INTEGER NOT NULL DEFAULT 0,
                tax INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL,
                payment_mode TEXT NOT NULL DEFAULT 'simulation',
                idempotency_key TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                expires_at TEXT,
                paid_at TEXT,
                canceled_at TEXT,
                refunded_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, idempotency_key)
            );

            CREATE TABLE IF NOT EXISTS billing_order_items (
                order_item_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_type TEXT NOT NULL,
                service_code TEXT,
                quantity INTEGER NOT NULL,
                unit_price INTEGER NOT NULL,
                line_total INTEGER NOT NULL,
                credit_cost INTEGER NOT NULL DEFAULT 0,
                credit_amount INTEGER NOT NULL DEFAULT 0,
                snapshot_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(order_id)
                    REFERENCES billing_orders(order_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS billing_payments (
                payment_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                transaction_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                provider_payload_json TEXT NOT NULL DEFAULT '{}',
                paid_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(order_id)
                    REFERENCES billing_orders(order_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS billing_entitlements (
                entitlement_id TEXT PRIMARY KEY,
                order_id TEXT,
                order_item_id TEXT,
                user_id TEXT NOT NULL,
                service_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                source_type TEXT NOT NULL,
                source_reference TEXT,
                expires_at TEXT,
                consumed_at TEXT,
                consumed_reference TEXT,
                refunded_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(order_id)
                    REFERENCES billing_orders(order_id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS billing_wallets (
                user_id TEXT PRIMARY KEY,
                credit_balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_credit_ledger (
                ledger_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                entry_type TEXT NOT NULL,
                reference_type TEXT,
                reference_id TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS billing_webhook_events (
                event_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                event_type TEXT NOT NULL,
                order_id TEXT,
                payload_json TEXT NOT NULL,
                processing_status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                processed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_orders_user
            ON billing_orders(
                user_id,
                created_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_orders_status
            ON billing_orders(
                status,
                created_at
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_entitlements_user
            ON billing_entitlements(
                user_id,
                service_code,
                status
            );

            CREATE INDEX IF NOT EXISTS
                idx_billing_credit_ledger_user
            ON billing_credit_ledger(
                user_id,
                created_at
            );
            """
        )

        current_time = utc_now()

        for product in DEFAULT_PRODUCTS:
            connection.execute(
                """
                INSERT OR IGNORE INTO billing_products (
                    product_code,
                    name,
                    description,
                    product_type,
                    service_code,
                    price_idr,
                    credit_cost,
                    credit_amount,
                    active,
                    sort_order,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    product["product_code"],
                    product["name"],
                    product["description"],
                    product["product_type"],
                    product["service_code"],
                    product["price_idr"],
                    product["credit_cost"],
                    product["credit_amount"],
                    product["sort_order"],
                    current_time,
                    current_time,
                ),
            )

        connection.commit()


def row_to_dict(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if not row:
        return None

    result = dict(row)

    for key in [
        "metadata_json",
        "snapshot_json",
        "provider_payload_json",
        "payload_json",
    ]:
        if key not in result:
            continue

        raw_value = result.pop(
            key,
            "{}",
        )

        target_key = key.replace(
            "_json",
            "",
        )

        try:
            result[target_key] = json.loads(
                raw_value or "{}"
            )
        except json.JSONDecodeError:
            result[target_key] = {}

    return result


initialize_billing_database()
