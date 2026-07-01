from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services import database_adapter as db  # noqa: E402
from services.postgres_connection import (  # noqa: E402
    postgres_connection,
)


DATABASES = (
    (
        "storage/docurapi.db",
        "core",
    ),
    (
        "storage/billing/billing.db",
        "billing",
    ),
    (
        "storage/saas/saas.db",
        "saas",
    ),
    (
        "storage/saas/security.db",
        "security",
    ),
    (
        "storage/background/background_jobs.db",
        "background",
    ),
    (
        "storage/notifications/notifications.db",
        "notifications",
    ),
    (
        "storage/system/observability.db",
        "observability",
    ),
)


def quote_identifier(
    value: str,
) -> str:
    return '"' + value.replace(
        '"',
        '""',
    ) + '"'


def verify_backend() -> None:
    print("Backend:", db.backend_name())

    if db.backend_name() != "postgresql":
        raise RuntimeError(
            "Runtime belum menggunakan PostgreSQL."
        )


def load_migration_inventory() -> dict[
    str,
    list[dict[str, Any]],
]:
    with postgres_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                source_database,
                schema_name,
                table_name,
                target_rows
            FROM
                docurapi_meta.sqlite_migration_tables
            ORDER BY
                source_database,
                table_name
            """
        ).fetchall()

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[
            str(row["source_database"])
        ].append(
            dict(row)
        )

    return dict(grouped)


def verify_all_migrated_tables() -> int:
    inventory = load_migration_inventory()

    if len(inventory) != 7:
        raise RuntimeError(
            f"Inventaris hanya memuat {len(inventory)} database."
        )

    total_current_rows = 0
    total_snapshot_rows = 0
    total_tables = 0

    for database_path, schema_name in DATABASES:
        tables = inventory.get(
            database_path,
            [],
        )

        if not tables:
            raise RuntimeError(
                f"Inventaris kosong: {database_path}"
            )

        with db.connect(
            database_path,
            timeout=30,
        ) as connection:
            connection.row_factory = db.Row

            schema_row = connection.execute(
                """
                SELECT
                    current_schema()
                        AS schema_name
                """
            ).fetchone()

            if schema_row is None:
                raise RuntimeError(
                    "current_schema() tidak menghasilkan data."
                )

            if schema_row["schema_name"] != schema_name:
                raise RuntimeError(
                    f"Schema {database_path} salah: "
                    f"{schema_row['schema_name']}"
                )

            for table in tables:
                table_name = str(
                    table["table_name"]
                )

                expected_rows = int(
                    table["target_rows"]
                )

                statement = (
                    "SELECT COUNT(*) AS total "
                    "FROM "
                    + quote_identifier(
                        table_name
                    )
                )

                row = connection.execute(
                    statement
                ).fetchone()

                if row is None:
                    raise RuntimeError(
                        f"Tabel tidak dapat dibaca: "
                        f"{schema_name}.{table_name}"
                    )

                current_rows = int(
                    row["total"]
                )

                if current_rows < expected_rows:
                    raise RuntimeError(
                        f"Jumlah baris berkurang pada "
                        f"{schema_name}.{table_name}: "
                        f"snapshot={expected_rows}, "
                        f"current={current_rows}"
                    )

                total_tables += 1
                total_snapshot_rows += (
                    expected_rows
                )
                total_current_rows += (
                    current_rows
                )

        print(
            f"{schema_name:14} "
            f"tables={len(tables)}"
        )

    print(
        "Tabel diverifikasi :",
        total_tables,
    )

    print(
        "Baris snapshot     :",
        total_snapshot_rows,
    )

    print(
        "Baris saat ini     :",
        total_current_rows,
    )

    if total_tables != 34:
        raise RuntimeError(
            f"Jumlah tabel {total_tables}, seharusnya 34."
        )

    if total_snapshot_rows != 116:
        raise RuntimeError(
            f"Jumlah snapshot {total_snapshot_rows}, "
            "seharusnya 116."
        )

    return total_current_rows


def verify_transaction_compatibility() -> None:
    for database_path, schema_name in DATABASES:
        with db.connect(
            database_path,
            timeout=30,
        ) as connection:
            connection.row_factory = db.Row

            connection.execute(
                """
                CREATE TEMP TABLE
                    docurapi_runtime_probe
                (
                    probe_key TEXT
                        PRIMARY KEY,
                    probe_value TEXT
                        NOT NULL
                )
                """
            )

            connection.commit()

            connection.execute(
                "BEGIN IMMEDIATE"
            )

            connection.execute(
                """
                INSERT INTO
                    docurapi_runtime_probe
                (
                    probe_key,
                    probe_value
                )
                VALUES (?, ?)
                """,
                (
                    "rollback",
                    schema_name,
                ),
            )

            connection.rollback()

            rollback_row = (
                connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM docurapi_runtime_probe
                    WHERE probe_key = ?
                    """,
                    ("rollback",),
                ).fetchone()
            )

            if (
                rollback_row is None
                or int(
                    rollback_row["total"]
                ) != 0
            ):
                raise RuntimeError(
                    f"Rollback gagal pada schema {schema_name}."
                )

            first = connection.execute(
                """
                INSERT OR IGNORE INTO
                    docurapi_runtime_probe
                (
                    probe_key,
                    probe_value
                )
                VALUES (?, ?)
                """,
                (
                    "committed",
                    "first",
                ),
            )

            second = connection.execute(
                """
                INSERT OR IGNORE INTO
                    docurapi_runtime_probe
                (
                    probe_key,
                    probe_value
                )
                VALUES (?, ?)
                """,
                (
                    "committed",
                    "second",
                ),
            )

            connection.commit()

            committed_row = (
                connection.execute(
                    """
                    SELECT
                        probe_key,
                        probe_value
                    FROM
                        docurapi_runtime_probe
                    WHERE
                        probe_key = ?
                    """,
                    ("committed",),
                ).fetchone()
            )

            if committed_row is None:
                raise RuntimeError(
                    f"Commit gagal pada schema {schema_name}."
                )

            if (
                committed_row["probe_value"]
                != "first"
            ):
                raise RuntimeError(
                    f"INSERT OR IGNORE gagal "
                    f"pada schema {schema_name}."
                )

            if (
                committed_row[0]
                != committed_row["probe_key"]
            ):
                raise RuntimeError(
                    "Row index/name compatibility gagal."
                )

            if first.rowcount != 1:
                raise RuntimeError(
                    f"Rowcount insert pertama salah: "
                    f"{first.rowcount}"
                )

            if second.rowcount != 0:
                raise RuntimeError(
                    f"Rowcount insert duplikat salah: "
                    f"{second.rowcount}"
                )

            connection.execute(
                """
                DROP TABLE
                    docurapi_runtime_probe
                """
            )

            connection.commit()

        print(
            f"{schema_name:14} transaction=PASSED"
        )

    print(
        "POSTGRES_TRANSACTION_COMPATIBILITY_PASSED"
    )


