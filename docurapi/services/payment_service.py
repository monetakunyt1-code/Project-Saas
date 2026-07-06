from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from docurapi.core.settings import settings
from docurapi.db.jobs_repository import get_job, mark_job_expired, update_job_invoice
from docurapi.db.payments_repository import create_payment_record, list_payments_for_job, update_latest_payment_for_job
from docurapi.providers.payment.manual_qris_whatsapp import ManualQrisWhatsappPaymentProvider
from docurapi.providers.payment.midtrans import MidtransPaymentProvider
from docurapi.providers.payment.simulation import SimulationPaymentProvider
from docurapi.providers.payment.xendit import XenditPaymentProvider
from docurapi.services.file_service import safe_filename
from docurapi.services.invoice_service import build_invoice_fields, is_invoice_expired


def get_payment_provider():
    payment_mode = settings.PAYMENT_MODE.lower().strip()

    if payment_mode == "manual_qris_whatsapp":
        return ManualQrisWhatsappPaymentProvider()

    if payment_mode == "manual_qris":
        return ManualQrisWhatsappPaymentProvider()

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
        raise HTTPException(status_code=404, detail="Job tidak ditemukan.")

    saved_token = job.get("access_token")

    if saved_token and token != saved_token:
        raise HTTPException(status_code=403, detail="Token akses tidak valid.")

    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Dokumen belum selesai diproses.")

    return job


def ensure_invoice_can_be_confirmed(job: dict[str, Any]) -> None:
    if is_invoice_expired(job):
        mark_job_expired(job["job_id"])
        raise HTTPException(
            status_code=409,
            detail="Invoice pembayaran sudah kedaluwarsa. Silakan refresh invoice sebelum melakukan konfirmasi pembayaran.",
        )


async def save_payment_proof(job_id: str, proof_file: UploadFile | None) -> dict[str, Any] | None:
    if not proof_file or not proof_file.filename:
        return None

    original_name = safe_filename(proof_file.filename)
    suffix = Path(original_name).suffix.lower()

    if suffix not in settings.ALLOWED_PAYMENT_PROOF_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Bukti pembayaran harus berupa JPG, JPEG, PNG, WEBP, atau PDF.",
        )

    content = await proof_file.read()

    if not content:
        return None

    if len(content) > settings.MAX_PAYMENT_PROOF_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Ukuran bukti pembayaran melebihi batas 5 MB.",
        )

    destination = settings.PAYMENT_PROOF_DIR / f"{job_id}_{uuid4().hex}_{original_name}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    return {
        "proof_file_name": original_name,
        "proof_path": str(destination),
        "proof_content_type": proof_file.content_type or "application/octet-stream",
    }


def create_checkout(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)

    if is_invoice_expired(job):
        mark_job_expired(job_id)
        job = get_job(job_id) or job

    provider = get_payment_provider()
    return provider.create_checkout(job, token)


async def confirm_manual_payment(
    job_id: str,
    token: str,
    payer_name: str | None = None,
    note: str | None = None,
    proof_file: UploadFile | None = None,
) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)
    ensure_invoice_can_be_confirmed(job)

    provider = get_payment_provider()
    proof_meta = await save_payment_proof(job_id=job_id, proof_file=proof_file)

    return provider.confirm_manual_payment(
        job=job,
        token=token,
        payer_name=payer_name,
        note=note,
        proof_meta=proof_meta,
    )


def refresh_invoice(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)

    if job.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Invoice tidak bisa diperbarui karena pembayaran sudah paid.")

    if job.get("payment_status") == "pending_verification":
        raise HTTPException(status_code=400, detail="Invoice tidak bisa diperbarui karena pembayaran sedang menunggu verifikasi admin.")

    base_amount = int(job.get("base_amount") or job.get("amount") or 0)

    if base_amount <= 0:
        raise HTTPException(status_code=400, detail="Harga dasar invoice tidak valid.")

    invoice_fields = build_invoice_fields(base_amount)

    update_job_invoice(
        job_id=job_id,
        base_amount=int(invoice_fields["base_amount"]),
        unique_code=int(invoice_fields["unique_code"]),
        amount=int(invoice_fields["amount"]),
        invoice_expires_at=str(invoice_fields["invoice_expires_at"]),
    )

    create_payment_record(
        job_id=job_id,
        provider=get_payment_provider().provider_name,
        amount=int(invoice_fields["amount"]),
        status="waiting_user_payment",
        checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
        raw_payload={
            "event": "refresh_invoice",
            "base_amount": invoice_fields["base_amount"],
            "unique_code": invoice_fields["unique_code"],
            "amount": invoice_fields["amount"],
            "invoice_expires_at": invoice_fields["invoice_expires_at"],
        },
    )

    refreshed_job = get_job(job_id)

    if not refreshed_job:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan setelah refresh invoice.")

    checkout = get_payment_provider().create_checkout(refreshed_job, token)
    checkout["message"] = "Invoice berhasil diperbarui. Gunakan nominal unik terbaru untuk pembayaran."

    return checkout


def simulate_paid(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)
    provider = get_payment_provider()
    return provider.simulate_paid(job, token)


def get_payment_status(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)

    if is_invoice_expired(job):
        mark_job_expired(job_id)
        job = get_job(job_id) or job

    payments = list_payments_for_job(job_id)

    return {
        "success": True,
        "job_id": job_id,
        "job_payment_status": job.get("payment_status", "unpaid"),
        "amount": job.get("amount", 0),
        "base_amount": job.get("base_amount", job.get("amount", 0)),
        "unique_code": job.get("unique_code", 0),
        "invoice_expires_at": job.get("invoice_expires_at"),
        "invoice_expired": is_invoice_expired(job),
        "payments": payments,
    }
