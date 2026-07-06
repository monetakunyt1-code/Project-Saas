from __future__ import annotations

from typing import Any, Protocol


class PaymentProvider(Protocol):
    provider_name: str

    def create_checkout(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        """Membuat sesi checkout untuk job yang belum dibayar."""
        ...

    def simulate_paid(self, job: dict[str, Any], token: str) -> dict[str, Any]:
        """Dipakai hanya untuk mode development/simulation."""
        ...
