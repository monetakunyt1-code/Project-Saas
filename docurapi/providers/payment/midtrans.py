from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class MidtransPaymentProvider:
    provider_name = "midtrans"

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(
            status_code=501,
            detail="Midtrans provider belum dikonfigurasi. Gunakan DOCURAPI_PAYMENT_MODE=simulation untuk development.",
        )

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        raise HTTPException(
            status_code=400,
            detail="Simulasi pembayaran tidak tersedia pada Midtrans provider.",
        )
