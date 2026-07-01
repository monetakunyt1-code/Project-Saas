from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
from services import database_adapter as sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zipfile import (
    ZIP_DEFLATED,
    ZipFile,
)

from config import STORAGE_DIR
from system_database import (
    record_system_event,
)


BASE_DIR = Path(
    __file__
).resolve().parent.parent

BACKUP_ROOT = (
    STORAGE_DIR
    / "system_backups"
)

BACKUP_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

AUTO_BACKUP_ENABLED = (
    os.getenv(
        "DOCURAPI_AUTO_BACKUP",
        "1",
    )
    == "1"
)

AUTO_BACKUP_INTERVAL_SECONDS = max(
    300,
    int(
        os.getenv(
            "DOCURAPI_AUTO_BACKUP_INTERVAL",
            "86400",
        )
    ),
)

AUTO_BACKUP_KEEP = max(
    3,
    int(
        os.getenv(
            "DOCURAPI_AUTO_BACKUP_KEEP",
            "14",
        )
    ),
)

_backup_lock = threading.Lock()
_scheduler_lock = threading.Lock()
_scheduler_started = False


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_relative_path(
    path: Path,
) -> Path:
    resolved = path.resolve()
    root = BASE_DIR.resolve()

    try:
        return resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Path berada di luar folder proyek."
        ) from exc


def file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def is_sqlite_database(
    path: Path,
) -> bool:
    try:
        if not path.is_file():
            return False

        with path.open("rb") as file_handle:
            header = file_handle.read(16)

        return header == b"SQLite format 3\x00"

    except OSError:
        return False


def is_excluded_path(
    path: Path,
) -> bool:
    relative = safe_relative_path(path)

    for part in relative.parts:
        if part == ".venv":
            return True

        if part == "__pycache__":
            return True

        if part == "system_backups":
            return True

        if part.startswith("_backup_"):
            return True

    return False


def discover_databases() -> list[Path]:
    databases: list[Path] = []

    for path in BASE_DIR.rglob("*.db"):
        try:
            if is_excluded_path(path):
                continue

            if not is_sqlite_database(path):
                continue

            databases.append(
                path.resolve()
            )

        except (
            OSError,
            ValueError,
        ):
            continue

    return sorted(
        databases,
        key=lambda item: str(item),
    )


def sqlite_online_backup(
    source_path: Path,
    destination_path: Path,
) -> None:
    destination_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_connection = sqlite3.connect(
        str(source_path),
        timeout=30,
    )

    destination_connection = sqlite3.connect(
        str(destination_path),
        timeout=30,
    )

    try:
        source_connection.backup(
            destination_connection,
            pages=256,
            sleep=0.05,
        )

        destination_connection.commit()

    finally:
        destination_connection.close()
        source_connection.close()


def copy_metadata_files(
    destination: Path,
) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []

    candidates = [
        BASE_DIR / "FEATURE_MANIFEST.json",
        BASE_DIR / ".env.example",
    ]

    candidates.extend(
        BASE_DIR.glob("*_STATUS.txt")
    )

    for source in candidates:
        if not source.exists():
            continue

        target = (
            destination
            / source.name
        )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            target,
        )

        copied.append(
            {
                "name": source.name,
                "size_bytes": (
                    target.stat().st_size
                ),
                "sha256": file_sha256(
                    target
                ),
            }
        )

    return copied