def verify_application_import() -> None:
    from app import app

    paths = {
        path
        for route in app.routes
        if isinstance(
            path := getattr(
                route,
                "path",
                None,
            ),
            str,
        )
    }

    required = {
        "/",
        "/billing",
        "/api/plans",
        "/api/process",
    }

    missing = sorted(
        required - paths
    )

    print(
        "Application type:",
        type(app).__name__,
    )

    print(
        "Route objects   :",
        len(app.routes),
    )

    print(
        "Missing routes  :",
        missing,
    )

    if missing:
        raise RuntimeError(
            "Route wajib tidak tersedia: "
            + ", ".join(missing)
        )

    if db.backend_name() != "postgresql":
        raise RuntimeError(
            "Application import tidak menggunakan PostgreSQL."
        )

    print(
        "APPLICATION_POSTGRES_RUNTIME_IMPORT_PASSED"
    )


def main() -> None:
    print()
    print("=" * 72)
    print("POSTGRESQL RUNTIME CUTOVER CHECK")
    print("=" * 72)

    verify_backend()
    verify_all_migrated_tables()
    verify_transaction_compatibility()
    verify_application_import()

    print()
    print("=" * 72)
    print("POSTGRESQL RUNTIME CUTOVER CHECK BERHASIL")
    print("=" * 72)
    print(
        "DOCURAPI_POSTGRES_RUNTIME_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
