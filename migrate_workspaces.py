from __future__ import annotations

import json
from pathlib import Path

from saas_database import (
    admin_users,
    get_user_by_email,
)
from workspace_database import (
    claim_resource,
    ensure_personal_workspace,
    initialize_workspace_database,
)


initialize_workspace_database()

users = admin_users()

workspace_by_user: dict[str, dict] = {}

for user in users:
    workspace = ensure_personal_workspace(
        user_id=user["user_id"],
        display_name=user["display_name"],
    )

    workspace_by_user[
        user["user_id"]
    ] = workspace

    print(
        "PERSONAL_WORKSPACE",
        user["email"],
        workspace["workspace_id"],
    )


admin = get_user_by_email(
    "admin@docurapi.local"
)

if not admin:
    print(
        "ADMIN_NOT_FOUND_SKIP_LEGACY_MIGRATION"
    )

    raise SystemExit(0)


admin_workspace = workspace_by_user.get(
    admin["user_id"]
)

if not admin_workspace:
    admin_workspace = ensure_personal_workspace(
        user_id=admin["user_id"],
        display_name=admin["display_name"],
    )


def claim(
    resource_type: str,
    resource_id: object,
    metadata: dict | None = None,
) -> None:
    if resource_id is None:
        return

    claim_resource(
        resource_type=resource_type,
        resource_id=str(resource_id),
        workspace_id=(
            admin_workspace["workspace_id"]
        ),
        owner_user_id=admin["user_id"],
        metadata={
            "migration": "legacy",
            **(metadata or {}),
        },
    )


try:
    from database import (
        list_jobs,
        list_templates,
    )

    for job in list_jobs(limit=10000):
        claim(
            "job",
            job.get("job_id"),
            {
                "original_name": (
                    job.get("original_name")
                )
            },
        )

    for template in list_templates():
        claim(
            "template",
            template.get("template_id"),
            {
                "template_name": (
                    template.get("template_name")
                )
            },
        )

except Exception as exc:
    print(
        "LEGACY_DATABASE_WARNING",
        str(exc),
    )


try:
    from services.profile_manager import (
        list_profiles,
    )

    for profile in list_profiles():
        claim(
            "profile",
            profile.get("profile_id"),
            {
                "name": profile.get("name")
            },
        )

except Exception as exc:
    print(
        "PROFILE_MIGRATION_WARNING",
        str(exc),
    )


try:
    from services.batch_manager import (
        list_batches,
    )

    for batch in list_batches():
        claim(
            "batch",
            batch.get("batch_id"),
        )

except Exception as exc:
    print(
        "BATCH_MIGRATION_WARNING",
        str(exc),
    )


base_dir = Path.cwd()

audit_directory = (
    base_dir
    / "storage"
    / "audits"
)

if audit_directory.exists():
    for folder in audit_directory.iterdir():
        if not folder.is_dir():
            continue

        metadata_path = (
            folder
            / "metadata.json"
        )

        metadata = {}

        if metadata_path.exists():
            try:
                metadata = json.loads(
                    metadata_path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                metadata = {}

        claim(
            "audit",
            metadata.get(
                "audit_id",
                folder.name,
            ),
            {
                "original_name": metadata.get(
                    "original_name"
                )
            },
        )


journal_directory = (
    base_dir
    / "storage"
    / "journals"
)

if journal_directory.exists():
    for folder in journal_directory.iterdir():
        if not folder.is_dir():
            continue

        metadata_path = (
            folder
            / "metadata.json"
        )

        metadata = {}

        if metadata_path.exists():
            try:
                metadata = json.loads(
                    metadata_path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                metadata = {}

        claim(
            "journal",
            metadata.get(
                "job_id",
                folder.name,
            ),
            {
                "title": metadata.get(
                    "title"
                )
            },
        )


print("WORKSPACE_LEGACY_MIGRATION_COMPLETED")
print(
    "ADMIN_WORKSPACE",
    admin_workspace["workspace_id"],
)