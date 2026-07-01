from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services import database_adapter as database  # noqa: E402
from services.runtime_file_mirror import (  # noqa: E402
    mirror_local_file,
)


SOURCES = (
    {
        "database":
            ROOT
            / "storage"
            / "docurapi.db",

        "module":
            "database",

        "queries": (
            (
                """
                SELECT
                    job_id,
                    output_path,
                    report_path
                FROM jobs
                """,
                (
                    "output_path",
                    "report_path",
                ),
                "job_id",
            ),
            (
                """
                SELECT
                    template_id,
                    file_path
                FROM templates
                """,
                (
                    "file_path",
                ),
                "template_id",
            ),
        ),
    },
    {
        "database":
            ROOT
            / "storage"
            / "background"
            / "background_jobs.db",

        "module":
            "background_database",

        "queries": (
            (
                """
                SELECT
                    job_id,
                    user_id,
                    workspace_id,
                    target_path,
                    artifact_path
                FROM background_jobs
                """,
                (
                    "target_path",
                    "artifact_path",
                ),
                "job_id",
            ),
        ),
    },
    {
        "database":
            ROOT
            / "storage"
            / "notifications"
            / "notifications.db",

        "module":
            "notification_database",

        "queries": (
            (
                """
                SELECT
                    email_id,
                    user_id,
                    local_file_path
                FROM email_outbox
                """,
                (
                    "local_file_path",
                ),
                "email_id",
            ),
        ),
    },
)


def row_arguments(
    row: Any,
    resource_field: str,
) -> dict[str, Any]:
    arguments: dict[
        str,
        Any,
    ] = {
        "resource_id":
            row[resource_field],
    }

    for field in (
        "user_id",
        "workspace_id",
        "job_id",
        "template_id",
        "email_id",
    ):
        try:
            value = row[field]
        except (
            KeyError,
            IndexError,
        ):
            continue

        if value not in {
            None,
            "",
        }:
            arguments[field] = (
                value
            )

    return arguments


def main() -> None:
    mirrored = 0
    skipped = 0
    failed = 0

    print()
    print("=" * 72)
    print("DOCURAPI OBJECT STORAGE BACKFILL")
    print("=" * 72)

    for source in SOURCES:
        connection = database.connect(
            source["database"],
            timeout=30,
        )

        connection.row_factory = (
            database.Row
        )

        try:
            for (
                query,
                fields,
                resource_field,
            ) in source["queries"]:
                rows = connection.execute(
                    query
                ).fetchall()

                for row in rows:
                    arguments = row_arguments(
                        row,
                        resource_field,
                    )

                    for field in fields:
                        value = row[field]

                        if not value:
                            skipped += 1
                            continue

                        try:
                            record = (
                                mirror_local_file(
                                    value,
                                    field_name=
                                        field,
                                    arguments=
                                        arguments,
                                    module_name=
                                        source[
                                            "module"
                                        ],
                                )
                            )

                            if record is None:
                                skipped += 1
                                continue

                            mirrored += 1

                            print(
                                "MIRRORED:",
                                field,
                                "->",
                                record.object_reference,
                            )

                        except Exception as exc:
                            failed += 1

                            print(
                                "FAILED:",
                                field,
                                value,
                                type(exc).__name__,
                                str(exc),
                            )

        finally:
            connection.close()

    print()
    print("Mirrored :", mirrored)
    print("Skipped  :", skipped)
    print("Failed   :", failed)

    if failed:
        raise RuntimeError(
            f"{failed} file gagal dibackfill."
        )

    print(
        "OBJECT_STORAGE_BACKFILL_PASSED"
    )


if __name__ == "__main__":
    main()
