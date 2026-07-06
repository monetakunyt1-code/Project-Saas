from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Query

from docurapi.db.jobs_repository import get_job, mark_job_paid
from docurapi.schemas.common import PaymentCheckoutResponse, PaymentSuccessResponse

router = APIRouter(prefix="/api/payments", tags=["payments"])


def ensure_payment_access(job_id: str, token: str):
    job = get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job tidak ditemukan.",
        )

    saved_token = job.get("access_token")

    if saved_token and token != saved_token:
        raise HTTPException(
            status_code=403,
            detail="Token akses tidak valid.",
        )

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Dokumen belum selesai diproses.",
        )

    return job


@router.get("/{job_id}/checkout", response_model=PaymentCheckoutResponse)
def checkout(job_id: str, token: str = Query(...)):
    job = ensure_payment_access(job_id, token)

    payment_status = job.get("payment_status", "unpaid")

    if payment_status == "paid":
        return {
            "success": True,
            "job_id": job_id,
            "payment_status": "paid",
            "amount": job.get("amount", 0),
            "message": "Pembayaran sudah berhasil. Dokumen sudah bisa di-download.",
            "simulate_payment_url": None,
        }

    return {
        "success": True,
        "job_id": job_id,
        "payment_status": "unpaid",
        "amount": job.get("amount", 0),
        "message": "Mode development: checkout masih simulasi. Nanti endpoint ini diganti integrasi payment gateway.",
        "simulate_payment_url": f"/api/payments/{job_id}/simulate-paid?token={token}",
    }


@router.post("/{job_id}/simulate-paid", response_model=PaymentSuccessResponse)
def simulate_paid(job_id: str, token: str = Query(...)):
    job = ensure_payment_access(job_id, token)

    if job.get("payment_status", "unpaid") == "paid":
        payment_reference = job.get("payment_reference") or "already-paid"
    else:
        payment_reference = f"DEV-{secrets.token_hex(8).upper()}"
        mark_job_paid(job_id, payment_reference)

    return {
        "success": True,
        "job_id": job_id,
        "payment_status": "paid",
        "payment_reference": payment_reference,
        "message": "Pembayaran simulasi berhasil. Download dokumen sudah terbuka.",
        "download_url": f"/api/jobs/{job_id}/download?token={token}",
    }