def create_backup(
    label: str = "manual",
    initiated_by: str = "system",
) -> dict[str, Any]:
    with _backup_lock:
        databases = discover_databases()

        if not databases:
            raise RuntimeError(
                "Tidak ditemukan database SQLite."
            )

        timestamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_id = (
            f"{timestamp}_"
            f"{uuid4().hex[:8]}"
        )

        temporary_directory = (
            BACKUP_ROOT
            / f".tmp_{backup_id}"
        )

        final_directory = (
            BACKUP_ROOT
            / backup_id
        )

        archive_path = (
            BACKUP_ROOT
            / f"{backup_id}.zip"
        )

        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )

        temporary_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        database_records: list[
            dict[str, Any]
        ] = []

        try:
            for source_path in databases:
                source_relative = (
                    safe_relative_path(
                        source_path
                    )
                )

                backup_relative = (
                    Path("databases")
                    / source_relative
                )

                destination_path = (
                    temporary_directory
                    / backup_relative
                )

                sqlite_online_backup(
                    source_path,
                    destination_path,
                )

                database_records.append(
                    {
                        "source_relative": (
                            source_relative.as_posix()
                        ),
                        "backup_relative": (
                            backup_relative.as_posix()
                        ),
                        "size_bytes": (
                            destination_path
                            .stat()
                            .st_size
                        ),
                        "sha256": file_sha256(
                            destination_path
                        ),
                    }
                )

            metadata_records = copy_metadata_files(
                temporary_directory
                / "metadata"
            )

            manifest = {
                "backup_id": backup_id,
                "label": (
                    label.strip()
                    or "manual"
                )[:200],
                "initiated_by": (
                    initiated_by
                    or "system"
                )[:200],
                "created_at": utc_now(),
                "database_count": len(
                    database_records
                ),
                "databases": (
                    database_records
                ),
                "metadata_files": (
                    metadata_records
                ),
                "project_root_name": (
                    BASE_DIR.name
                ),
                "format_version": 1,
            }

            (
                temporary_directory
                / "manifest.json"
            ).write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            if final_directory.exists():
                shutil.rmtree(
                    final_directory
                )

            temporary_directory.rename(
                final_directory
            )

            with ZipFile(
                archive_path,
                "w",
                ZIP_DEFLATED,
            ) as archive:
                for file_path in (
                    final_directory.rglob("*")
                ):
                    if not file_path.is_file():
                        continue

                    archive.write(
                        file_path,
                        file_path.relative_to(
                            final_directory
                        ),
                    )

            result = {
                **manifest,
                "folder_path": str(
                    final_directory
                ),
                "archive_path": str(
                    archive_path
                ),
                "archive_size_bytes": (
                    archive_path
                    .stat()
                    .st_size
                ),
            }

            record_system_event(
                level="info",
                category="backup",
                message=(
                    f"Backup {backup_id} "
                    "berhasil dibuat."
                ),
                metadata_json=json.dumps(
                    {
                        "backup_id": backup_id,
                        "label": label,
                        "database_count": len(
                            database_records
                        ),
                    },
                    ensure_ascii=False,
                ),
            )

            return result

        except Exception:
            shutil.rmtree(
                temporary_directory,
                ignore_errors=True,
            )

            shutil.rmtree(
                final_directory,
                ignore_errors=True,
            )

            archive_path.unlink(
                missing_ok=True
            )

            raise


def read_manifest(
    backup_id: str,
) -> dict[str, Any]:
    manifest_path = (
        BACKUP_ROOT
        / backup_id
        / "manifest.json"
    )

    if not manifest_path.exists():
        raise FileNotFoundError(
            "Manifest backup tidak ditemukan."
        )

    return json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )


def get_backup_record(
    backup_id: str,
) -> dict[str, Any]:
    manifest = read_manifest(
        backup_id
    )

    folder_path = (
        BACKUP_ROOT
        / backup_id
    )

    archive_path = (
        BACKUP_ROOT
        / f"{backup_id}.zip"
    )

    return {
        **manifest,
        "folder_path": str(
            folder_path
        ),
        "archive_path": str(
            archive_path
        ),
        "archive_exists": (
            archive_path.exists()
        ),
        "archive_size_bytes": (
            archive_path.stat().st_size
            if archive_path.exists()
            else 0
        ),
    }


