from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

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
    admin_users,
    list_plans,
    set_active,
    set_plan,
    usage_snapshot,
)
from services.auth_service import (
    SESSION_COOKIE,
    SESSION_DAYS,
    authenticate,
    issue_session,
    logout,
    register,
    require_admin,
    require_user,
)


BASE_DIR = Path(__file__).resolve().parent
PORTAL_FILE = (
    BASE_DIR
    / "templates"
    / "saas_portal.html"
)

router = APIRouter()


def secure_cookie() -> bool:
    return os.getenv(
        "DOCURAPI_COOKIE_SECURE",
        "0",
    ) == "1"


def attach_cookie(
    response: JSONResponse,
    token: str,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
        path="/",
    )


@router.get("/login")
@router.get("/register")
@router.get("/pricing")
@router.get("/account")
@router.get("/admin")
def portal_page() -> FileResponse:
    if not PORTAL_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail="Halaman portal belum tersedia.",
        )

    return FileResponse(PORTAL_FILE)


@router.post("/api/auth/register")
def api_register(
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
) -> JSONResponse:
    try:
        user = register(
            email,
            display_name,
            password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    token = issue_session(
        user["user_id"]
    )

    response = JSONResponse(
        {
            "success": True,
            "message": "Akun berhasil dibuat.",
            "user": user,
        }
    )

    attach_cookie(
        response,
        token,
    )

    return response


@router.post("/api/auth/login")
def api_login(
    email: str = Form(...),
    password: str = Form(...),
) -> JSONResponse:
    try:
        user = authenticate(
            email,
            password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    token = issue_session(
        user["user_id"]
    )

    response = JSONResponse(
        {
            "success": True,
            "message": "Login berhasil.",
            "user": user,
        }
    )

    attach_cookie(
        response,
        token,
    )

    return response


@router.post("/api/auth/logout")
def api_logout(
    request: Request,
) -> JSONResponse:
    logout(
        request.cookies.get(
            SESSION_COOKIE
        )
    )

    response = JSONResponse(
        {
            "success": True,
            "message": "Logout berhasil.",
        }
    )

    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
    )

    return response


@router.get("/api/auth/me")
def api_me(
    user=Depends(require_user),
) -> dict:
    return {
        "user": user,
        "usage": usage_snapshot(
            user["user_id"]
        ),
    }


@router.get("/api/account/usage")
def api_usage(
    user=Depends(require_user),
) -> dict:
    return {
        "usage": usage_snapshot(
            user["user_id"]
        )
    }


@router.get("/api/plans")
def api_plans() -> dict:
    return {
        "plans": list_plans(),
        "payment_mode": "simulation",
    }


@router.post("/api/billing/checkout")
def api_checkout(
    plan_code: str = Form(...),
    user=Depends(require_user),
) -> dict:
    try:
        usage = set_plan(
            user["user_id"],
            plan_code,
            payment_id=uuid4().hex,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Simulasi pembayaran berhasil. "
            "Paket telah diperbarui."
        ),
        "usage": usage,
    }


@router.get("/api/admin/users")
def api_admin_users(
    admin=Depends(require_admin),
) -> dict:
    return {
        "users": admin_users(),
        "requested_by": admin["email"],
    }


@router.get("/api/admin/payments")
def api_admin_payments(
    admin=Depends(require_admin),
) -> dict:
    return {
        "payments": admin_payments(),
        "requested_by": admin["email"],
    }


@router.post(
    "/api/admin/users/{user_id}/plan"
)
def api_admin_plan(
    user_id: str,
    plan_code: str = Form(...),
    admin=Depends(require_admin),
) -> dict:
    try:
        usage = set_plan(
            user_id,
            plan_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "usage": usage,
        "requested_by": admin["email"],
    }


@router.post(
    "/api/admin/users/{user_id}/toggle"
)
def api_admin_toggle(
    user_id: str,
    active: bool = Form(...),
    admin=Depends(require_admin),
) -> dict:
    if user_id == admin["user_id"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Admin tidak dapat menonaktifkan "
                "akunnya sendiri."
            ),
        )

    set_active(
        user_id,
        active,
    )

    return {
        "success": True,
        "user_id": user_id,
        "is_active": active,
    }