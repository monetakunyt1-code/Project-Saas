from __future__ import annotations

import hashlib
import os
import secrets
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from fastapi import (
    HTTPException,
    Request,
)

from workspace_database import (
    create_workspace,
    ensure_personal_workspace,
    get_membership,
    get_workspace,
    list_user_workspaces,
    save_invite,
)


WORKSPACE_COOKIE = "docurapi_workspace"

ROLE_LEVEL = {
    "viewer": 1,
    "member": 2,
    "admin": 3,
    "owner": 4,
}


def secure_cookie() -> bool:
    return os.getenv(
        "DOCURAPI_COOKIE_SECURE",
        "0",
    ) == "1"


def ensure_workspace_for_user(
    user: dict[str, Any],
) -> dict[str, Any]:
    return ensure_personal_workspace(
        user_id=user["user_id"],
        display_name=user["display_name"],
    )


def resolve_workspace(
    user: dict[str, Any],
    requested_workspace_id: str | None = None,
) -> dict[str, Any]:
    personal = ensure_workspace_for_user(
        user
    )

    if requested_workspace_id:
        membership = get_membership(
            requested_workspace_id,
            user["user_id"],
        )

        if membership:
            workspace = get_workspace(
                requested_workspace_id
            )

            if workspace:
                workspace["role"] = membership[
                    "role"
                ]

                return workspace

    personal_membership = get_membership(
        personal["workspace_id"],
        user["user_id"],
    )

    personal["role"] = (
        personal_membership["role"]
        if personal_membership
        else "owner"
    )

    return personal


def active_workspace_from_request(
    request: Request,
    user: dict[str, Any],
) -> dict[str, Any]:
    requested = request.cookies.get(
        WORKSPACE_COOKIE
    )

    return resolve_workspace(
        user,
        requested,
    )


def require_workspace_role(
    workspace_id: str,
    user_id: str,
    minimum_role: str,
) -> dict[str, Any]:
    membership = get_membership(
        workspace_id,
        user_id,
    )

    if not membership:
        raise HTTPException(
            status_code=404,
            detail="Workspace tidak ditemukan.",
        )

    current_level = ROLE_LEVEL.get(
        membership["role"],
        0,
    )

    minimum_level = ROLE_LEVEL.get(
        minimum_role,
        99,
    )

    if current_level < minimum_level:
        raise HTTPException(
            status_code=403,
            detail=(
                "Anda tidak memiliki izin "
                "untuk tindakan ini."
            ),
        )

    return membership


def create_workspace_invite(
    workspace_id: str,
    created_by: str,
    role: str,
    expires_hours: int,
    max_uses: int,
) -> str:
    raw_token = secrets.token_urlsafe(
        32
    )

    invite_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    safe_hours = max(
        1,
        min(
            int(expires_hours),
            168,
        ),
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=safe_hours)
    ).isoformat()

    save_invite(
        invite_hash=invite_hash,
        workspace_id=workspace_id,
        created_by=created_by,
        role=role,
        expires_at=expires_at,
        max_uses=max_uses,
    )

    return raw_token


def available_workspaces(
    user: dict[str, Any],
) -> list[dict[str, Any]]:
    ensure_workspace_for_user(
        user
    )

    return list_user_workspaces(
        user["user_id"]
    )