from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
)

from services.auth_service import (
    SESSION_COOKIE,
    require_admin,
    session_user,
)
from services.billing_enforcement_service import (
    check_access,
    enforcement_health,
    finalize_processing_access,
    list_all_reservations,
    list_user_reservations,
    release_processing_access,
    reserve_processing_access,
    service_code_for_operation,
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
            detail=(
                "Silakan login terlebih dahulu."
            ),
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


@router.get(
    "/api/billing/enforcement/health"
)
def billing_enforcement_health() -> dict[str, Any]:
    return enforcement_health()


@router.get(
    "/api/billing/access/check/{operation}"
)
def billing_access_check(
    operation: str,
    request: Request,
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    return check_access(
        user_id=user_identifier(user),
        operation=operation,
    )


@router.post(
    "/api/billing/access/reserve/{operation}"
)
def billing_access_reserve(
    operation: str,
    request: Request,
    request_reference: str = Form(""),
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    service_code = service_code_for_operation(
        operation
    )

    if not service_code:
        raise HTTPException(
            status_code=400,
            detail=(
                "Operasi belum memiliki "
                "pemetaan billing."
            ),
        )

    try:
        reservation = reserve_processing_access(
            user_id=user_identifier(user),
            service_code=service_code,
            operation=operation,
            request_reference=(
                request_reference
                or None
            ),
        )

        return {
            "success": True,
            "reservation": reservation,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=402,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/billing/access/finalize"
)
def billing_access_finalize(
    request: Request,
    reservation_token: str = Form(...),
    processing_reference: str = Form(...),
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    try:
        reservation = finalize_processing_access(
            reservation_token=(
                reservation_token
            ),
            processing_reference=(
                processing_reference
            ),
            user_id=user_identifier(user),
        )

        return {
            "success": True,
            "reservation": reservation,
        }

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/billing/access/release"
)
def billing_access_release(
    request: Request,
    reservation_token: str = Form(...),
    reason: str = Form(
        "processing_failed"
    ),
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    try:
        reservation = release_processing_access(
            reservation_token=(
                reservation_token
            ),
            reason=reason,
            user_id=user_identifier(user),
        )

        return {
            "success": True,
            "reservation": reservation,
        }

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/billing/access/reservations"
)
def billing_access_reservations(
    request: Request,
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
) -> dict[str, Any]:
    user = require_current_user(
        request
    )

    return {
        "reservations": list_user_reservations(
            user_id=user_identifier(user),
            limit=limit,
        )
    }


@router.get(
    "/api/billing/admin/reservations"
)
def billing_admin_reservations(
    limit: int = Query(
        200,
        ge=1,
        le=1000,
    ),
    status: str | None = None,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "reservations": list_all_reservations(
            limit=limit,
            status=status,
        ),
        "requested_by": admin["email"],
    }
