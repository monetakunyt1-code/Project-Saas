from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request

from saas_database import (
    create_session,
    create_user,
    delete_session,
    get_session,
    get_user_by_email,
)


SESSION_COOKIE = "docurapi_session"
SESSION_DAYS = 14
ITERATIONS = 240_000

EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


def normalize_email(
    email: str,
) -> str:
    return email.strip().lower()


def password_hash(
    password: str,
    salt_hex: str | None = None,
) -> tuple[str, str]:
    if len(password) < 8 or len(password) > 128:
        raise ValueError(
            "Kata sandi harus 8–128 karakter."
        )

    salt = (
        bytes.fromhex(salt_hex)
        if salt_hex
        else secrets.token_bytes(24)
    )

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )

    return (
        digest.hex(),
        salt.hex(),
    )


def verify_password(
    password: str,
    expected_hash: str,
    salt_hex: str,
) -> bool:
    try:
        actual_hash, _ = password_hash(
            password,
            salt_hex,
        )
    except ValueError:
        return False

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )


def public_user(
    user: dict[str, Any],
) -> dict[str, Any]:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "is_active": bool(
            user["is_active"]
        ),
        "created_at": user["created_at"],
    }


def register(
    email: str,
    display_name: str,
    password: str,
) -> dict[str, Any]:
    email = normalize_email(email)
    display_name = display_name.strip()

    if not EMAIL_PATTERN.match(email):
        raise ValueError(
            "Format email tidak valid."
        )

    if len(display_name) < 2 or len(display_name) > 100:
        raise ValueError(
            "Nama pengguna harus 2–100 karakter."
        )

    if get_user_by_email(email):
        raise ValueError(
            "Email sudah terdaftar."
        )

    digest, salt = password_hash(password)

    return public_user(
        create_user(
            user_id=uuid4().hex,
            email=email,
            display_name=display_name,
            password_hash=digest,
            password_salt=salt,
        )
    )


def authenticate(
    email: str,
    password: str,
) -> dict[str, Any]:
    user = get_user_by_email(
        normalize_email(email)
    )

    if (
        not user
        or not verify_password(
            password,
            user["password_hash"],
            user["password_salt"],
        )
    ):
        raise ValueError(
            "Email atau kata sandi salah."
        )

    if not bool(user["is_active"]):
        raise ValueError(
            "Akun sedang dinonaktifkan."
        )

    return public_user(user)


def issue_session(
    user_id: str,
) -> str:
    raw_token = secrets.token_urlsafe(48)

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=SESSION_DAYS)
    ).isoformat()

    create_session(
        token_hash,
        user_id,
        expires_at,
    )

    return raw_token


def session_user(
    raw_token: str | None,
) -> dict[str, Any] | None:
    if not raw_token:
        return None

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    record = get_session(token_hash)

    if not record:
        return None

    try:
        expires_at = datetime.fromisoformat(
            record["expires_at"]
        )
    except ValueError:
        delete_session(token_hash)
        return None

    if (
        expires_at <= datetime.now(timezone.utc)
        or not bool(record["is_active"])
    ):
        delete_session(token_hash)
        return None

    return public_user(record)


def logout(
    raw_token: str | None,
) -> None:
    if not raw_token:
        return

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    delete_session(token_hash)


def require_user(
    request: Request,
) -> dict[str, Any]:
    user = session_user(
        request.cookies.get(
            SESSION_COOKIE
        )
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Silakan login terlebih dahulu.",
        )

    return user


def require_admin(
    request: Request,
) -> dict[str, Any]:
    user = require_user(request)

    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Akses administrator diperlukan.",
        )

    return user