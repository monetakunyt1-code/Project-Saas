from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from services.postgres_schema_fidelity import (  # noqa: E402
    apply_all_schema_fidelity,
)


def main() -> None:
    print()
    print("=" * 72)
    print("POSTGRESQL SCHEMA FIDELITY")
    print("=" * 72)

    results = apply_all_schema_fidelity(
        ROOT
    )

    totals = {
        "databases": len(results),
        "tables": 0,
        "primary_keys": 0,
        "sequences": 0,
        "not_null": 0,
        "defaults": 0,
        "indexes": 0,
        "unique_indexes": 0,
        "foreign_keys": 0,
        "unsupported_defaults": 0,
        "unsupported_indexes": 0,
    }

    for result in results:
        print()
        print(
            "Database:",
            result["source_database"],
        )
        print(
            "Schema  :",
            result["schema_name"],
        )

        for key in totals:
            if key == "databases":
                continue

            value = int(
                result.get(key, 0)
            )

            totals[key] += value

            print(
                f"  {key:22}:",
                value,
            )

    print()
    print("=" * 72)
    print("RINGKASAN SCHEMA FIDELITY")
    print("=" * 72)

    for key, value in totals.items():
        print(
            f"{key:24}:",
            value,
        )

    if totals["databases"] != 7:
        raise RuntimeError(
            "Jumlah database bukan tujuh."
        )

    if totals["tables"] != 34:
        raise RuntimeError(
            "Jumlah tabel bukan 34."
        )

    report_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "/tmp/DOCURAPI_POSTGRES_PHASE2B.json"
    )

    report_path.write_text(
        json.dumps(
            {
                "totals": totals,
                "databases": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Laporan:", report_path)
    print(
        "POSTGRES_SCHEMA_FIDELITY_PASSED"
    )


if __name__ == "__main__":
    main()
