from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from services.sqlite_postgres_migration import (  # noqa: E402
    migrate_all,
)


def main() -> None:
    print()
    print("=" * 72)
    print("MIGRASI SNAPSHOT SQLITE KE POSTGRESQL")
    print("=" * 72)

    results = migrate_all(
        ROOT
    )

    total_databases = len(results)
    total_tables = 0
    total_source_rows = 0
    total_target_rows = 0

    for database in results:
        print()
        print(
            "Database:",
            database["source"],
        )
        print(
            "Schema  :",
            database["schema"],
        )
        print(
            "SHA256  :",
            database["checksum"],
        )

        for table in database["tables"]:
            total_tables += 1
            total_source_rows += int(
                table["source_rows"]
            )
            total_target_rows += int(
                table["target_rows"]
            )

            print(
                "  -",
                table["table"],
                "| kolom:",
                table["columns"],
                "| SQLite:",
                table["source_rows"],
                "| PostgreSQL:",
                table["target_rows"],
            )

    print()
    print("=" * 72)
    print("RINGKASAN MIGRASI")
    print("=" * 72)
    print(
        "Database        :",
        total_databases,
    )
    print(
        "Tabel           :",
        total_tables,
    )
    print(
        "Baris SQLite    :",
        total_source_rows,
    )
    print(
        "Baris PostgreSQL:",
        total_target_rows,
    )

    if total_source_rows != total_target_rows:
        raise RuntimeError(
            "Total jumlah baris tidak sama."
        )

    report_path = Path(
        "/tmp/DOCURAPI_SQLITE_POSTGRES_RESULT.json"
    )

    report_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Laporan JSON    :",
        report_path,
    )
    print()
    print(
        "DOCURAPI_SQLITE_POSTGRES_MIGRATION_PASSED"
    )


if __name__ == "__main__":
    main()
