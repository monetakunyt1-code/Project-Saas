from __future__ import annotations

import time
import traceback
from typing import Any

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)
from services.backup_service import (
    start_auto_backup,
)
from system_database import (
    record_error,
    record_request,
)


def client_ip(
    request: Request,
) -> str:
    forwarded = request.headers.get(
        "x-forwarded-for",
        "",
    )

    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def request_identity(
    request: Request,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    user = getattr(
        request.state,
        "saas_user",
        None,
    )

    if not user:
        user = getattr(
            request.state,
            "security_user",
            None,
        )

    if not user:
        user = session_user(
            request.cookies.get(
                SESSION_COOKIE
            )
        )

    workspace = getattr(
        request.state,
        "workspace",
        None,
    )

    return user, workspace


class SystemObservabilityMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        start_auto_backup()

        if request.url.path.startswith(
            "/static/"
        ):
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(
                request
            )

            status_code = (
                response.status_code
            )

            return response

        except Exception as exc:
            user, workspace = (
                request_identity(
                    request
                )
            )

            record_error(
                error_type=(
                    type(exc).__name__
                ),
                message=str(exc),
                traceback_text=(
                    traceback.format_exc()
                ),
                method=request.method,
                path=request.url.path,
                user_id=(
                    user.get("user_id")
                    if user
                    else None
                ),
                workspace_id=(
                    workspace.get(
                        "workspace_id"
                    )
                    if workspace
                    else None
                ),
                client_ip=client_ip(
                    request
                ),
            )

            raise

        finally:
            duration_ms = (
                time.perf_counter()
                - started
            ) * 1000

            user, workspace = (
                request_identity(
                    request
                )
            )

            try:
                record_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    user_id=(
                        user.get("user_id")
                        if user
                        else None
                    ),
                    workspace_id=(
                        workspace.get(
                            "workspace_id"
                        )
                        if workspace
                        else None
                    ),
                    client_ip=client_ip(
                        request
                    ),
                )

            except Exception:
                pass