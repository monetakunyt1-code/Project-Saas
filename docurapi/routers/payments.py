from __future__ import annotations

from fastapi import APIRouter, Form, Query

from docurapi.schemas.common import (
    ManualPaymentConfirmResponse,
    PaymentCheckoutResponse,
    PaymentStatusResponse,
    PaymentSuccessResponse,
)
from docurapi.services.payment_service import (
    confirm_manual_payment,
    create_checkout,
    get_payment_status,
    simulate_paid,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/{job_id}/checkout", response_model=PaymentCheckoutResponse)
def checkout(job_id: str, token: str = Query(...)):
    return create_checkout(job_id=job_id, token=token)


@router.get("/{job_id}/status", response_model=PaymentStatusResponse)
def payment_status(job_id: str, token: str = Query(...)):
    return get_payment_status(job_id=job_id, token=token)


@router.post("/{job_id}/confirm-manual", response_model=ManualPaymentConfirmResponse)
def confirm_manual(
    job_id: str,
    token: str = Query(...),
    payer_name: str | None = Form(None),
    note: str | None = Form(None),
):
    return confirm_manual_payment(
        job_id=job_id,
        token=token,
        payer_name=payer_name,
        note=note,
    )


@router.post("/{job_id}/simulate-paid", response_model=PaymentSuccessResponse)
def simulate_paid_route(job_id: str, token: str = Query(...)):
    return simulate_paid(job_id=job_id, token=token)
