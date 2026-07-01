from __future__ import annotations

import argparse
import json

from services.retention_service import (
    apply_retention,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Maintenance dan retensi data DocuRapi."
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help=(
            "Hapus data yang lebih lama "
            "dari jumlah hari ini."
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Jalankan penghapusan. "
            "Tanpa opsi ini hanya pratinjau."
        ),
    )

    arguments = parser.parse_args()

    result = apply_retention(
        retention_days=arguments.days,
        dry_run=not arguments.apply,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()