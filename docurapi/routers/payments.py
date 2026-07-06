from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, UploadFile

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
