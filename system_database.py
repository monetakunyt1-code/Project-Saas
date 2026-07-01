from __future__ import annotations

from services import database_adapter as sqlite3
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from config import STORAGE_DIR


SYSTEM_DIRECTORY = (
    STORAGE_DIR
    / "system"
)

OBSERVABILITY_DATABASE_PATH = (
    SYSTEM_DIRECTORY
    / "observability.db"
)

SYSTEM_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        OBSERVABILITY_DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def initialize_system_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS request_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                user_id TEXT,
                workspace_id TEXT,
                client_ip TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS error_events (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                traceback_text TEXT,
                method TEXT,
                path TEXT,
                user_id TEXT,
                workspace_id TEXT,
                client_ip TEXT,
                resolved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS system_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_request_metrics_created
            ON request_metrics(created_at);

            CREATE INDEX IF NOT EXISTS
                idx_request_metrics_path
            ON request_metrics(path);

            CREATE INDEX IF NOT EXISTS
                idx_error_events_created
            ON error_events(created_at);

            CREATE INDEX IF NOT EXISTS
                idx_system_events_created
            ON system_events(created_at);
            """
        )

        connection.commit()


def record_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str | None = None,
    workspace_id: str | None = None,
    client_ip: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO request_metrics (
                method,
                path,
                status_code,
                duration_ms,
                user_id,
                workspace_id,
                client_ip,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                method[:20],
                path[:500],
                int(status_code),
                float(duration_ms),
                user_id,
                workspace_id,
                client_ip,
                utc_now(),
            ),
        )

        connection.commit()


def record_error(
    error_type: str,
    message: str,
    traceback_text: str = "",
    method: str = "",
    path: str = "",
    user_id: str | None = None,
    workspace_id: str | None = None,
    client_ip: str | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO error_events (
                error_type,
                message,
                traceback_text,
                method,
                path,
                user_id,
                workspace_id,
                client_ip,
                resolved,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                error_type[:200],
                message[:4000],
                traceback_text[:30000],
                method[:20],
                path[:500],
                user_id,
                workspace_id,
                client_ip,
                utc_now(),
            ),
        )

        connection.commit()


def record_system_event(
    level: str,
    category: str,
    message: str,
    metadata_json: str = "{}",
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO system_events (
                level,
                category,
                message,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                level[:30],
                category[:100],
                message[:4000],
                metadata_json[:20000],
                utc_now(),
            ),
        )

        connection.commit()


def request_summary(
    hours: int = 24,
) -> dict[str, Any]:
    safe_hours = max(
        1,
        min(int(hours), 24 * 90),
    )

    threshold = (
        datetime.now(timezone.utc)
        - timedelta(hours=safe_hours)
    ).isoformat()

    with connect() as connection:
        aggregate = connection.execute(
            """
            SELECT
                COUNT(*) AS request_count,
                COALESCE(
                    AVG(duration_ms),
                    0
                ) AS average_duration_ms,
                COALESCE(
                    MAX(duration_ms),
                    0
                ) AS maximum_duration_ms,
                SUM(
                    CASE
                        WHEN status_code >= 500
                        THEN 1
                        ELSE 0
                    END
                ) AS server_error_count,
                SUM(
                    CASE
                        WHEN status_code >= 400
                         AND status_code < 500
                        THEN 1
                        ELSE 0
                    END
                ) AS client_error_count
            FROM request_metrics
            WHERE created_at >= ?
            """,
            (threshold,),
        ).fetchone()

        paths = connection.execute(
            """
            SELECT
                method,
                path,
                COUNT(*) AS request_count,
                ROUND(
                    AVG(duration_ms),
                    2
                ) AS average_duration_ms,
                MAX(duration_ms)
                    AS maximum_duration_ms
            FROM request_metrics
            WHERE created_at >= ?
            GROUP BY method, path
            ORDER BY request_count DESC
            LIMIT 20
            """,
            (threshold,),
        ).fetchall()

    result = dict(aggregate)

    for key, value in list(
        result.items()
    ):
        if value is None:
            result[key] = 0

    result["hours"] = safe_hours

    result["top_paths"] = [
        dict(row)
        for row in paths
    ]

    return result


def list_errors(
    limit: int = 100,
    unresolved_only: bool = False,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 1000),
    )

    with connect() as connection:
        if unresolved_only:
            rows = connection.execute(
                """
                SELECT *
                FROM error_events
                WHERE resolved = 0
                ORDER BY error_id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT *
                FROM error_events
                ORDER BY error_id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def resolve_error(
    error_id: int,
) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE error_events
            SET resolved = 1
            WHERE error_id = ?
            """,
            (int(error_id),),
        )

        connection.commit()

    return cursor.rowcount > 0


def list_system_events(
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 1000),
    )

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM system_events
            ORDER BY event_id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def cleanup_observability(
    retention_days: int = 90,
) -> dict[str, int]:
    safe_days = max(
        7,
        min(int(retention_days), 3650),
    )

    threshold = (
        datetime.now(timezone.utc)
        - timedelta(days=safe_days)
    ).isoformat()

    with connect() as connection:
        requests_cursor = connection.execute(
            """
            DELETE FROM request_metrics
            WHERE created_at < ?
            """,
            (threshold,),
        )

        errors_cursor = connection.execute(
            """
            DELETE FROM error_events
            WHERE created_at < ?
              AND resolved = 1
            """,
            (threshold,),
        )

        events_cursor = connection.execute(
            """
            DELETE FROM system_events
            WHERE created_at < ?
            """,
            (threshold,),
        )

        connection.commit()

    return {
        "requests_removed": (
            requests_cursor.rowcount
        ),
        "errors_removed": (
            errors_cursor.rowcount
        ),
        "events_removed": (
            events_cursor.rowcount
        ),
    }


initialize_system_database()