def list_backups() -> list[dict[str, Any]]:
    records: list[
        dict[str, Any]
    ] = []

    for directory in BACKUP_ROOT.iterdir():
        if not directory.is_dir():
            continue

        if directory.name.startswith(
            ".tmp_"
        ):
            continue

        try:
            records.append(
                get_backup_record(
                    directory.name
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

    records.sort(
        key=lambda item: item.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    return records


def verify_backup(
    backup_id: str,
) -> dict[str, Any]:
    record = get_backup_record(
        backup_id
    )

    folder_path = Path(
        record["folder_path"]
    )

    problems: list[str] = []
    verified_databases = 0

    for database in record.get(
        "databases",
        [],
    ):
        backup_path = (
            folder_path
            / database["backup_relative"]
        )

        if not backup_path.exists():
            problems.append(
                "File tidak ditemukan: "
                + database[
                    "backup_relative"
                ]
            )

            continue

        actual_checksum = file_sha256(
            backup_path
        )

        if (
            actual_checksum
            != database["sha256"]
        ):
            problems.append(
                "Checksum tidak sesuai: "
                + database[
                    "backup_relative"
                ]
            )

            continue

        try:
            connection = sqlite3.connect(
                str(backup_path),
                timeout=10,
            )

            check = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            connection.close()

            if (
                not check
                or check[0] != "ok"
            ):
                problems.append(
                    "SQLite quick_check gagal: "
                    + database[
                        "backup_relative"
                    ]
                )

                continue

        except sqlite3.Error as exc:
            problems.append(
                "Database tidak dapat dibuka: "
                + str(exc)
            )

            continue

        verified_databases += 1

    return {
        "backup_id": backup_id,
        "valid": not problems,
        "database_count": len(
            record.get(
                "databases",
                [],
            )
        ),
        "verified_databases": (
            verified_databases
        ),
        "problems": problems,
        "archive_exists": record[
            "archive_exists"
        ],
    }


def delete_backup(
    backup_id: str,
) -> None:
    folder_path = (
        BACKUP_ROOT
        / backup_id
    )

    archive_path = (
        BACKUP_ROOT
        / f"{backup_id}.zip"
    )

    if not folder_path.exists():
        raise FileNotFoundError(
            "Backup tidak ditemukan."
        )

    shutil.rmtree(
        folder_path,
        ignore_errors=False,
    )

    archive_path.unlink(
        missing_ok=True
    )

    record_system_event(
        level="warning",
        category="backup",
        message=(
            f"Backup {backup_id} dihapus."
        ),
    )


def prune_backups(
    keep: int = AUTO_BACKUP_KEEP,
) -> dict[str, Any]:
    safe_keep = max(
        1,
        min(int(keep), 365),
    )

    backups = list_backups()

    removed: list[str] = []

    for record in backups[safe_keep:]:
        backup_id = record["backup_id"]

        try:
            delete_backup(
                backup_id
            )

            removed.append(
                backup_id
            )

        except OSError:
            continue

    return {
        "keep": safe_keep,
        "removed_total": len(
            removed
        ),
        "removed": removed,
    }


def restore_plan(
    backup_id: str,
) -> dict[str, Any]:
    verification = verify_backup(
        backup_id
    )

    record = get_backup_record(
        backup_id
    )

    items = []

    for database in record.get(
        "databases",
        [],
    ):
        items.append(
            {
                "source_backup": (
                    database[
                        "backup_relative"
                    ]
                ),
                "target_database": (
                    database[
                        "source_relative"
                    ]
                ),
                "size_bytes": (
                    database[
                        "size_bytes"
                    ]
                ),
            }
        )

    return {
        "backup_id": backup_id,
        "verification": verification,
        "database_count": len(items),
        "items": items,
        "requires_server_stopped": True,
    }


def server_is_running(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> bool:
    try:
        with socket.create_connection(
            (host, port),
            timeout=0.5,
        ):
            return True

    except OSError:
        return False


def restore_backup(
    backup_id: str,
    force: bool = False,
) -> dict[str, Any]:
    if (
        server_is_running()
        and not force
    ):
        raise RuntimeError(
            "Server masih aktif. "
            "Hentikan server sebelum restore."
        )

    verification = verify_backup(
        backup_id
    )

    if not verification["valid"]:
        raise RuntimeError(
            "Backup gagal diverifikasi: "
            + "; ".join(
                verification["problems"]
            )
        )

    record = get_backup_record(
        backup_id
    )

    backup_folder = Path(
        record["folder_path"]
    )

    pre_restore = create_backup(
        label=(
            "pre_restore_"
            + backup_id
        ),
        initiated_by="restore_service",
    )

    restored: list[str] = []

    for database in record.get(
        "databases",
        [],
    ):
        backup_path = (
            backup_folder
            / database["backup_relative"]
        )

        target_path = (
            BASE_DIR
            / database["source_relative"]
        ).resolve()

        safe_relative_path(
            target_path
        )

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_target = (
            target_path.with_suffix(
                target_path.suffix
                + ".restore_tmp"
            )
        )

        shutil.copy2(
            backup_path,
            temporary_target,
        )

        Path(
            str(target_path)
            + "-wal"
        ).unlink(
            missing_ok=True
        )

        Path(
            str(target_path)
            + "-shm"
        ).unlink(
            missing_ok=True
        )

        os.replace(
            temporary_target,
            target_path,
        )

        restored.append(
            database[
                "source_relative"
            ]
        )

    record_system_event(
        level="warning",
        category="restore",
        message=(
            f"Backup {backup_id} "
            "berhasil dipulihkan."
        ),
        metadata_json=json.dumps(
            {
                "backup_id": backup_id,
                "pre_restore_backup": (
                    pre_restore[
                        "backup_id"
                    ]
                ),
                "databases": restored,
            },
            ensure_ascii=False,
        ),
    )

    return {
        "success": True,
        "backup_id": backup_id,
        "pre_restore_backup_id": (
            pre_restore["backup_id"]
        ),
        "restored_total": len(
            restored
        ),
        "restored": restored,
    }


def latest_auto_backup() -> (
    dict[str, Any] | None
):
    for backup in list_backups():
        if str(
            backup.get(
                "label",
                "",
            )
        ).startswith(
            "auto"
        ):
            return backup

    return None


def auto_backup_is_due() -> bool:
    latest = latest_auto_backup()

    if not latest:
        return True

    try:
        created_at = datetime.fromisoformat(
            latest["created_at"]
        )
    except (
        ValueError,
        TypeError,
    ):
        return True

    age_seconds = (
        datetime.now(timezone.utc)
        - created_at
    ).total_seconds()

    return (
        age_seconds
        >= AUTO_BACKUP_INTERVAL_SECONDS
    )


def _scheduler_loop() -> None:
    time.sleep(10)

    while True:
        try:
            if (
                AUTO_BACKUP_ENABLED
                and auto_backup_is_due()
            ):
                create_backup(
                    label="auto",
                    initiated_by=(
                        "automatic_scheduler"
                    ),
                )

                prune_backups(
                    AUTO_BACKUP_KEEP
                )

        except Exception as exc:
            record_system_event(
                level="error",
                category="backup_scheduler",
                message=str(exc),
            )

        time.sleep(
            min(
                AUTO_BACKUP_INTERVAL_SECONDS,
                3600,
            )
        )


def start_auto_backup() -> None:
    global _scheduler_started

    if not AUTO_BACKUP_ENABLED:
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        thread = threading.Thread(
            target=_scheduler_loop,
            name=(
                "docurapi-auto-backup"
            ),
            daemon=True,
        )

        thread.start()

        _scheduler_started = True

        record_system_event(
            level="info",
            category="backup_scheduler",
            message=(
                "Scheduler backup otomatis aktif."
            ),
        )


def scheduler_status() -> dict[str, Any]:
    return {
        "enabled": AUTO_BACKUP_ENABLED,
        "started": _scheduler_started,
        "interval_seconds": (
            AUTO_BACKUP_INTERVAL_SECONDS
        ),
        "keep_backups": (
            AUTO_BACKUP_KEEP
        ),
        "backup_due": (
            auto_backup_is_due()
            if AUTO_BACKUP_ENABLED
            else False
        ),
    }