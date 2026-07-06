from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from docurapi.core.settings import settings


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def calculate_invoice_expiry() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(hours=settings.PAYMENT_EXPIRY_HOURS)
    ).isoformat()


def generate_unique_payment_amount(base_amount: int) -> tuple[int, int]:
    unique_code = secrets.randbelow(
        settings.UNIQUE_CODE_MAX - settings.UNIQUE_CODE_MIN + 1
    ) + settings.UNIQUE_CODE_MIN

    return base_amount + unique_code, unique_code


def is_invoice_expired(job: dict[str, Any]) -> bool:
    payment_status = job.get("payment_status", "unpaid")

    if payment_status == "paid":
        return False

    expires_at = parse_iso_datetime(job.get("invoice_expires_at"))

    if not expires_at:
        return False

    return datetime.now(timezone.utc) > expires_at


def build_invoice_fields(base_amount: int) -> dict[str, int | str]:
    amount, unique_code = generate_unique_payment_amount(base_amount)

    return {
        "base_amount": base_amount,
        "unique_code": unique_code,
        "amount": amount,
        "invoice_expires_at": calculate_invoice_expiry(),
    }


def build_invoice_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": job.get("amount", 0),
        "base_amount": job.get("base_amount", job.get("amount", 0)),
        "unique_code": job.get("unique_code", 0),
        "invoice_expires_at": job.get("invoice_expires_at"),
        "invoice_expired": is_invoice_expired(job),
    }
