from __future__ import annotations

from typing import Any, Protocol


class PaymentProvider(Protocol):
    provider_name: str

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        ...

    def confirm_manual_payment(
        self,
        job: dict[str, Any],
        token: str,
        payer_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        ...

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        ...
