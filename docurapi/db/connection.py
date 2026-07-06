from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from docurapi.core.settings import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not column_exists(connection, table_name, column_name):
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def initialize_database() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                original_name TEXT NOT NULL,
                mode TEXT NOT NULL,
                preset TEXT NOT NULL,
                status TEXT NOT NULL,
                input_size INTEGER DEFAULT 0,
                output_name TEXT,
                output_path TEXT,
                report_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        add_column_if_missing(connection, "jobs", "payment_status", "TEXT NOT NULL DEFAULT 'unpaid'")
        add_column_if_missing(connection, "jobs", "payment_reference", "TEXT")
        add_column_if_missing(connection, "jobs", "amount", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(connection, "jobs", "paid_at", "TEXT")
        add_column_if_missing(connection, "jobs", "access_token", "TEXT")
        add_column_if_missing(connection, "jobs", "rejected_at", "TEXT")
        add_column_if_missing(connection, "jobs", "rejection_reason", "TEXT")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                template_id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                institution_name TEXT,
                document_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                external_reference TEXT,
                checkout_url TEXT,
                raw_payload TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                paid_at TEXT,
                rejected_at TEXT,
                rejection_reason TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
            )
            """
        )

        add_column_if_missing(connection, "payments", "rejected_at", "TEXT")
        add_column_if_missing(connection, "payments", "rejection_reason", "TEXT")

        connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_payment_status ON jobs(payment_status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_templates_created_at ON templates(created_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_payments_job_id ON payments(job_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_payments_external_reference ON payments(external_reference)")

        connection.commit()
