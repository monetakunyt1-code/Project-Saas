from __future__ import annotations

import hashlib
import os
import secrets
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
)

from saas_database import (
    admin_payments,
    connect as saas_connect,
    get_user,
    get_user_by_email,
    usage_snapshot,
)
from security_database import (
    consume_reset_token,
    get_privacy_settings,
    list_audit_events,
    remove_user_security_data,
    save_privacy_settings,
    store_reset_token,
)
from services.auth_service import (
    password_hash,
    require_admin,
    require_user,
    verify_password,
)
from services.retention_service import (
    apply_retention,
)
from services.security_service import (
    CSRF_COOKIE,
    request_csrf_token,
)


BASE_DIR = Path(__file__).resolve().parent

SECURITY_PAGE = (
    BASE_DIR
    / "templates"
    / "security_center.html"
)

router = APIRouter()


def delete_user_sessions(
    user_id: str,
) -> None:
    with saas_connect() as connection:
        connection.execute(
            """
            DELETE FROM sessions
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        connection.commit()


def update_user_password(
    user_id: str,
    new_password: str,
) -> None:
    digest, salt = password_hash(
        new_password
    )

    with saas_connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET
                password_hash = ?,
                password_salt = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                digest,
                salt,
                datetime.now(
                    timezone.utc
                ).isoformat(),
                user_id,
            ),
        )

        connection.execute(
            """
            DELETE FROM sessions
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        )

        connection.commit()


@router.get("/security-center")
def security_center_page() -> FileResponse:
    if not SECURITY_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Halaman Security Center "
                "belum tersedia."
            ),
        )

    return FileResponse(
        SECURITY_PAGE
    )


@router.get("/api/security/csrf")
def security_csrf(
    request: Request,
) -> dict:
    return {
        "csrf_token": request_csrf_token(
            request
        ),
        "cookie_name": CSRF_COOKIE,
    }


@router.post("/api/security/password/change")
def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    user=Depends(require_user),
) -> dict:
    record = get_user(
        user["user_id"]
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    if not verify_password(
        current_password,
        record["password_hash"],
        record["password_salt"],
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Kata sandi saat ini salah."
            ),
        )

    try:
        update_user_password(
            user["user_id"],
            new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Kata sandi berhasil diubah. "
            "Silakan login kembali."
        ),
    }


@router.post(
    "/api/security/password/reset/request"
)
def request_password_reset(
    email: str = Form(...),
) -> dict:
    normalized_email = (
        email.strip().lower()
    )

    user = get_user_by_email(
        normalized_email
    )

    response = {
        "success": True,
        "message": (
            "Apabila email terdaftar, "
            "instruksi reset telah dibuat."
        ),
        "delivery_mode": (
            "local-development"
        ),
    }

    if not user:
        return response

    raw_token = secrets.token_urlsafe(
        40
    )

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=30)
    ).isoformat()

    store_reset_token(
        token_hash=token_hash,
        user_id=user["user_id"],
        expires_at=expires_at,
    )

    if os.getenv(
        "DOCURAPI_DEV_MODE",
        "1",
    ) == "1":
        response[
            "development_reset_token"
        ] = raw_token

    return response


@router.post(
    "/api/security/password/reset/confirm"
)
def confirm_password_reset(
    token: str = Form(...),
    new_password: str = Form(...),
) -> dict:
    token_hash = hashlib.sha256(
        token.strip().encode("utf-8")
    ).hexdigest()

    user_id = consume_reset_token(
        token_hash
    )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Token reset tidak valid "
                "atau sudah kedaluwarsa."
            ),
        )

    try:
        update_user_password(
            user_id,
            new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Kata sandi berhasil direset."
        ),
    }


@router.get("/api/security/privacy")
def privacy_get(
    user=Depends(require_user),
) -> dict:
    return {
        "settings": get_privacy_settings(
            user["user_id"]
        )
    }


@router.post("/api/security/privacy")
def privacy_update(
    retention_days: int = Form(...),
    analytics_enabled: bool = Form(False),
    user=Depends(require_user),
) -> dict:
    settings = save_privacy_settings(
        user_id=user["user_id"],
        retention_days=retention_days,
        analytics_enabled=analytics_enabled,
    )

    return {
        "success": True,
        "message": (
            "Pengaturan privasi disimpan."
        ),
        "settings": settings,
    }


@router.get("/api/security/account/export")
def export_account_data(
    user=Depends(require_user),
) -> JSONResponse:
    record = get_user(
        user["user_id"]
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    safe_user = {
        "user_id": record["user_id"],
        "email": record["email"],
        "display_name": (
            record["display_name"]
        ),
        "role": record["role"],
        "is_active": bool(
            record["is_active"]
        ),
        "created_at": (
            record["created_at"]
        ),
    }

    payments = [
        item
        for item in admin_payments()
        if item["user_id"] == user["user_id"]
    ]

    return JSONResponse(
        content={
            "exported_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "user": safe_user,
            "usage": usage_snapshot(
                user["user_id"]
            ),
            "privacy": get_privacy_settings(
                user["user_id"]
            ),
            "payments": payments,
            "audit_events": list_audit_events(
                limit=500,
                user_id=user["user_id"],
            ),
        },
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="docurapi_account_export.json"'
            )
        },
    )


@router.post("/api/security/account/delete")
def delete_account(
    password: str = Form(...),
    confirmation: str = Form(...),
    user=Depends(require_user),
) -> dict:
    if user["role"] == "admin":
        raise HTTPException(
            status_code=400,
            detail=(
                "Akun administrator tidak dapat "
                "dihapus melalui halaman ini."
            ),
        )

    if confirmation.strip().upper() != "HAPUS":
        raise HTTPException(
            status_code=400,
            detail=(
                "Ketik HAPUS untuk mengonfirmasi."
            ),
        )

    record = get_user(
        user["user_id"]
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Pengguna tidak ditemukan.",
        )

    if not verify_password(
        password,
        record["password_hash"],
        record["password_salt"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Kata sandi salah.",
        )

    remove_user_security_data(
        user["user_id"]
    )

    with saas_connect() as connection:
        connection.execute(
            """
            DELETE FROM users
            WHERE user_id = ?
            """,
            (
                user["user_id"],
            ),
        )

        connection.commit()

    return {
        "success": True,
        "message": (
            "Akun berhasil dihapus."
        ),
    }


@router.get("/api/security/admin/audit-events")
def admin_audit_events(
    limit: int = 200,
    admin=Depends(require_admin),
) -> dict:
    return {
        "events": list_audit_events(
            limit=limit
        ),
        "requested_by": admin["email"],
    }


@router.get("/api/security/admin/retention/preview")
def retention_preview(
    retention_days: int = 30,
    admin=Depends(require_admin),
) -> dict:
    result = apply_retention(
        retention_days=retention_days,
        dry_run=True,
    )

    return {
        **result,
        "requested_by": admin["email"],
    }


@router.post("/api/security/admin/retention/apply")
def retention_apply(
    retention_days: int = Form(30),
    admin=Depends(require_admin),
) -> dict:
    result = apply_retention(
        retention_days=retention_days,
        dry_run=False,
    )

    return {
        **result,
        "requested_by": admin["email"],
    }


@router.get("/api/security/health")
def security_health() -> dict:
    return {
        "status": "ok",
        "csrf_protection": True,
        "rate_limiting": True,
        "security_headers": True,
        "audit_logging": True,
    }