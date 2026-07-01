from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from saas_database import connect


WORKSPACE_ROLES = {
    "owner",
    "admin",
    "member",
    "viewer",
}


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def slugify(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "-",
        value.lower().strip(),
    ).strip("-")

    return normalized or "workspace"


def row_dict(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    return dict(row) if row else None


def initialize_workspace_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                owner_user_id TEXT NOT NULL,
                workspace_type TEXT NOT NULL DEFAULT 'team',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (owner_user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, user_id),
                FOREIGN KEY (workspace_id)
                    REFERENCES workspaces(workspace_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workspace_invites (
                invite_hash TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                created_by TEXT NOT NULL,
                role TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 1,
                used_count INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id)
                    REFERENCES workspaces(workspace_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (created_by)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS resource_ownership (
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (resource_type, resource_id),
                FOREIGN KEY (workspace_id)
                    REFERENCES workspaces(workspace_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (owner_user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS
                idx_workspace_members_user
            ON workspace_members(user_id);

            CREATE INDEX IF NOT EXISTS
                idx_resource_workspace
            ON resource_ownership(
                workspace_id,
                resource_type
            );

            CREATE INDEX IF NOT EXISTS
                idx_workspace_invites_workspace
            ON workspace_invites(workspace_id);
            """
        )

        connection.commit()


def unique_slug(
    connection: sqlite3.Connection,
    name: str,
) -> str:
    base_slug = slugify(name)
    candidate = base_slug
    counter = 2

    while connection.execute(
        """
        SELECT 1
        FROM workspaces
        WHERE slug = ?
        """,
        (candidate,),
    ).fetchone():
        candidate = f"{base_slug}-{counter}"
        counter += 1

    return candidate


def create_workspace(
    name: str,
    owner_user_id: str,
    workspace_type: str = "team",
) -> dict[str, Any]:
    clean_name = name.strip()

    if len(clean_name) < 2:
        raise ValueError(
            "Nama workspace minimal 2 karakter."
        )

    if len(clean_name) > 100:
        raise ValueError(
            "Nama workspace maksimal 100 karakter."
        )

    workspace_id = uuid4().hex
    timestamp = utc_now()

    with connect() as connection:
        slug = unique_slug(
            connection,
            clean_name,
        )

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                name,
                slug,
                owner_user_id,
                workspace_type,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                clean_name,
                slug,
                owner_user_id,
                workspace_type,
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO workspace_members (
                workspace_id,
                user_id,
                role,
                joined_at
            )
            VALUES (?, ?, 'owner', ?)
            """,
            (
                workspace_id,
                owner_user_id,
                timestamp,
            ),
        )

        connection.commit()

    result = get_workspace(
        workspace_id
    )

    if not result:
        raise RuntimeError(
            "Workspace gagal dibuat."
        )

    return result


def get_workspace(
    workspace_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                w.*,
                u.display_name AS owner_name,
                u.email AS owner_email
            FROM workspaces w
            JOIN users u
                ON u.user_id = w.owner_user_id
            WHERE w.workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

    return row_dict(row)


def ensure_personal_workspace(
    user_id: str,
    display_name: str,
) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT w.*
            FROM workspaces w
            JOIN workspace_members m
                ON m.workspace_id = w.workspace_id
            WHERE m.user_id = ?
              AND w.workspace_type = 'personal'
            ORDER BY w.created_at ASC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    if row:
        return dict(row)

    return create_workspace(
        name=f"Workspace {display_name}",
        owner_user_id=user_id,
        workspace_type="personal",
    )


def list_user_workspaces(
    user_id: str,
) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                w.*,
                m.role,
                (
                    SELECT COUNT(*)
                    FROM workspace_members members
                    WHERE members.workspace_id =
                        w.workspace_id
                ) AS member_count
            FROM workspaces w
            JOIN workspace_members m
                ON m.workspace_id = w.workspace_id
            WHERE m.user_id = ?
            ORDER BY
                CASE
                    WHEN w.workspace_type = 'personal'
                    THEN 0
                    ELSE 1
                END,
                w.name ASC
            """,
            (user_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_membership(
    workspace_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT
                m.*,
                u.email,
                u.display_name,
                u.is_active
            FROM workspace_members m
            JOIN users u
                ON u.user_id = m.user_id
            WHERE m.workspace_id = ?
              AND m.user_id = ?
            """,
            (
                workspace_id,
                user_id,
            ),
        ).fetchone()

    return row_dict(row)


def list_workspace_members(
    workspace_id: str,
) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                m.user_id,
                m.role,
                m.joined_at,
                u.email,
                u.display_name,
                u.is_active
            FROM workspace_members m
            JOIN users u
                ON u.user_id = m.user_id
            WHERE m.workspace_id = ?
            ORDER BY
                CASE m.role
                    WHEN 'owner' THEN 1
                    WHEN 'admin' THEN 2
                    WHEN 'member' THEN 3
                    ELSE 4
                END,
                u.display_name ASC
            """,
            (workspace_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def save_invite(
    invite_hash: str,
    workspace_id: str,
    created_by: str,
    role: str,
    expires_at: str,
    max_uses: int,
) -> None:
    if role not in {
        "admin",
        "member",
        "viewer",
    }:
        raise ValueError(
            "Peran undangan tidak valid."
        )

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO workspace_invites (
                invite_hash,
                workspace_id,
                created_by,
                role,
                expires_at,
                max_uses,
                used_count,
                revoked,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (
                invite_hash,
                workspace_id,
                created_by,
                role,
                expires_at,
                max(
                    1,
                    min(
                        int(max_uses),
                        100,
                    ),
                ),
                utc_now(),
            ),
        )

        connection.commit()


def join_with_invite(
    raw_token: str,
    user_id: str,
) -> dict[str, Any]:
    invite_hash = hashlib.sha256(
        raw_token.strip().encode(
            "utf-8"
        )
    ).hexdigest()

    now = datetime.now(
        timezone.utc
    )

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM workspace_invites
            WHERE invite_hash = ?
            """,
            (invite_hash,),
        ).fetchone()

        if not row:
            raise ValueError(
                "Kode undangan tidak valid."
            )

        invite = dict(row)

        try:
            expires_at = datetime.fromisoformat(
                invite["expires_at"]
            )
        except ValueError as exc:
            raise ValueError(
                "Data undangan tidak valid."
            ) from exc

        if bool(invite["revoked"]):
            raise ValueError(
                "Undangan telah dinonaktifkan."
            )

        if expires_at <= now:
            raise ValueError(
                "Undangan telah kedaluwarsa."
            )

        if (
            int(invite["used_count"])
            >= int(invite["max_uses"])
        ):
            raise ValueError(
                "Batas penggunaan undangan telah tercapai."
            )

        connection.execute(
            """
            INSERT INTO workspace_members (
                workspace_id,
                user_id,
                role,
                joined_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(workspace_id, user_id)
            DO UPDATE SET
                role = excluded.role
            """,
            (
                invite["workspace_id"],
                user_id,
                invite["role"],
                utc_now(),
            ),
        )

        connection.execute(
            """
            UPDATE workspace_invites
            SET used_count = used_count + 1
            WHERE invite_hash = ?
            """,
            (invite_hash,),
        )

        connection.commit()

    workspace = get_workspace(
        invite["workspace_id"]
    )

    if not workspace:
        raise RuntimeError(
            "Workspace undangan tidak ditemukan."
        )

    return workspace


def update_member_role(
    workspace_id: str,
    user_id: str,
    role: str,
) -> None:
    if role not in {
        "admin",
        "member",
        "viewer",
    }:
        raise ValueError(
            "Peran anggota tidak valid."
        )

    with connect() as connection:
        membership = connection.execute(
            """
            SELECT role
            FROM workspace_members
            WHERE workspace_id = ?
              AND user_id = ?
            """,
            (
                workspace_id,
                user_id,
            ),
        ).fetchone()

        if not membership:
            raise ValueError(
                "Anggota tidak ditemukan."
            )

        if membership["role"] == "owner":
            raise ValueError(
                "Peran owner tidak dapat diubah."
            )

        connection.execute(
            """
            UPDATE workspace_members
            SET role = ?
            WHERE workspace_id = ?
              AND user_id = ?
            """,
            (
                role,
                workspace_id,
                user_id,
            ),
        )

        connection.commit()


def remove_member(
    workspace_id: str,
    user_id: str,
) -> None:
    with connect() as connection:
        membership = connection.execute(
            """
            SELECT role
            FROM workspace_members
            WHERE workspace_id = ?
              AND user_id = ?
            """,
            (
                workspace_id,
                user_id,
            ),
        ).fetchone()

        if not membership:
            raise ValueError(
                "Anggota tidak ditemukan."
            )

        if membership["role"] == "owner":
            raise ValueError(
                "Owner tidak dapat dikeluarkan."
            )

        connection.execute(
            """
            DELETE FROM workspace_members
            WHERE workspace_id = ?
              AND user_id = ?
            """,
            (
                workspace_id,
                user_id,
            ),
        )

        connection.commit()


def claim_resource(
    resource_type: str,
    resource_id: str,
    workspace_id: str,
    owner_user_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    timestamp = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO resource_ownership (
                resource_type,
                resource_id,
                workspace_id,
                owner_user_id,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(resource_type, resource_id)
            DO UPDATE SET
                workspace_id =
                    excluded.workspace_id,
                owner_user_id =
                    excluded.owner_user_id,
                metadata_json =
                    excluded.metadata_json,
                updated_at =
                    excluded.updated_at
            """,
            (
                resource_type,
                str(resource_id),
                workspace_id,
                owner_user_id,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
                timestamp,
                timestamp,
            ),
        )

        connection.commit()


def get_resource_owner(
    resource_type: str,
    resource_id: str,
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM resource_ownership
            WHERE resource_type = ?
              AND resource_id = ?
            """,
            (
                resource_type,
                str(resource_id),
            ),
        ).fetchone()

    if not row:
        return None

    result = dict(row)

    try:
        result["metadata"] = json.loads(
            result.pop("metadata_json")
        )
    except json.JSONDecodeError:
        result["metadata"] = {}

    return result


def remove_resource_owner(
    resource_type: str,
    resource_id: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            DELETE FROM resource_ownership
            WHERE resource_type = ?
              AND resource_id = ?
            """,
            (
                resource_type,
                str(resource_id),
            ),
        )

        connection.commit()


def list_resource_ids(
    workspace_id: str,
    resource_type: str,
) -> list[str]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT resource_id
            FROM resource_ownership
            WHERE workspace_id = ?
              AND resource_type = ?
            """,
            (
                workspace_id,
                resource_type,
            ),
        ).fetchall()

    return [
        str(row["resource_id"])
        for row in rows
    ]


def workspace_resource_counts(
    workspace_id: str,
) -> dict[str, int]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                resource_type,
                COUNT(*) AS total
            FROM resource_ownership
            WHERE workspace_id = ?
            GROUP BY resource_type
            """,
            (workspace_id,),
        ).fetchall()

    return {
        str(row["resource_type"]): int(
            row["total"]
        )
        for row in rows
    }


initialize_workspace_database()