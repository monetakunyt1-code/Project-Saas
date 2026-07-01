from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from saas_database import (
    consume_usage,
    usage_snapshot,
)
from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)


PROTECTED_OPERATIONS = {
    ("POST", "/api/process"),
    ("POST", "/api/batch/process"),
    ("POST", "/api/audit/document"),
    ("POST", "/api/journal/build"),
}


class SaaSQuotaMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request,
        call_next,
    ):
        operation = (
            request.method.upper(),
            request.url.path,
        )

        if operation not in PROTECTED_OPERATIONS:
            return await call_next(request)

        user = session_user(
            request.cookies.get(
                SESSION_COOKIE
            )
        )

        if not user:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": (
                        "Silakan login sebelum "
                        "memproses dokumen."
                    )
                },
            )

        usage = usage_snapshot(
            user["user_id"]
        )

        if (
            int(usage["used_count"])
            >= int(usage["monthly_quota"])
        ):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        "Kuota bulanan telah habis. "
                        "Tingkatkan paket untuk melanjutkan."
                    ),
                    "usage": usage,
                },
            )

        request.state.saas_user = user

        response = await call_next(request)

        if 200 <= response.status_code < 300:
            consume_usage(
                user["user_id"],
                1,
            )

        return response