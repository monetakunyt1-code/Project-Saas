from __future__ import annotations

import secrets
from typing import Any

from docurapi.db.jobs_repository import mark_job_paid
from docurapi.db.payments_repository import (
    create_payment_record,
    get_latest_payment_for_job,
    update_latest_payment_for_job,
)


class SimulationPaymentProvider:
    provider_name = "simulation"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]
        amount = job.get("amount", 0)

        if job.get("payment_status", "unpaid") == "paid":
            latest_payment = get_latest_payment_for_job(job_id)

            return {
                "success": True,
                "job_id": job_id,
                "payment_id": latest_payment["payment_id"] if latest_payment else None,
                "provider": self.provider_name,
                "payment_status": "paid",
                "amount": amount,
                "message": "Pembayaran sudah berhasil. Dokumen sudah bisa di-download.",
                "simulate_payment_url": None,
            }

        latest_payment = get_latest_payment_for_job(job_id)

        if not latest_payment or latest_payment["status"] != "pending":
            latest_payment = create_payment_record(
                job_id=job_id,
                provider=self.provider_name,
                amount=amount,
                status="pending",
                checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                raw_payload={"mode": "simulation"},
            )

        return {
            "success": True,
            "job_id": job_id,
            "payment_id": latest_payment["payment_id"],
            "provider": self.provider_name,
            "payment_status": "unpaid",
            "amount": amount,
            "message": "Mode development: checkout masih simulasi.",
            "simulate_payment_url": f"/api/payments/{job_id}/simulate-paid?token={token}",
        }

    def confirm_manual_payment(
        self,
        job: dict[str, Any],
        token: str,
        payer_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        return self.simulate_paid(job, token)

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]
        payment_reference = f"DEV-{secrets.token_hex(8).upper()}"

        if not get_latest_payment_for_job(job_id):
            create_payment_record(
                job_id=job_id,
                provider=self.provider_name,
                amount=job.get("amount", 0),
                status="pending",
                checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                raw_payload={"mode": "simulation-auto-created"},
            )

        update_latest_payment_for_job(
            job_id=job_id,
            status="paid",
            external_reference=payment_reference,
            raw_payload={"mode": "simulation", "event": "simulate-paid"},
        )

        mark_job_paid(job_id, payment_reference)

        return {
            "success": True,
            "job_id": job_id,
            "payment_status": "paid",
            "payment_reference": payment_reference,
            "message": "Pembayaran simulasi berhasil. Download dokumen sudah terbuka.",
            "download_url": f"/api/jobs/{job_id}/download?token={token}",
        }
