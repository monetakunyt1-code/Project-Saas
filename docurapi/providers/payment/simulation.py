from __future__ import annotations

import secrets
from typing import Any

from docurapi.db.jobs_repository import mark_job_paid


class SimulationPaymentProvider:
    provider_name = "simulation"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]

        if job.get("payment_status", "unpaid") == "paid":
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
            "message": "Mode development: checkout masih simulasi. Endpoint ini nanti dapat diganti dengan payment gateway.",
            "simulate_payment_url": f"/api/payments/{job_id}/simulate-paid?token={token}",
        }

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        job_id = job["job_id"]

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
