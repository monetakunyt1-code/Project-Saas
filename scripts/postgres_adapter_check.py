from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services import database_adapter as db  # noqa: E402


DATABASE_TABLES = (
    (
        "storage/docurapi.db",
        "core",
        "jobs",
    ),
    (
        "storage/billing/billing.db",
        "billing",
        "billing_products",
    ),
    (
        "storage/saas/saas.db",
        "saas",
        "users",
    ),
    (
        "storage/saas/security.db",
        "security",
        "rate_limits",
    ),
    (
        (
            "storage/background/"
            "background_jobs.db"
        ),
        "background",
        "background_jobs",
    ),
    (
        (
            "storage/notifications/"
            "notifications.db"
        ),
        "notifications",
        "notifications",
    ),
    (
        (
            "storage/system/"
            "observability.db"
        ),
        "observability",
        "request_metrics",
    ),
)


def check_schema_connections() -> None:
    for path, schema, table in (
        DATABASE_TABLES
    ):
        with db.connect(
            path,
            timeout=30,
        ) as connection:
            connection.row_factory = (
                db.Row
            )

            if (
                connection.schema_name
                != schema
            ):
                raise RuntimeError(
                    f"Schema salah untuk {path}: "
                    f"{connection.schema_name}"
                )

            row = connection.execute(
                f"""
                SELECT
                    COUNT(*) AS total
                FROM "{table}"
                """
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    f"Tidak ada hasil dari {table}."
                )

            if row[0] != row["total"]:
                raise RuntimeError(
                    "Row tidak kompatibel "
                    "dengan indeks dan nama."
                )

            print(
                f"{schema:14} "
                f"{table:32} "
                f"rows={row['total']}"
            )


def check_sqlite_compatibility() -> None:
    with db.connect(
        "storage/docurapi.db",
        timeout=30,
    ) as connection:
        connection.row_factory = db.Row

        quick_check = (
            connection.execute(
                "PRAGMA quick_check"
            ).fetchone()
        )

        if (
            quick_check is None
            or quick_check[0] != "ok"
        ):
            raise RuntimeError(
                "PRAGMA quick_check tidak kompatibel."
            )

        table_info = (
            connection.execute(
                'PRAGMA table_info("jobs")'
            ).fetchall()
        )

        if not table_info:
            raise RuntimeError(
                "PRAGMA table_info tidak "
                "menghasilkan kolom."
            )

        column_names = {
            row["name"]
            for row in table_info
        }

        if "job_id" not in column_names:
            raise RuntimeError(
                "Kolom job_id tidak ditemukan."
            )

        master_rows = (
            connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        )

        if not master_rows:
            raise RuntimeError(
                "sqlite_master compatibility gagal."
            )

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                adapter_phase2c_probe
            (
                probe_id INTEGER
                    PRIMARY KEY
                    AUTOINCREMENT,
                probe_key TEXT
                    NOT NULL
                    UNIQUE,
                probe_value TEXT
                    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS
                idx_adapter_phase2c_value
            ON adapter_phase2c_probe(
                probe_value
            );
            """
        )

        connection.execute(
            "BEGIN IMMEDIATE"
        )

        connection.execute(
            """
            DELETE FROM
                adapter_phase2c_probe
            WHERE probe_key = ?
            """,
            (
                "phase2c",
            ),
        )

        first = connection.execute(
            """
            INSERT OR IGNORE INTO
                adapter_phase2c_probe
            (
                probe_key,
                probe_value
            )
            VALUES (?, ?)
            """,
            (
                "phase2c",
                "first",
            ),
        )

        second = connection.execute(
            """
            INSERT OR IGNORE INTO
                adapter_phase2c_probe
            (
                probe_key,
                probe_value
            )
            VALUES (?, ?)
            """,
            (
                "phase2c",
                "second",
            ),
        )

        result = connection.execute(
            """
            SELECT
                probe_key,
                probe_value
            FROM adapter_phase2c_probe
            WHERE probe_key = ?
            """,
            (
                "phase2c",
            ),
        )

        row = result.fetchone()

        if row is None:
            raise RuntimeError(
                "Data adapter probe tidak ditemukan."
            )

        if row["probe_value"] != "first":
            raise RuntimeError(
                "INSERT OR IGNORE tidak bekerja."
            )

        if result.description is None:
            raise RuntimeError(
                "Cursor description tidak tersedia."
            )

        print(
            "Probe insert pertama rowcount:",
            first.rowcount,
        )

        print(
            "Probe insert kedua rowcount:",
            second.rowcount,
        )

        connection.execute(
            """
            DROP TABLE IF EXISTS
                adapter_phase2c_probe
            """
        )

    print(
        "SQLITE_API_COMPATIBILITY_PASSED"
    )


def check_application_import() -> None:
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
            "Aplikasi tidak menggunakan "
            "PostgreSQL saat live check."
        )

    print(
        "APPLICATION_POSTGRES_IMPORT_PASSED"
    )


def main() -> None:
    print()
    print("=" * 72)
    print("DOCURAPI POSTGRESQL ADAPTER CHECK")
    print("=" * 72)

    print(
        "Backend:",
        db.backend_name(),
    )

    if db.backend_name() != "postgresql":
        raise RuntimeError(
            "DOCURAPI_DATABASE_URL "
            "belum aktif."
        )

    check_schema_connections()
    check_sqlite_compatibility()
    check_application_import()

    print()
    print("=" * 72)
    print("POSTGRESQL ADAPTER CHECK BERHASIL")
    print("=" * 72)
    print(
        "DOCURAPI_POSTGRES_ADAPTER_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
