from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"

FILE_DIRECTORIES = [
    STORAGE_DIR / "uploads",
    STORAGE_DIR / "outputs",
    STORAGE_DIR / "reports",
    STORAGE_DIR / "exports",
    STORAGE_DIR / "report_views",
]

FOLDER_DIRECTORIES = [
    STORAGE_DIR / "audits",
    STORAGE_DIR / "journals",
]


def utc_datetime(
    timestamp: float,
) -> datetime:
    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    )


def directory_latest_modified(
    directory: Path,
) -> float:
    timestamps = [
        directory.stat().st_mtime
    ]

    for path in directory.rglob("*"):
        try:
            timestamps.append(
                path.stat().st_mtime
            )
        except OSError:
            continue

    return max(
        timestamps
    )


def directory_size(
    directory: Path,
) -> int:
    total = 0

    for path in directory.rglob("*"):
        if not path.is_file():
            continue

        try:
            total += path.stat().st_size
        except OSError:
            continue

    return total


def preview_retention(
    retention_days: int,
) -> list[dict[str, Any]]:
    safe_days = max(
        1,
        min(int(retention_days), 3650),
    )

    threshold = (
        datetime.now(timezone.utc)
        - timedelta(days=safe_days)
    )

    candidates: list[
        dict[str, Any]
    ] = []

    for directory in FILE_DIRECTORIES:
        if not directory.exists():
            continue

        for path in directory.rglob("*"):
            if not path.is_file():
                continue

            try:
                modified = utc_datetime(
                    path.stat().st_mtime
                )
                size = path.stat().st_size
            except OSError:
                continue

            if modified >= threshold:
                continue

            candidates.append(
                {
                    "type": "file",
                    "path": str(path),
                    "size_bytes": size,
                    "modified_at": (
                        modified.isoformat()
                    ),
                }
            )

    for directory in FOLDER_DIRECTORIES:
        if not directory.exists():
            continue

        for child in directory.iterdir():
            if not child.is_dir():
                continue

            try:
                modified_timestamp = (
                    directory_latest_modified(
                        child
                    )
                )

                modified = utc_datetime(
                    modified_timestamp
                )
            except OSError:
                continue

            if modified >= threshold:
                continue

            candidates.append(
                {
                    "type": "directory",
                    "path": str(child),
                    "size_bytes": (
                        directory_size(child)
                    ),
                    "modified_at": (
                        modified.isoformat()
                    ),
                }
            )

    batch_directory = (
        STORAGE_DIR
        / "batches"
    )

    if batch_directory.exists():
        for child in batch_directory.glob(
            "work_*"
        ):
            if not child.is_dir():
                continue

            try:
                modified = utc_datetime(
                    directory_latest_modified(
                        child
                    )
                )
            except OSError:
                continue

            if modified >= threshold:
                continue

            candidates.append(
                {
                    "type": "directory",
                    "path": str(child),
                    "size_bytes": (
                        directory_size(child)
                    ),
                    "modified_at": (
                        modified.isoformat()
                    ),
                }
            )

    return sorted(
        candidates,
        key=lambda item: item[
            "modified_at"
        ],
    )


def apply_retention(
    retention_days: int,
    dry_run: bool = True,
) -> dict[str, Any]:
    candidates = preview_retention(
        retention_days
    )

    removed: list[
        dict[str, Any]
    ] = []

    failed: list[
        dict[str, str]
    ] = []

    for item in candidates:
        path = Path(
            item["path"]
        )

        if dry_run:
            removed.append(item)
            continue

        try:
            if item["type"] == "directory":
                shutil.rmtree(
                    path,
                    ignore_errors=False,
                )
            else:
                path.unlink(
                    missing_ok=True
                )

            removed.append(item)

        except OSError as exc:
            failed.append(
                {
                    "path": str(path),
                    "error": str(exc),
                }
            )

    return {
        "dry_run": dry_run,
        "retention_days": int(
            retention_days
        ),
        "candidates_total": len(
            candidates
        ),
        "removed_total": len(
            removed
        ),
        "failed_total": len(
            failed
        ),
        "size_bytes": sum(
            int(item["size_bytes"])
            for item in removed
        ),
        "items": removed,
        "failures": failed,
    }