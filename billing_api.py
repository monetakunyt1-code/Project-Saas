from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
)

from services.auth_service import (
    SESSION_COOKIE,
    require_admin,
    session_user,
)
from services.billing_service import (
    billing_health,
    cancel_order,
    create_order,
    create_quote,
    get_catalog,
    get_order,
    list_all_orders,
    list_entitlements,
    list_user_orders,
    process_webhook,
    redeem_credits,
    refund_order,
    simulate_payment,
    update_product,
    wallet_summary,
)


BASE_DIR = Path(
    __file__
).resolve().parent

BILLING_PAGE = (
    BASE_DIR
    / "templates"
    / "billing_center.html"
)

ADMIN_BILLING_PAGE = (
    BASE_DIR
    / "templates"
    / "admin_billing.html"
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
) -> str | None:
    value = user.get("email")

    return (
        str(value)
        if value
        else None
    )


def order_for_user(
    order_id: str,
    user_id: str,
) -> dict[str, Any]:
    order = get_order(
        order_id
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Pesanan tidak ditemukan.",
        )

    if str(order["user_id"]) != str(user_id):
        raise HTTPException(
            status_code=403,
            detail=(
                "Pesanan bukan milik pengguna ini."
            ),
        )

    return order


@router.get("/billing")
def billing_page() -> FileResponse:
    return FileResponse(
        BILLING_PAGE
    )


@router.get("/billing/history")
def billing_history_page() -> FileResponse:
    return FileResponse(
        BILLING_PAGE
    )


@router.get("/admin/billing")
def admin_billing_page() -> FileResponse:
    return FileResponse(
        ADMIN_BILLING_PAGE
    )


@router.get("/api/billing/health")
def billing_health_endpoint() -> dict[str, Any]:
    return billing_health()


@router.get("/api/billing/catalog")
def billing_catalog() -> dict[str, Any]:
    return {
        "products": get_catalog(),
        "currency": "IDR",
        "billing_model": "pay_per_use",
        "subscription_enabled": False,
    }


