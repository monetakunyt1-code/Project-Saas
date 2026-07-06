from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class XenditPaymentProvider:
    provider_name = "xendit"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail="Xendit provider belum dikonfigurasi.")

    def confirm_manual_payment(
        self,
        job: dict[str, Any],
        token: str,
        payer_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        raise HTTPException(status_code=400, detail="Konfirmasi manual tidak tersedia untuk Xendit.")

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(status_code=400, detail="Simulasi tidak tersedia untuk Xendit.")
