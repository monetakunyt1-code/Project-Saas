from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from docurapi.core.security import verify_admin_action_token
from docurapi.core.settings import settings
from docurapi.db.jobs_repository import (
    get_job,
    list_jobs_by_payment_status,
    mark_job_paid,
    mark_job_rejected,
)
from docurapi.db.payments_repository import (
    get_latest_payment_for_job,
    list_payments_for_job,
    update_latest_payment_for_job,
)


def ensure_admin_secret(secret: str) -> None:
    if not settings.ADMIN_APPROVAL_SECRET:
        raise HTTPException(status_code=500, detail="Admin approval secret belum dikonfigurasi.")

    if secret != settings.ADMIN_APPROVAL_SECRET:
        raise HTTPException(status_code=403, detail="Secret admin tidak valid.")


def ensure_admin_action_access(
    job_id: str,
    action: str,
    secret: str | None = None,
    admin_token: str | None = None,
) -> None:
    if admin_token and verify_admin_action_token(job_id=job_id, action=action, token=admin_token):
        return

    if secret:
        ensure_admin_secret(secret)
        return

    raise HTTPException(status_code=403, detail="Akses admin tidak valid.")


def list_pending_payments(secret: str, limit: int = 25) -> dict:
    ensure_admin_secret(secret)
    jobs = list_jobs_by_payment_status("pending_verification", limit=limit)

    return {
        "success": True,
        "total": len(jobs),
        "jobs": jobs,
    }


def approve_payment(
    job_id: str,
    secret: str | None = None,
    admin_token: str | None = None,
) -> dict:
    ensure_admin_action_access(job_id=job_id, action="approve", secret=secret, admin_token=admin_token)

    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")

    payment_reference = job.get("payment_reference") or f"MANUAL-APPROVED-{job_id[:8].upper()}"

    update_latest_payment_for_job(
        job_id=job_id,
        status="paid",
        external_reference=payment_reference,
        raw_payload={
            "event": "admin_approve_manual_qris",
            "approved_by": "admin_action_token",
        },
    )

    mark_job_paid(job_id, payment_reference)

    return {
        "success": True,
        "job_id": job_id,
        "payment_status": "paid",
        "payment_reference": payment_reference,
        "message": "Pembayaran disetujui. Download sudah terbuka.",
        "download_url": f"/api/jobs/{job_id}/download?token={job.get('access_token')}",
    }


def reject_payment(
    job_id: str,
    secret: str | None = None,
    admin_token: str | None = None,
    reason: str = "Pembayaran tidak ditemukan atau tidak sesuai.",
) -> dict:
    ensure_admin_action_access(job_id=job_id, action="reject", secret=secret, admin_token=admin_token)

    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")

    update_latest_payment_for_job(
        job_id=job_id,
        status="rejected",
        raw_payload={
            "event": "admin_reject_manual_qris",
            "reason": reason,
        },
        rejection_reason=reason,
    )

    mark_job_rejected(job_id, reason)

    return {
        "success": True,
        "job_id": job_id,
        "payment_status": "rejected",
        "message": "Pembayaran ditolak.",
        "reason": reason,
    }


def get_admin_payment_detail(
    job_id: str,
    secret: str | None = None,
    admin_token: str | None = None,
) -> dict:
    ensure_admin_action_access(job_id=job_id, action="view", secret=secret, admin_token=admin_token)

    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")

    payments = list_payments_for_job(job_id)
    proof_url = None

    latest_payment = payments[0] if payments else None

    if latest_payment and latest_payment.get("proof_path"):
        proof_url = f"/api/admin/payments/{job_id}/proof"

    return {
        "success": True,
        "job": job,
        "payments": payments,
        "proof_url": proof_url,
    }


def get_payment_proof_response(
    job_id: str,
    secret: str | None = None,
    admin_token: str | None = None,
):
    ensure_admin_action_access(job_id=job_id, action="view", secret=secret, admin_token=admin_token)

    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")

    payment = get_latest_payment_for_job(job_id)

    if not payment or not payment.get("proof_path"):
        raise HTTPException(status_code=404, detail="Bukti pembayaran belum tersedia.")

    proof_path = Path(payment["proof_path"])

    try:
        proof_path.relative_to(settings.PAYMENT_PROOF_DIR)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path bukti pembayaran tidak valid.")

    if not proof_path.exists() or not proof_path.is_file():
        raise HTTPException(status_code=404, detail="File bukti pembayaran tidak ditemukan.")

    return FileResponse(
        proof_path,
        filename=payment.get("proof_file_name") or proof_path.name,
        media_type=payment.get("proof_content_type") or "application/octet-stream",
    )
