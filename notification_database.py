from __future__ import annotations

import json
from services import database_adapter as sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import STORAGE_DIR


NOTIFICATION_DIRECTORY = (
    STORAGE_DIR
    / "notifications"
)

NOTIFICATION_DATABASE_PATH = (
    NOTIFICATION_DIRECTORY
    / "notifications.db"
)

NOTIFICATION_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        NOTIFICATION_DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_notification_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                workspace_id TEXT,
                notification_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                action_url TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                read_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_outbox (
                email_id TEXT PRIMARY KEY,
                user_id TEXT,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body_text TEXT NOT NULL,
                body_html TEXT,
                template_key TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                local_file_path TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT
            );

            CREATE TABLE IF NOT EXISTS email_tokens (
                token_id TEXT PRIMARY KEY,
                user_id TEXT,
                email TEXT NOT NULL,
                purpose TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verified_emails (
                email TEXT PRIMARY KEY,
                user_id TEXT,
                verified_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_notifications_user
            ON notifications(user_id, created_at);

            CREATE INDEX IF NOT EXISTS
                idx_notifications_unread
            ON notifications(user_id, read_at);

            CREATE INDEX IF NOT EXISTS
                idx_email_outbox_status
            ON email_outbox(status, created_at);

            CREATE INDEX IF NOT EXISTS
                idx_email_tokens_lookup
            ON email_tokens(
                token_hash,
                purpose,
                consumed_at
            );
            """
        )

        connection.commit()


def create_notification_record(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: str | None = None,
    workspace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    notification_id = uuid4().hex

    created_at = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO notifications (
                notification_id,
                user_id,
                workspace_id,
                notification_type,
                title,
                message,
                action_url,
                metadata_json,
                read_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                notification_id,
                str(user_id),
                workspace_id,
                notification_type[:50],
                title[:300],
                message[:4000],
                action_url,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
                created_at,
            ),
        )

        connection.commit()

    return get_notification(
        notification_id
    )


def get_notification(
    notification_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM notifications
            WHERE notification_id = ?
            """,
            (notification_id,),
        ).fetchone()

    if not row:
        return None

    result = dict(row)

    try:
        result["metadata"] = json.loads(
            result.pop(
                "metadata_json",
                "{}",
            )
        )
    except json.JSONDecodeError:
        result["metadata"] = {}

    return result


def list_notifications(
    user_id: str,
    limit: int = 100,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    with connect() as connection:
        if unread_only:
            rows = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE user_id = ?
                  AND read_at IS NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    str(user_id),
                    safe_limit,
                ),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    str(user_id),
                    safe_limit,
                ),
            ).fetchall()

    results = []

    for row in rows:
        item = dict(row)

        try:
            item["metadata"] = json.loads(
                item.pop(
                    "metadata_json",
                    "{}",
                )
            )
        except json.JSONDecodeError:
            item["metadata"] = {}

        results.append(item)

    return results


def unread_notification_count(
    user_id: str,
) -> int:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM notifications
            WHERE user_id = ?
              AND read_at IS NULL
            """,
            (str(user_id),),
        ).fetchone()

    return int(
        row["total"]
        if row
        else 0
    )


def mark_notification_read(
    notification_id: str,
    user_id: str,
) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET read_at = COALESCE(
                read_at,
                ?
            )
            WHERE notification_id = ?
              AND user_id = ?
            """,
            (
                utc_now(),
                notification_id,
                str(user_id),
            ),
        )

        connection.commit()

    return cursor.rowcount > 0


def mark_all_notifications_read(
    user_id: str,
) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET read_at = ?
            WHERE user_id = ?
              AND read_at IS NULL
            """,
            (
                utc_now(),
                str(user_id),
            ),
        )

        connection.commit()

    return cursor.rowcount


def delete_notification_record(
    notification_id: str,
    user_id: str,
) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM notifications
            WHERE notification_id = ?
              AND user_id = ?
            """,
            (
                notification_id,
                str(user_id),
            ),
        )

        connection.commit()

    return cursor.rowcount > 0


def enqueue_email_record(
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    template_key: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    email_id = uuid4().hex

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO email_outbox (
                email_id,
                user_id,
                recipient,
                subject,
                body_text,
                body_html,
                template_key,
                status,
                attempts,
                last_error,
                local_file_path,
                created_at,
                sent_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                'queued', 0, NULL, NULL, ?, NULL
            )
            """,
            (
                email_id,
                user_id,
                recipient.strip().lower(),
                subject[:500],
                body_text,
                body_html,
                template_key,
                utc_now(),
            ),
        )

        connection.commit()

    return get_email_record(
        email_id
    )


def get_email_record(
    email_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM email_outbox
            WHERE email_id = ?
            """,
            (email_id,),
        ).fetchone()

    return dict(row) if row else None


def list_email_outbox(
    limit: int = 100,
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
                FROM email_outbox
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
                FROM email_outbox
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def list_pending_email_records(
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM email_outbox
            WHERE status IN (
                'queued',
                'failed'
            )
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def mark_email_sent(
    email_id: str,
    local_file_path: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE email_outbox
            SET
                status = 'sent',
                attempts = attempts + 1,
                last_error = NULL,
                local_file_path = ?,
                sent_at = ?
            WHERE email_id = ?
            """,
            (
                local_file_path,
                utc_now(),
                email_id,
            ),
        )

        connection.commit()


def mark_email_failed(
    email_id: str,
    error_message: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE email_outbox
            SET
                status = 'failed',
                attempts = attempts + 1,
                last_error = ?
            WHERE email_id = ?
            """,
            (
                error_message[:4000],
                email_id,
            ),
        )

        connection.commit()


def create_token_record(
    user_id: str | None,
    email: str,
    purpose: str,
    token_hash: str,
    expires_at: str,
) -> dict[str, Any]:
    token_id = uuid4().hex

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO email_tokens (
                token_id,
                user_id,
                email,
                purpose,
                token_hash,
                expires_at,
                consumed_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                token_id,
                user_id,
                email.strip().lower(),
                purpose,
                token_hash,
                expires_at,
                utc_now(),
            ),
        )

        connection.commit()

    return {
        "token_id": token_id,
        "user_id": user_id,
        "email": email.strip().lower(),
        "purpose": purpose,
        "expires_at": expires_at,
    }


def get_active_token_by_hash(
    token_hash: str,
    purpose: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM email_tokens
            WHERE token_hash = ?
              AND purpose = ?
              AND consumed_at IS NULL
            LIMIT 1
            """,
            (
                token_hash,
                purpose,
            ),
        ).fetchone()

    return dict(row) if row else None


def consume_token_record(
    token_id: str,
) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE email_tokens
            SET consumed_at = ?
            WHERE token_id = ?
              AND consumed_at IS NULL
            """,
            (
                utc_now(),
                token_id,
            ),
        )

        connection.commit()

    return cursor.rowcount > 0


def record_verified_email(
    email: str,
    user_id: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO verified_emails (
                email,
                user_id,
                verified_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(email)
            DO UPDATE SET
                user_id = excluded.user_id,
                verified_at = excluded.verified_at
            """,
            (
                email.strip().lower(),
                user_id,
                utc_now(),
            ),
        )

        connection.commit()


def email_is_verified(
    email: str,
) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM verified_emails
            WHERE email = ?
            LIMIT 1
            """,
            (
                email.strip().lower(),
            ),
        ).fetchone()

    return row is not None


initialize_notification_database()
