from __future__ import annotations

from typing import Any

from docurapi.core.logging_config import logger
from docurapi.db.audit_repository import create_audit_log


def log_event(
    event_type: str,
    actor: str,
    message: str,
    job_id: str | None = None,
    payment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        create_audit_log(
            event_type=event_type,
            actor=actor,
            message=message,
            job_id=job_id,
            payment_id=payment_id,
            metadata=metadata,
        )
    except Exception:
        logger.exception("Gagal menyimpan audit log.")
