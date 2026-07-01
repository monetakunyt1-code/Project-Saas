from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import FileResponse

from notification_database import (
    delete_notification_record,
    mark_all_notifications_read,
    mark_notification_read,
)
from services.auth_service import (
    SESSION_COOKIE,
    require_admin,
    session_user,
)
from services.notification_service import (
    confirm_email_verification,
    confirm_password_reset,
    create_notification,
    email_status,
    notification_health,
    outbox_items,
    send_password_reset_email,
    send_pending_emails,
    send_verification_email,
    user_notifications,
    user_unread_count,
)


BASE_DIR = Path(__file__).resolve().parent

NOTIFICATION_PAGE = (
    BASE_DIR
    / "templates"
    / "notification_center.html"
)

RESET_PASSWORD_PAGE = (
    BASE_DIR
    / "templates"
    / "reset_password.html"
)

router = APIRouter()


def require_current_user(
    request: Request,
) -> dict[str, Any]:
    user = getattr(
        request.state,
        "saas_user",
        None,
    )

    if not user:
        user = session_user(
            request.cookies.get(
                SESSION_COOKIE
            )
        )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Silakan login terlebih dahulu.",
        )

    return user


def user_identifier(
    user: dict[str, Any],
) -> str:
    value = (
        user.get("user_id")
        or user.get("id")
        or user.get("uuid")
    )

    if value is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Identitas pengguna tidak tersedia."
            ),
        )

    return str(value)


def user_email(
    user: dict[str, Any],
) -> str:
    value = user.get("email")

    if not value:
        raise HTTPException(
            status_code=400,
            detail=(
                "Email akun tidak tersedia."
            ),
        )

    return str(value)


@router.get("/notifications")
def notification_page() -> FileResponse:
    return FileResponse(
        NOTIFICATION_PAGE
    )


@router.get("/reset-password")
def reset_password_page() -> FileResponse:
    return FileResponse(
        RESET_PASSWORD_PAGE
    )


@router.get("/api/notifications/health")
def notifications_health() -> dict[str, Any]:
    return notification_health()


@router.get("/api/notifications")
def notifications_list(
    request: Request,
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    unread_only: bool = False,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    user_id = user_identifier(
        user
    )

    return {
        "notifications": user_notifications(
            user_id=user_id,
            limit=limit,
            unread_only=unread_only,
        ),
        "unread_count": user_unread_count(
            user_id
        ),
    }


@router.get(
    "/api/notifications/unread-count"
)
def notifications_unread_count(
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    return {
        "unread_count": user_unread_count(
            user_identifier(user)
        )
    }


@router.post(
    "/api/notifications/{notification_id}/read"
)
def notification_mark_read(
    notification_id: str,
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    updated = mark_notification_read(
        notification_id=notification_id,
        user_id=user_identifier(user),
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail=(
                "Notifikasi tidak ditemukan."
            ),
        )

    return {
        "success": True,
        "message": (
            "Notifikasi ditandai sudah dibaca."
        ),
    }


@router.post(
    "/api/notifications/read-all"
)
def notifications_mark_all_read(
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    updated = mark_all_notifications_read(
        user_identifier(user)
    )

    return {
        "success": True,
        "updated": updated,
        "message": (
            f"{updated} notifikasi "
            "ditandai sudah dibaca."
        ),
    }


@router.delete(
    "/api/notifications/{notification_id}"
)
def notification_delete(
    notification_id: str,
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    deleted = delete_notification_record(
        notification_id=notification_id,
        user_id=user_identifier(user),
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=(
                "Notifikasi tidak ditemukan."
            ),
        )

    return {
        "success": True,
        "message": (
            "Notifikasi berhasil dihapus."
        ),
    }


@router.post("/api/notifications/test")
def notification_test(
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    notification = create_notification(
        user_id=user_identifier(user),
        title="Notifikasi pengujian",
        message=(
            "Notification Center DocuRapi "
            "berfungsi dengan baik."
        ),
        notification_type="success",
        action_url="/system-health",
    )

    return {
        "success": True,
        "notification": notification,
    }


@router.get(
    "/api/email/verification/status"
)
def verification_status(
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    return email_status(
        user_email(user)
    )


@router.post(
    "/api/email/verification/request"
)
def verification_request(
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    result = send_verification_email(
        user_id=user_identifier(user),
        email=user_email(user),
    )

    if result["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=(
                "Email verifikasi gagal dikirim: "
                + result.get(
                    "error",
                    "unknown error",
                )
            ),
        )

    return {
        "success": True,
        "message": (
            "Email verifikasi berhasil dibuat."
        ),
        "delivery": result,
    }


@router.get(
    "/api/email/verification/confirm"
)
def verification_confirm(
    token: str = Query(
        ...,
        min_length=20,
    ),
) -> dict[str, Any]:
    result = confirm_email_verification(
        token
    )

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"],
        )

    return result


@router.post(
    "/api/email/password-reset/request"
)
def password_reset_request(
    email: str = Form(...),
) -> dict[str, Any]:
    return send_password_reset_email(
        email
    )


@router.post(
    "/api/email/password-reset/confirm"
)
def password_reset_confirm(
    token: str = Form(...),
    new_password: str = Form(
        ...,
        min_length=8,
    ),
) -> dict[str, Any]:
    result = confirm_password_reset(
        raw_token=token,
        new_password=new_password,
    )

    if not result["success"]:
        status_code = (
            501
            if result.get("unsupported")
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=result["message"],
        )

    return result


@router.get(
    "/api/notifications/admin/outbox"
)
def admin_outbox(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
    status: str | None = None,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "emails": outbox_items(
            limit=limit,
            status=status,
        ),
        "requested_by": admin["email"],
    }


@router.post(
    "/api/notifications/admin/send-pending"
)
def admin_send_pending(
    limit: int = Form(50),
    admin=Depends(require_admin),
) -> dict[str, Any]:
    result = send_pending_emails(
        limit=limit
    )

    result["requested_by"] = (
        admin["email"]
    )

    return result
