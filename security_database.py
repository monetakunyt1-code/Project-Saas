from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import STORAGE_DIR


SECURITY_DIRECTORY = STORAGE_DIR / "saas"
SECURITY_DATABASE_PATH = (
    SECURITY_DIRECTORY
    / "security.db"
)

SECURITY_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        SECURITY_DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def initialize_security_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                bucket_key TEXT PRIMARY KEY,
                request_count INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                email TEXT,
                ip_address TEXT,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                user_agent TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS privacy_settings (
                user_id TEXT PRIMARY KEY,
                retention_days INTEGER NOT NULL DEFAULT 30,
                analytics_enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_audit_created_at
            ON audit_events(created_at);

            CREATE INDEX IF NOT EXISTS
                idx_audit_user_id
            ON audit_events(user_id);

            CREATE INDEX IF NOT EXISTS
                idx_reset_user_id
            ON password_reset_tokens(user_id);
            """
        )

        connection.commit()


def hit_rate_limit(
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> dict[str, Any]:
    now_timestamp = int(
        time.time()
    )

    bucket_number = (
        now_timestamp
        // window_seconds
    )

    bucket_key = (
        f"{scope}:"
        f"{identity}:"
        f"{bucket_number}"
    )

    expires_at = (
        (bucket_number + 1)
        * window_seconds
    )

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO rate_limits (
                bucket_key,
                request_count,
                expires_at,
                updated_at
            )
            VALUES (?, 1, ?, ?)
            ON CONFLICT(bucket_key)
            DO UPDATE SET
                request_count =
                    request_count + 1,
                updated_at =
                    excluded.updated_at
            """,
            (
                bucket_key,
                expires_at,
                utc_now(),
            ),
        )

        row = connection.execute(
            """
            SELECT request_count
            FROM rate_limits
            WHERE bucket_key = ?
            """,
            (bucket_key,),
        ).fetchone()

        connection.execute(
            """
            DELETE FROM rate_limits
            WHERE expires_at < ?
            """,
            (
                now_timestamp
                - window_seconds,
            ),
        )

        connection.commit()

    count = int(
        row["request_count"]
    )

    return {
        "allowed": count <= limit,
        "limit": limit,
        "count": count,
        "remaining": max(
            limit - count,
            0,
        ),
        "retry_after": max(
            expires_at - now_timestamp,
            1,
        ),
    }


def add_audit_event(
    user_id: str | None,
    email: str | None,
    ip_address: str,
    method: str,
    path: str,
    status_code: int,
    user_agent: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
                user_id,
                email,
                ip_address,
                method,
                path,
                status_code,
                user_agent,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                email,
                ip_address,
                method,
                path,
                int(status_code),
                user_agent[:500],
                utc_now(),
            ),
        )

        connection.commit()


def list_audit_events(
    limit: int = 200,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 1000),
    )

    with connect() as connection:
        if user_id:
            rows = connection.execute(
                """
                SELECT *
                FROM audit_events
                WHERE user_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (
                    user_id,
                    safe_limit,
                ),
            ).fetchall()

        else:
            rows = connection.execute(
                """
                SELECT *
                FROM audit_events
                ORDER BY event_id DESC
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


def store_reset_token(
    token_hash: str,
    user_id: str,
    expires_at: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE user_id = ?
              AND used_at IS NULL
            """,
            (
                user_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO password_reset_tokens (
                token_hash,
                user_id,
                expires_at,
                used_at,
                created_at
            )
            VALUES (?, ?, ?, NULL, ?)
            """,
            (
                token_hash,
                user_id,
                expires_at,
                utc_now(),
            ),
        )

        connection.commit()


def consume_reset_token(
    token_hash: str,
) -> str | None:
    now = datetime.now(
        timezone.utc
    )

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM password_reset_tokens
            WHERE token_hash = ?
              AND used_at IS NULL
            """,
            (
                token_hash,
            ),
        ).fetchone()

        if not row:
            return None

        try:
            expires_at = datetime.fromisoformat(
                row["expires_at"]
            )
        except ValueError:
            return None

        if expires_at <= now:
            return None

        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE token_hash = ?
            """,
            (
                utc_now(),
                token_hash,
            ),
        )

        connection.commit()

    return str(
        row["user_id"]
    )


def get_privacy_settings(
    user_id: str,
) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM privacy_settings
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

    if not row:
        return {
            "user_id": user_id,
            "retention_days": 30,
            "analytics_enabled": False,
        }

    result = dict(row)

    result["analytics_enabled"] = bool(
        result["analytics_enabled"]
    )

    return result


def save_privacy_settings(
    user_id: str,
    retention_days: int,
    analytics_enabled: bool,
) -> dict[str, Any]:
    safe_retention = max(
        1,
        min(int(retention_days), 365),
    )

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO privacy_settings (
                user_id,
                retention_days,
                analytics_enabled,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                retention_days =
                    excluded.retention_days,
                analytics_enabled =
                    excluded.analytics_enabled,
                updated_at =
                    excluded.updated_at
            """,
            (
                user_id,
                safe_retention,
                1 if analytics_enabled else 0,
                utc_now(),
            ),
        )

        connection.commit()

    return get_privacy_settings(
        user_id
    )


def remove_user_security_data(
    user_id: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        connection.execute(
            """
            DELETE FROM privacy_settings
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        connection.execute(
            """
            UPDATE audit_events
            SET
                user_id = NULL,
                email = NULL
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        connection.commit()


initialize_security_database()