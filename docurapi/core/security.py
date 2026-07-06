from __future__ import annotations

import hashlib
import hmac

from docurapi.core.settings import settings


def _admin_secret_bytes() -> bytes:
    return settings.ADMIN_APPROVAL_SECRET.encode("utf-8")


def create_admin_action_token(job_id: str, action: str) -> str:
    normalized_action = action.lower().strip()
    message = f"{job_id}:{normalized_action}"

    signature = hmac.new(
        _admin_secret_bytes(),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{message}:{signature}"


def verify_admin_action_token(job_id: str, action: str, token: str) -> bool:
    normalized_action = action.lower().strip()
    expected = create_admin_action_token(job_id=job_id, action=normalized_action)

    return hmac.compare_digest(expected, token)
