from __future__ import annotations

from fastapi import APIRouter, Form, Query

from docurapi.services.admin_payment_service import (
    approve_payment,
    get_admin_payment_detail,
    list_pending_payments,
    reject_payment,
)

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])


@router.get("/pending")
def pending_payments(
    secret: str = Query(...),
    limit: int = Query(25, ge=1, le=100),
):
    return list_pending_payments(secret=secret, limit=limit)


@router.get("/{job_id}")
def payment_detail(job_id: str, secret: str = Query(...)):
    return get_admin_payment_detail(job_id=job_id, secret=secret)


@router.get("/{job_id}/approve")
def approve_payment_by_link(job_id: str, secret: str = Query(...)):
    return approve_payment(job_id=job_id, secret=secret)


@router.post("/{job_id}/approve")
def approve_payment_by_post(job_id: str, secret: str = Query(...)):
    return approve_payment(job_id=job_id, secret=secret)


@router.get("/{job_id}/reject")
def reject_payment_by_link(
    job_id: str,
    secret: str = Query(...),
    reason: str = Query("Pembayaran tidak ditemukan atau tidak sesuai."),
):
    return reject_payment(job_id=job_id, secret=secret, reason=reason)


@router.post("/{job_id}/reject")
def reject_payment_by_post(
    job_id: str,
    secret: str = Query(...),
    reason: str = Form("Pembayaran tidak ditemukan atau tidak sesuai."),
):
    return reject_payment(job_id=job_id, secret=secret, reason=reason)
