from __future__ import annotations

import hmac
import os
import secrets
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from security_database import (
    add_audit_event,
    hit_rate_limit,
)
from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)


CSRF_COOKIE = "docurapi_csrf"
CSRF_HEADER = "X-CSRF-Token"

UNSAFE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}

AUTH_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/security/password/reset/request",
    "/api/security/password/reset/confirm",
}

PROCESSING_PATHS = {
    "/api/process",
    "/api/batch/process",
    "/api/audit/document",
    "/api/journal/build",
}


def secure_cookie_enabled() -> bool:
    return os.getenv(
        "DOCURAPI_COOKIE_SECURE",
        "0",
    ) == "1"


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(
        32
    )


def request_csrf_token(
    request: Request,
) -> str:
    token = request.cookies.get(
        CSRF_COOKIE
    )

    if token:
        return token

    return generate_csrf_token()


def client_ip(
    request: Request,
) -> str:
    if request.client:
        return request.client.host

    return "unknown"


def apply_security_headers(
    response: Any,
) -> None:
    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "DENY"

    response.headers[
        "Referrer-Policy"
    ] = "strict-origin-when-cross-origin"

    response.headers[
        "Permissions-Policy"
    ] = (
        "camera=(), microphone=(), "
        "geolocation=(), payment=()"
    )

    response.headers[
        "Content-Security-Policy"
    ] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    if secure_cookie_enabled():
        response.headers[
            "Strict-Transport-Security"
        ] = (
            "max-age=31536000; "
            "includeSubDomains"
        )


def attach_csrf_cookie(
    response: Any,
    csrf_token: str,
) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        max_age=14 * 24 * 60 * 60,
        httponly=False,
        secure=secure_cookie_enabled(),
        samesite="lax",
        path="/",
    )


class SecurityMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        csrf_token = request_csrf_token(
            request
        )

        raw_session = request.cookies.get(
            SESSION_COOKIE
        )

        user = session_user(
            raw_session
        )

        identity = (
            user["user_id"]
            if user
            else client_ip(request)
        )

        path = request.url.path
        method = request.method.upper()

        if path in AUTH_PATHS:
            rate_result = hit_rate_limit(
                scope="auth",
                identity=client_ip(request),
                limit=10,
                window_seconds=60,
            )

        elif (
            method in UNSAFE_METHODS
            and path in PROCESSING_PATHS
        ):
            rate_result = hit_rate_limit(
                scope="processing",
                identity=identity,
                limit=30,
                window_seconds=60,
            )

        elif method in UNSAFE_METHODS:
            rate_result = hit_rate_limit(
                scope="write",
                identity=identity,
                limit=90,
                window_seconds=60,
            )

        else:
            rate_result = {
                "allowed": True,
                "remaining": 0,
                "retry_after": 0,
            }

        if not rate_result["allowed"]:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Terlalu banyak permintaan. "
                        "Silakan tunggu sebelum mencoba lagi."
                    ),
                    "retry_after": rate_result[
                        "retry_after"
                    ],
                },
            )

            response.headers[
                "Retry-After"
            ] = str(
                rate_result["retry_after"]
            )

            apply_security_headers(
                response
            )

            attach_csrf_cookie(
                response,
                csrf_token,
            )

            return response

        if (
            method in UNSAFE_METHODS
            and path.startswith("/api/")
        ):
            submitted_token = (
                request.headers.get(
                    CSRF_HEADER
                )
            )

            cookie_token = (
                request.cookies.get(
                    CSRF_COOKIE
                )
            )

            valid_csrf = bool(
                submitted_token
                and cookie_token
                and hmac.compare_digest(
                    submitted_token,
                    cookie_token,
                )
            )

            if not valid_csrf:
                response = JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Token keamanan tidak valid. "
                            "Muat ulang halaman lalu coba kembali."
                        )
                    },
                )

                apply_security_headers(
                    response
                )

                attach_csrf_cookie(
                    response,
                    csrf_token,
                )

                return response

        request.state.security_user = user

        response = await call_next(
            request
        )

        if (
            method in UNSAFE_METHODS
            or path.startswith(
                "/api/admin/"
            )
        ):
            try:
                add_audit_event(
                    user_id=(
                        user["user_id"]
                        if user
                        else None
                    ),
                    email=(
                        user["email"]
                        if user
                        else None
                    ),
                    ip_address=client_ip(
                        request
                    ),
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    user_agent=request.headers.get(
                        "user-agent",
                        "",
                    ),
                )
            except Exception:
                pass

        apply_security_headers(
            response
        )

        attach_csrf_cookie(
            response,
            csrf_token,
        )

        if (
            path.startswith("/account")
            or path.startswith("/admin")
            or path.startswith(
                "/security-center"
            )
            or path.startswith(
                "/api/auth/"
            )
            or path.startswith(
                "/api/security/"
            )
        ):
            response.headers[
                "Cache-Control"
            ] = (
                "no-store, max-age=0"
            )

        return response