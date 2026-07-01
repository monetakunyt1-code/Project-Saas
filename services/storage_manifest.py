"""Manifest hubungan file lokal dan object storage DocuRapi."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services import database_adapter as database


ROOT = Path(__file__).resolve().parents[1]

MANIFEST_DATABASE = (
    ROOT
    / "storage"
    / "docurapi.db"
)


@dataclass(frozen=True)
class StorageManifestRecord:
    local_path: str
    object_reference: str
    object_key: str
    field_name: str
    module_name: str
    backend: str
    size: int
    checksum: str | None
    created_at: str
    updated_at: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_local_path(
    value: str | os.PathLike[str],
) -> str:
    return str(
        Path(value)
        .expanduser()
        .resolve()
    )


def connect() -> Any:
    connection = database.connect(
        MANIFEST_DATABASE,
        timeout=30,
    )

    connection.row_factory = (
        database.Row
    )

    return connection


def initialize() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                storage_object_mirrors
            (
                local_path TEXT
                    PRIMARY KEY,

                object_reference TEXT
                    NOT NULL,

                object_key TEXT
                    NOT NULL,

                field_name TEXT
                    NOT NULL,

                module_name TEXT
                    NOT NULL,

                backend TEXT
                    NOT NULL,

                size INTEGER
                    NOT NULL,

                checksum TEXT,

                created_at TEXT
                    NOT NULL,

                updated_at TEXT
                    NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_storage_object_reference
            ON storage_object_mirrors(
                object_reference
            );

            CREATE INDEX IF NOT EXISTS
                idx_storage_object_field
            ON storage_object_mirrors(
                field_name,
                updated_at
            );
            """
        )


def record_mirror(
    *,
    local_path: str | os.PathLike[str],
    object_reference: str,
    object_key: str,
    field_name: str,
    module_name: str,
    backend: str,
    size: int,
    checksum: str | None = None,
) -> StorageManifestRecord:
    """Mencatat hubungan path lokal dengan object storage.

    Satu object reference hanya boleh memiliki satu local path aktif.
    Jika local path atau object reference telah dipakai record lain,
    record lama diganti secara atomik dalam transaksi yang sama.
    """

    normalized_local = normalize_local_path(
        local_path
    )

    timestamp = utc_now()

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT
                created_at
            FROM storage_object_mirrors
            WHERE
                local_path = ?
                OR object_reference = ?
            ORDER BY
                CASE
                    WHEN local_path = ?
                    THEN 0
                    ELSE 1
                END
            LIMIT 1
            """,
            (
                normalized_local,
                object_reference,
                normalized_local,
            ),
        ).fetchone()

        created_at = (
            str(existing["created_at"])
            if existing is not None
            else timestamp
        )

        # Menghapus kedua kemungkinan konflik:
        #
        # 1. local_path yang sama sudah menunjuk object lain;
        # 2. object_reference yang sama berasal dari local path lain.
        connection.execute(
            """
            DELETE FROM storage_object_mirrors
            WHERE
                local_path = ?
                OR object_reference = ?
            """,
            (
                normalized_local,
                object_reference,
            ),
        )

        connection.execute(
            """
            INSERT INTO storage_object_mirrors
            (
                local_path,
                object_reference,
                object_key,
                field_name,
                module_name,
                backend,
                size,
                checksum,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_local,
                object_reference,
                object_key,
                field_name,
                module_name,
                backend,
                int(size),
                checksum,
                created_at,
                timestamp,
            ),
        )

    result = get_mirror(
        normalized_local
    )

    if result is None:
        raise RuntimeError(
            "Storage manifest gagal disimpan."
        )

    if (
        result.object_reference
        != object_reference
    ):
        raise RuntimeError(
            "Storage manifest menghasilkan "
            "object reference yang tidak sesuai."
        )

    return result


def get_mirror(
    local_path: str | os.PathLike[str],
) -> StorageManifestRecord | None:
    normalized_local = normalize_local_path(
        local_path
    )

    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                local_path,
                object_reference,
                object_key,
                field_name,
                module_name,
                backend,
                size,
                checksum,
                created_at,
                updated_at
            FROM storage_object_mirrors
            WHERE local_path = ?
            LIMIT 1
            """,
            (
                normalized_local,
            ),
        ).fetchone()

    if row is None:
        return None

    return StorageManifestRecord(
        local_path=str(
            row["local_path"]
        ),
        object_reference=str(
            row["object_reference"]
        ),
        object_key=str(
            row["object_key"]
        ),
        field_name=str(
            row["field_name"]
        ),
        module_name=str(
            row["module_name"]
        ),
        backend=str(
            row["backend"]
        ),
        size=int(
            row["size"]
        ),
        checksum=(
            str(row["checksum"])
            if row["checksum"]
            is not None
            else None
        ),
        created_at=str(
            row["created_at"]
        ),
        updated_at=str(
            row["updated_at"]
        ),
    )


def delete_mirror(
    local_path: str | os.PathLike[str],
) -> bool:
    normalized_local = normalize_local_path(
        local_path
    )

    with connect() as connection:
        cursor = connection.execute(
            """
            DELETE FROM storage_object_mirrors
            WHERE local_path = ?
            """,
            (
                normalized_local,
            ),
        )

        return cursor.rowcount > 0


def storage_statistics() -> dict[str, Any]:
    with connect() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS object_count,

                COALESCE(
                    SUM(size),
                    0
                ) AS total_bytes,

                COUNT(
                    DISTINCT backend
                ) AS backend_count
            FROM storage_object_mirrors
            """
        ).fetchone()

        fields = connection.execute(
            """
            SELECT
                field_name,
                COUNT(*) AS total
            FROM storage_object_mirrors
            GROUP BY field_name
            ORDER BY field_name
            """
        ).fetchall()

    return {
        "object_count": int(
            summary["object_count"]
        ),
        "total_bytes": int(
            summary["total_bytes"]
        ),
        "backend_count": int(
            summary["backend_count"]
        ),
        "fields": {
            str(row["field_name"]):
                int(row["total"])
            for row in fields
        },
    }


initialize()
