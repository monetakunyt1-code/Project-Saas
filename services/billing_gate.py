from __future__ import annotations

from typing import Any

from services.billing_service import (
    consume_entitlement,
    has_processing_access,
)


SERVICE_CODES = {
    "format_simple",
    "format_academic",
    "academic_audit",
    "journal_conversion",
    "template_format",
    "batch_processing",
}


def processing_access_available(
    user_id: str,
    service_code: str,
) -> bool:
    if service_code not in SERVICE_CODES:
        raise ValueError(
            "Kode layanan billing tidak dikenali."
        )

    return has_processing_access(
        user_id=user_id,
        service_code=service_code,
    )


def consume_processing_access(
    user_id: str,
    service_code: str,
    processing_reference: str,
) -> dict[str, Any]:
    if service_code not in SERVICE_CODES:
        raise ValueError(
            "Kode layanan billing tidak dikenali."
        )

    return consume_entitlement(
        user_id=user_id,
        service_code=service_code,
        consumed_reference=(
            processing_reference
        ),
    )
