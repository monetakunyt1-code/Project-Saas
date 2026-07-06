from __future__ import annotations

import secrets
from typing import Any

from docurapi.db.jobs_repository import mark_job_paid
from docurapi.db.payments_repository import (
    create_payment_record,
    get_latest_payment_for_job,
    mark_latest_payment_paid_for_job,
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

        if latest_payment and latest_payment["status"] == "pending":
            payment = latest_payment
        else:
            payment = create_payment_record(
                job_id=job_id,
                provider=self.provider_name,
                amount=amount,
                status="pending",
                checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                raw_payload={
                    "mode": "simulation",
                    "job_id": job_id,
                    "amount": amount,
                },
            )

        return {
            "success": True,
            "job_id": job_id,
            "payment_id": payment["payment_id"],
            "provider": self.provider_name,
            "payment_status": "unpaid",
            "amount": amount,
            "message": "Mode development: checkout masih simulasi. Endpoint ini nanti dapat diganti dengan payment gateway.",
            "simulate_payment_url": f"/api/payments/{job_id}/simulate-paid?token={token}",
        }

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]

        if job.get("payment_status", "unpaid") == "paid":
            payment_reference = job.get("payment_reference") or "already-paid"
        else:
            payment_reference = f"DEV-{secrets.token_hex(8).upper()}"

            latest_payment = get_latest_payment_for_job(job_id)

            if not latest_payment:
                create_payment_record(
                    job_id=job_id,
                    provider=self.provider_name,
                    amount=job.get("amount", 0),
                    status="pending",
                    checkout_url=f"/api/payments/{job_id}/checkout?token={token}",
                    raw_payload={
                        "mode": "simulation-auto-created",
                        "job_id": job_id,
                    },
                )

            mark_latest_payment_paid_for_job(
                job_id=job_id,
                external_reference=payment_reference,
                raw_payload={
                    "mode": "simulation",
                    "event": "simulate-paid",
                    "payment_reference": payment_reference,
                },
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
