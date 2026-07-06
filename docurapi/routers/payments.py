from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, UploadFile

from docurapi.schemas.common import (
    ManualPaymentConfirmResponse,
    PaymentCheckoutResponse,
    PaymentStatusResponse,
    PaymentSuccessResponse,
)
from docurapi.services.invoice_page_service import (
    build_invoice_payload,
    build_receipt_payload,
    render_invoice_html,
    render_receipt_html,
)
from docurapi.services.payment_service import (
    confirm_manual_payment,
    create_checkout,
    get_payment_status,
    refresh_invoice,
    simulate_paid,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])




@router.get("/{job_id}/invoice")
def invoice_page(job_id: str, token: str = Query(...), format: str = Query("html")):
    payload = build_invoice_payload(job_id=job_id, token=token)

    if format.lower() == "json":
        return payload

    return render_invoice_html(payload)


@router.get("/{job_id}/receipt")
def receipt_page(job_id: str, token: str = Query(...), format: str = Query("html")):
    payload = build_receipt_payload(job_id=job_id, token=token)

    if format.lower() == "json":
        return payload

    return render_receipt_html(payload)

@router.get("/{job_id}/checkout", response_model=PaymentCheckoutResponse)
def checkout(job_id: str, token: str = Query(...)):
    return create_checkout(job_id=job_id, token=token)


@router.post("/{job_id}/refresh-invoice", response_model=PaymentCheckoutResponse)
def refresh_invoice_route(job_id: str, token: str = Query(...)):
    return refresh_invoice(job_id=job_id, token=token)


@router.get("/{job_id}/status", response_model=PaymentStatusResponse)
def payment_status(job_id: str, token: str = Query(...)):
    return get_payment_status(job_id=job_id, token=token)


@router.post("/{job_id}/confirm-manual", response_model=ManualPaymentConfirmResponse)
async def confirm_manual(
    job_id: str,
    token: str = Query(...),
    payer_name: str | None = Form(None),
    note: str | None = Form(None),
    proof_file: UploadFile | None = File(None),
):
    return await confirm_manual_payment(
        job_id=job_id,
        token=token,
        payer_name=payer_name,
        note=note,
        proof_file=proof_file,
    )


@router.post("/{job_id}/simulate-paid", response_model=PaymentSuccessResponse)
def simulate_paid_route(job_id: str, token: str = Query(...)):
    return simulate_paid(job_id=job_id, token=token)
