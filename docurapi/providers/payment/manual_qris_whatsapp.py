from __future__ import annotations

from typing import Any
from urllib.parse import quote

from docurapi.core.security import create_admin_action_token
from docurapi.core.settings import settings
from docurapi.db.jobs_repository import mark_job_pending_verification
from docurapi.db.payments_repository import (
    create_payment_record,
    get_latest_payment_for_job,
    update_latest_payment_for_job,
)


class ManualQrisWhatsappPaymentProvider:
    provider_name = "manual_qris_whatsapp"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]
        amount = job.get("amount", 0)
        payment_status = job.get("payment_status", "unpaid")

        latest_payment = get_latest_payment_for_job(job_id)

        if not latest_payment or latest_payment["status"] in {"paid", "rejected", "failed"}:
            latest_payment = create_payment_record(
                job_id=job_id,
                provider=self.provider_name,
                amount=amount,
                status="waiting_user_payment",
                checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                raw_payload={
                    "mode": "manual_qris_whatsapp",
                    "merchant_name": settings.MERCHANT_NAME,
                    "qris_static_image_url": settings.QRIS_STATIC_IMAGE_URL,
                },
            )

        return {
            "success": True,
            "job_id": job_id,
            "payment_id": latest_payment["payment_id"],
            "provider": self.provider_name,
            "payment_status": payment_status,
            "amount": amount,
            "message": "Silakan bayar melalui QRIS statis, lalu klik konfirmasi pembayaran.",
            "qris_type": "static",
            "merchant_name": settings.MERCHANT_NAME,
            "qris_static_image_url": settings.QRIS_STATIC_IMAGE_URL,
            "payment_instruction": [
                "Scan QRIS menggunakan aplikasi pembayaran.",
                f"Pastikan nominal pembayaran adalah Rp{amount:,}.",
                "Setelah membayar, klik tombol konfirmasi pembayaran.",
                "Download akan dibuka setelah admin memverifikasi pembayaran.",
            ],
            "confirm_manual_url": f"/api/payments/{job_id}/confirm-manual?token={token}",
            "simulate_payment_url": None,
        }

    def confirm_manual_payment(
        self,
        job: dict[str, Any],
        token: str,
        payer_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        job_id = job["job_id"]
        amount = job.get("amount", 0)

        latest_payment = get_latest_payment_for_job(job_id)

        if not latest_payment:
            latest_payment = create_payment_record(
                job_id=job_id,
                provider=self.provider_name,
                amount=amount,
                status="waiting_user_payment",
                checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                raw_payload={
                    "mode": "manual_qris_whatsapp-auto-created",
                },
            )

        update_latest_payment_for_job(
            job_id=job_id,
            status="pending_verification",
            raw_payload={
                "event": "user_confirm_manual_payment",
                "payer_name": payer_name,
                "note": note,
            },
        )

        mark_job_pending_verification(job_id)

        admin_whatsapp_url = self._build_admin_whatsapp_url(
            job=job,
            payer_name=payer_name,
            note=note,
        )

        return {
            "success": True,
            "job_id": job_id,
            "payment_id": latest_payment["payment_id"],
            "payment_status": "pending_verification",
            "amount": amount,
            "message": "Konfirmasi pembayaran diterima. Admin perlu memverifikasi pembayaran sebelum download dibuka.",
            "admin_whatsapp_url": admin_whatsapp_url,
        }

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        return self.confirm_manual_payment(job=job, token=token)

    def _build_admin_whatsapp_url(
        self,
        job: dict[str, Any],
        payer_name: str | None,
        note: str | None,
    ) -> str | None:
        admin_number = settings.ADMIN_WHATSAPP.strip()

        if not admin_number:
            return None

        job_id = job["job_id"]
        public_base = settings.PUBLIC_BASE_URL.rstrip("/")

        approve_token = quote(
            create_admin_action_token(job_id=job_id, action="approve"),
            safe="",
        )

        reject_token = quote(
            create_admin_action_token(job_id=job_id, action="reject"),
            safe="",
        )

        approve_url = f"{public_base}/api/admin/payments/{job_id}/approve?admin_token={approve_token}"
        reject_url = f"{public_base}/api/admin/payments/{job_id}/reject?admin_token={reject_token}"

        message = (
            "Konfirmasi pembayaran DocuRapi\n\n"
            f"Job ID: {job_id}\n"
            f"File: {job.get('original_name')}\n"
            f"Mode: {job.get('mode')}\n"
            f"Preset: {job.get('preset')}\n"
            f"Nominal: Rp{job.get('amount', 0):,}\n"
            f"Nama pembayar: {payer_name or '-'}\n"
            f"Catatan: {note or '-'}\n\n"
            "Cek transaksi di aplikasi ShopeePay Merchant terlebih dahulu.\n\n"
            f"APPROVE:\n{approve_url}\n\n"
            f"REJECT:\n{reject_url}"
        )

        return f"https://wa.me/{admin_number}?text={quote(message)}"
