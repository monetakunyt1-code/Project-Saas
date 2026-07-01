from __future__ import annotations

import argparse
import json

from services.backup_service import (
    create_backup,
    list_backups,
    prune_backups,
    restore_backup,
    restore_plan,
    verify_backup,
)
from services.system_health_service import (
    build_health_snapshot,
)


def print_json(
    payload: object,
) -> None:
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Maintenance, backup, restore, "
            "dan health check DocuRapi."
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    backup_parser = subparsers.add_parser(
        "backup"
    )

    backup_parser.add_argument(
        "--label",
        default="manual_cli",
    )

    subparsers.add_parser(
        "list"
    )

    verify_parser = subparsers.add_parser(
        "verify"
    )

    verify_parser.add_argument(
        "--backup-id",
        required=True,
    )

    restore_parser = subparsers.add_parser(
        "restore"
    )

    restore_parser.add_argument(
        "--backup-id",
        required=True,
    )

    restore_parser.add_argument(
        "--apply",
        action="store_true",
    )

    restore_parser.add_argument(
        "--force",
        action="store_true",
    )

    prune_parser = subparsers.add_parser(
        "prune"
    )

    prune_parser.add_argument(
        "--keep",
        type=int,
        default=14,
    )

    subparsers.add_parser(
        "health"
    )

    arguments = parser.parse_args()

    if arguments.command == "backup":
        print_json(
            create_backup(
                label=arguments.label,
                initiated_by="maintenance_cli",
            )
        )

    elif arguments.command == "list":
        print_json(
            list_backups()
        )

    elif arguments.command == "verify":
        print_json(
            verify_backup(
                arguments.backup_id
            )
        )

    elif arguments.command == "restore":
        if not arguments.apply:
            print_json(
                restore_plan(
                    arguments.backup_id
                )
            )

            print(
                "\nRestore belum dijalankan. "
                "Tambahkan --apply untuk melanjutkan."
            )

            return

        print_json(
            restore_backup(
                backup_id=arguments.backup_id,
                force=arguments.force,
            )
        )

    elif arguments.command == "prune":
        print_json(
            prune_backups(
                keep=arguments.keep
            )
        )

    elif arguments.command == "health":
        print_json(
            build_health_snapshot(
                include_sensitive_paths=True
            )
        )


if __name__ == "__main__":
    main()