@router.get("/api/billing/quote")
def billing_quote(
    product_code: str = Query(...),
    quantity: int = Query(
        1,
        ge=1,
        le=100,
    ),
) -> dict[str, Any]:
    try:
        return create_quote(
            product_code=product_code,
            quantity=quantity,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post("/api/billing/orders")
def billing_create_order(
    request: Request,
    product_code: str = Form(...),
    quantity: int = Form(
        1,
        ge=1,
        le=100,
    ),
    idempotency_key: str = Form(""),
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        order = create_order(
            user_id=user_identifier(
                user
            ),
            user_email=user_email(
                user
            ),
            product_code=product_code,
            quantity=quantity,
            idempotency_key=(
                idempotency_key
                or uuid4().hex
            ),
            metadata={
                "source": "billing_center"
            },
        )

        return {
            "success": True,
            "order": order,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/api/billing/orders")
def billing_orders(
    request: Request,
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
) -> dict[str, Any]:
    user = current_user(
        request
    )

    return {
        "orders": list_user_orders(
            user_identifier(user),
            limit=limit,
        )
    }


@router.get(
    "/api/billing/orders/{order_id}"
)
def billing_order_detail(
    order_id: str,
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    return order_for_user(
        order_id,
        user_identifier(user),
    )


@router.post(
    "/api/billing/orders/{order_id}/simulate-pay"
)
def billing_simulate_payment(
    order_id: str,
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        order = simulate_payment(
            order_id=order_id,
            user_id=user_identifier(
                user
            ),
        )

        return {
            "success": True,
            "message": (
                "Pembayaran simulasi berhasil."
            ),
            "order": order,
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
    "/api/billing/orders/{order_id}/cancel"
)
def billing_cancel_order(
    order_id: str,
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        order = cancel_order(
            order_id=order_id,
            user_id=user_identifier(
                user
            ),
        )

        return {
            "success": True,
            "order": order,
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
    "/api/billing/orders/{order_id}/invoice"
)
def billing_invoice(
    order_id: str,
    request: Request,
) -> HTMLResponse:
    user = current_user(
        request
    )

    order = order_for_user(
        order_id,
        user_identifier(user),
    )

    item_rows = []

    for item in order["items"]:
        item_rows.append(
            "<tr>"
            f"<td>{html.escape(item['product_name'])}</td>"
            f"<td>{int(item['quantity'])}</td>"
            f"<td>Rp{int(item['unit_price']):,}</td>"
            f"<td>Rp{int(item['line_total']):,}</td>"
            "</tr>"
        )

    invoice_html = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <title>{html.escape(order['invoice_number'])}</title>
        <style>
            body {{
                max-width: 850px;
                margin: 40px auto;
                color: #172326;
                font-family: Arial, sans-serif;
            }}
            header {{
                display: flex;
                justify-content: space-between;
                gap: 20px;
                border-bottom: 2px solid #0f6b5d;
            }}
            table {{
                width: 100%;
                margin-top: 30px;
                border-collapse: collapse;
            }}
            th, td {{
                padding: 12px;
                border-bottom: 1px solid #dce7e4;
                text-align: left;
            }}
            .total {{
                margin-top: 24px;
                text-align: right;
                font-size: 22px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <header>
            <div>
                <h1>DocuRapi</h1>
                <p>Invoice Pay-per-Use</p>
            </div>
            <div>
                <p><strong>{html.escape(order['invoice_number'])}</strong></p>
                <p>Status: {html.escape(order['status'].upper())}</p>
            </div>
        </header>

        <p>Nomor pesanan: {html.escape(order['order_number'])}</p>
        <p>Email: {html.escape(order.get('user_email') or '-')}</p>
        <p>Dibuat: {html.escape(order['created_at'])}</p>

        <table>
            <thead>
                <tr>
                    <th>Layanan</th>
                    <th>Jumlah</th>
                    <th>Harga</th>
                    <th>Total</th>
                </tr>
            </thead>
            <tbody>
                {''.join(item_rows)}
            </tbody>
        </table>

        <div class="total">
            Total: {html.escape(order['formatted_total'])}
        </div>
    </body>
    </html>
    """

    invoice_html = invoice_html.replace(
        ",",
        ".",
    )

    return HTMLResponse(
        invoice_html
    )


@router.get("/api/billing/wallet")
def billing_wallet(
    request: Request,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    return wallet_summary(
        user_identifier(user)
    )


@router.get(
    "/api/billing/entitlements"
)
def billing_entitlements(
    request: Request,
    status: str | None = None,
) -> dict[str, Any]:
    user = current_user(
        request
    )

    return {
        "entitlements": list_entitlements(
            user_identifier(user),
            status=status,
        )
    }


@router.post(
    "/api/billing/credits/redeem"
)
def billing_redeem_credits(
    request: Request,
    product_code: str = Form(...),
    quantity: int = Form(
        1,
        ge=1,
        le=100,
    ),
) -> dict[str, Any]:
    user = current_user(
        request
    )

    try:
        return redeem_credits(
            user_id=user_identifier(
                user
            ),
            product_code=product_code,
            quantity=quantity,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/billing/webhooks/simulated"
)
async def billing_simulated_webhook(
    request: Request,
    x_docurapi_signature: str = Header(
        "",
        alias="X-DocuRapi-Signature",
    ),
) -> dict[str, Any]:
    payload = await request.json()

    event_id = str(
        payload.get("event_id", "")
    )

    order_id = str(
        payload.get("order_id", "")
    )

    event_type = str(
        payload.get("event_type", "")
    )

    if (
        not event_id
        or not order_id
        or not event_type
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "event_id, order_id, dan "
                "event_type wajib diisi."
            ),
        )

    try:
        return process_webhook(
            event_id=event_id,
            order_id=order_id,
            event_type=event_type,
            signature=x_docurapi_signature,
            payload=payload,
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/billing/admin/catalog"
)
def billing_admin_catalog(
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "products": get_catalog(
            include_inactive=True
        ),
        "requested_by": admin["email"],
    }


@router.post(
    "/api/billing/admin/catalog/{product_code}"
)
def billing_admin_update_product(
    product_code: str,
    name: str = Form(...),
    description: str = Form(...),
    price_idr: int = Form(
        ...,
        ge=0,
    ),
    credit_cost: int = Form(
        0,
        ge=0,
    ),
    active: bool = Form(True),
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        product = update_product(
            product_code=product_code,
            name=name,
            description=description,
            price_idr=price_idr,
            credit_cost=credit_cost,
            active=active,
        )

        return {
            "success": True,
            "product": product,
            "updated_by": admin["email"],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/billing/admin/orders"
)
def billing_admin_orders(
    limit: int = Query(
        200,
        ge=1,
        le=1000,
    ),
    status: str | None = None,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "orders": list_all_orders(
            limit=limit,
            status=status,
        ),
        "requested_by": admin["email"],
    }


@router.post(
    "/api/billing/admin/orders/{order_id}/refund"
)
def billing_admin_refund(
    order_id: str,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        order = refund_order(
            order_id
        )

        return {
            "success": True,
            "order": order,
            "refunded_by": admin["email"],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
