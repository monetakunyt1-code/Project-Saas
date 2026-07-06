from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class MidtransPaymentProvider:
    provider_name = "midtrans"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail="Midtrans provider belum dikonfigurasi.")

    def confirm_manual_payment(
        self,
        job: dict[str, Any],
        token: str,
        payer_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        raise HTTPException(status_code=400, detail="Konfirmasi manual tidak tersedia untuk Midtrans.")

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(status_code=400, detail="Simulasi tidak tersedia untuk Midtrans.")
