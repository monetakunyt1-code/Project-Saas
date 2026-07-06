from __future__ import annotations

from fastapi import Header, HTTPException, Query


def get_admin_secret(
    secret: str | None = Query(None),
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> str:
    resolved_secret = x_admin_secret or secret

    if not resolved_secret:
        raise HTTPException(
            status_code=403,
            detail="Secret admin wajib dikirim melalui query secret atau header X-Admin-Secret.",
        )

    return resolved_secret


def get_optional_admin_secret(
    secret: str | None = Query(None),
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> str | None:
    return x_admin_secret or secret
