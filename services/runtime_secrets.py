from __future__ import annotations

import os
from typing import Final


MINIMUM_SECRET_LENGTH: Final[int] = 32

PLACEHOLDER_VALUES: Final[set[str]] = {
    "",
    "changeme",
    "change-me",
    "replace-me",
    "replace-with-strong-password",
    "ganti-dengan-secret-kuat",
    "ganti-dengan-password-kuat",
    "local-development-secret",
    "secret",
    "password",
    "your-secret",
}


def _environment_value(
    name: str,
) -> str:
    return os.getenv(
        name,
        "",
    ).strip()


def _is_secure_secret(
    value: str,
) -> bool:
    return (
        len(value) >= MINIMUM_SECRET_LENGTH
        and value.lower()
        not in PLACEHOLDER_VALUES
    )


def application_secret() -> str:
    value = _environment_value(
        "DOCURAPI_SECRET_KEY"
    )

    if not _is_secure_secret(value):
        raise RuntimeError(
            "DOCURAPI_SECRET_KEY belum aman."
        )

    return value


def session_secret() -> str:
    value = _environment_value(
        "DOCURAPI_SESSION_SECRET"
    )

    if not _is_secure_secret(value):
        raise RuntimeError(
            "DOCURAPI_SESSION_SECRET belum aman."
        )

    return value


def payment_webhook_secret() -> str:
    value = _environment_value(
        "DOCURAPI_PAYMENT_WEBHOOK_SECRET"
    )

    if not _is_secure_secret(value):
        raise RuntimeError(
            "DOCURAPI_PAYMENT_WEBHOOK_SECRET belum aman."
        )

    return value


def validate_runtime_secrets() -> dict[str, int]:
    application = application_secret()
    session = session_secret()
    webhook = payment_webhook_secret()

    return {
        "application_secret_length": len(
            application
        ),
        "session_secret_length": len(
            session
        ),
        "webhook_secret_length": len(
            webhook
        ),
    }
