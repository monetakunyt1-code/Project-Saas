from __future__ import annotations

from fastapi import APIRouter, Query

from docurapi.schemas.common import PaymentCheckoutResponse, PaymentSuccessResponse
from docurapi.services.payment_service import create_checkout, simulate_paid

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/{job_id}/checkout", response_model=PaymentCheckoutResponse)
def checkout(job_id: str, token: str = Query(...)):
    return create_checkout(job_id=job_id, token=token)


@router.post("/{job_id}/simulate-paid", response_model=PaymentSuccessResponse)
def simulate_paid_route(job_id: str, token: str = Query(...)):
    return simulate_paid(job_id=job_id, token=token)
