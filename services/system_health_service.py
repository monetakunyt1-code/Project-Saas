from __future__ import annotations

import json
import shutil
from services import database_adapter as sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import STORAGE_DIR
from services.backup_service import (
    BASE_DIR,
    discover_databases,
    list_backups,
    scheduler_status,
)
from system_database import (
    list_errors,
    request_summary,
)


STARTED_AT = datetime.now(
    timezone.utc
)


def database_health() -> list[
    dict[str, Any]
]:
    checks: list[
        dict[str, Any]
    ] = []

    for path in discover_databases():
        relative_path = path.relative_to(
            BASE_DIR
        ).as_posix()

        status = "ok"
        message = "ok"

        try:
            connection = sqlite3.connect(
                str(path),
                timeout=5,
            )

            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            connection.close()

            if (
                not result
                or result[0] != "ok"
            ):
                status = "error"
                message = (
                    str(result[0])
                    if result
                    else "quick_check kosong"
                )

        except sqlite3.Error as exc:
            status = "error"
            message = str(exc)

        checks.append(
            {
                "database": relative_path,
                "status": status,
                "message": message,
                "size_bytes": (
                    path.stat().st_size
                ),
            }
        )

    return checks


def background_job_snapshot() -> dict[
    str,
    Any
]:
    database_path = (
        STORAGE_DIR
        / "background"
        / "background_jobs.db"
    )

    default = {
        "available": False,
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "canceled": 0,
    }

    if not database_path.exists():
        return default

    try:
        connection = sqlite3.connect(
            str(database_path),
            timeout=5,
        )

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS total
            FROM background_jobs
            GROUP BY status
            """
        ).fetchall()

        connection.close()

        result = dict(default)
        result["available"] = True

        for row in rows:
            status = str(
                row["status"]
            )

            if status == "canceling":
                status = "running"

            result[status] = (
                result.get(status, 0)
                + int(row["total"])
            )

        return result

    except sqlite3.Error as exc:
        return {
            **default,
            "error": str(exc),
        }


def application_version() -> dict[
    str,
    Any
]:
    manifest_path = (
        BASE_DIR
        / "FEATURE_MANIFEST.json"
    )

    if not manifest_path.exists():
        return {
            "version": "unknown",
            "package": "unknown",
        }

    try:
        payload = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        return {
            "version": payload.get(
                "version",
                "unknown",
            ),
            "package": payload.get(
                "package",
                "unknown",
            ),
        }

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {
            "version": "unknown",
            "package": "unknown",
        }


def build_health_snapshot(
    include_sensitive_paths: bool = False,
) -> dict[str, Any]:
    total_disk, used_disk, free_disk = (
        shutil.disk_usage(
            BASE_DIR
        )
    )

    databases = database_health()
    backups = list_backups()
    errors = list_errors(
        limit=25,
        unresolved_only=True,
    )

    request_metrics = request_summary(
        hours=24
    )

    database_errors = [
        item
        for item in databases
        if item["status"] != "ok"
    ]

    free_percent = (
        free_disk
        / max(total_disk, 1)
        * 100
    )

    status = "healthy"

    if database_errors:
        status = "degraded"

    if free_percent < 5:
        status = "critical"
    elif (
        free_percent < 10
        and status == "healthy"
    ):
        status = "degraded"

    if (
        request_metrics[
            "server_error_count"
        ]
        >= 10
        and status == "healthy"
    ):
        status = "degraded"

    latest_backup = (
        backups[0]
        if backups
        else None
    )

    if (
        latest_backup
        and not include_sensitive_paths
    ):
        latest_backup = {
            key: value
            for key, value in (
                latest_backup.items()
            )
            if key not in {
                "folder_path",
                "archive_path",
            }
        }

    if not include_sensitive_paths:
        for database in databases:
            database["database"] = (
                Path(
                    database["database"]
                ).name
            )

    uptime_seconds = int(
        (
            datetime.now(timezone.utc)
            - STARTED_AT
        ).total_seconds()
    )

    return {
        "status": status,
        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "application": (
            application_version()
        ),
        "uptime_seconds": (
            uptime_seconds
        ),
        "threads": threading.active_count(),
        "disk": {
            "total_bytes": total_disk,
            "used_bytes": used_disk,
            "free_bytes": free_disk,
            "free_percent": round(
                free_percent,
                2,
            ),
        },
        "databases": databases,
        "database_count": len(
            databases
        ),
        "database_errors": len(
            database_errors
        ),
        "requests_24h": (
            request_metrics
        ),
        "unresolved_errors": len(
            errors
        ),
        "recent_unresolved_errors": (
            errors
        ),
        "background_jobs": (
            background_job_snapshot()
        ),
        "backups": {
            "total": len(backups),
            "latest": latest_backup,
            "scheduler": (
                scheduler_status()
            ),
        },
    }