from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from docurapi.core.settings import settings
from docurapi.db.jobs_repository import get_job
from docurapi.providers.payment.midtrans import MidtransPaymentProvider
from docurapi.providers.payment.simulation import SimulationPaymentProvider
from docurapi.providers.payment.xendit import XenditPaymentProvider


def get_payment_provider():
    payment_mode = settings.PAYMENT_MODE.lower().strip()

    if payment_mode == "simulation":
        return SimulationPaymentProvider()

    if payment_mode == "midtrans":
        return MidtransPaymentProvider()

    if payment_mode == "xendit":
        return XenditPaymentProvider()

    raise HTTPException(
        status_code=500,
        detail=f"Payment mode tidak dikenal: {settings.PAYMENT_MODE}",
    )


def ensure_payment_access(job_id: str, token: str) -> dict[str, Any]:
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


def create_checkout(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)
    provider = get_payment_provider()

    return provider.create_checkout(job, token)


def simulate_paid(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)
    provider = get_payment_provider()

    return provider.simulate_paid(job, token)
