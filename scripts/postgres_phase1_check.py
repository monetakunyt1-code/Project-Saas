from __future__ import annotations

import sys
from pathlib import Path


# Memastikan root repository dapat di-import meskipun file ini
# dijalankan langsung dari folder scripts atau direktori lain.
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from services.postgres_connection import (  # noqa: E402
    DOCURAPI_SCHEMAS,
    ensure_docurapi_schemas,
    list_docurapi_schemas,
    ping_postgres,
)


def main() -> None:
    print()
    print("=" * 64)
    print("DOCURAPI POSTGRESQL RUNTIME CHECK")
    print("=" * 64)

    connection_info = ping_postgres()

    print(
        "Database :",
        connection_info["database_name"],
    )
    print(
        "User     :",
        connection_info["database_user"],
    )
    print(
        "Schema   :",
        connection_info["current_schema"],
    )

    ensure_docurapi_schemas()

    available = set(
        list_docurapi_schemas()
    )

    expected = set(
        DOCURAPI_SCHEMAS
    )

    missing = sorted(
        expected - available
    )

    print(
        "Namespace:",
        ", ".join(sorted(available)),
    )
    print(
        "Missing  :",
        missing,
    )

    if missing:
        raise RuntimeError(
            "Namespace PostgreSQL belum lengkap: "
            + ", ".join(missing)
        )

    print()
    print(
        "POSTGRESQL_RUNTIME_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
