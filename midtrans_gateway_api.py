
from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)

from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)
from services.midtrans_gateway_service import (
    client_key,
    create_snap_checkout,
    gateway_health,
    handle_webhook,
    midtrans_environment,
    payment_mode,
    snap_js_url,
    synchronize_order,
)


router = APIRouter()


def current_user(
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


def user_id(
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
    "/api/payments/midtrans/health"
)
def midtrans_health() -> dict[str, Any]:
    return gateway_health()


@router.get(
    "/api/payments/midtrans/config"
)
def midtrans_frontend_config() -> dict[str, Any]:
    health = gateway_health()

    return {
        "provider": "midtrans",
        "configured": (
            health["configured"]
        ),
        "payment_mode": payment_mode(),
        "environment": (
            midtrans_environment()
        ),
        "client_key": (
            client_key()
            if health["configured"]
            else ""
        ),
        "snap_js_url": snap_js_url(),
    }


@router.post(
    "/api/payments/midtrans/checkout/{order_id}"
)
def midtrans_checkout(
    order_id: str,
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        return create_snap_checkout(
            order_id,
            user_id(user),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except (
        ValueError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/payments/midtrans/sync/{order_id}"
)
def midtrans_sync(
    order_id: str,
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        return synchronize_order(
            order_id,
            user_id(user),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except (
        ValueError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/payments/midtrans/webhook"
)
async def midtrans_webhook(
    request: Request,
) -> dict[str, Any]:
    payload = await request.json()

    try:
        result = handle_webhook(
            payload
        )

        return {
            "status": "OK",
            "result": result,
        }

    except PermissionError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    except (
        ValueError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
