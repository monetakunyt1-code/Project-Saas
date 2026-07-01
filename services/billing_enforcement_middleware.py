from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request

from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)
from services.billing_enforcement_service import (
    admin_bypass_enabled,
    enforcement_mode,
    finalize_processing_access,
    operation_from_path,
    release_processing_access,
    reserve_processing_access,
    service_code_for_path,
)


class BillingEnforcementMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        mode = enforcement_mode()

        if mode == "disabled":
            return await call_next(
                request
            )

        if request.method.upper() not in {
            "POST",
            "PUT",
            "PATCH",
        }:
            return await call_next(
                request
            )

        service_code = service_code_for_path(
            request.url.path
        )

        operation = operation_from_path(
            request.url.path
        )

        if not service_code:
            if (
                mode == "strict"
                and request.url.path.startswith(
                    "/api/background/submit/"
                )
            ):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "code": (
                            "UNMAPPED_BILLING_OPERATION"
                        ),
                        "message": (
                            "Operasi pemrosesan belum "
                            "memiliki pemetaan billing."
                        ),
                        "operation": operation,
                    },
                )

            return await call_next(
                request
            )

        user = getattr(
            request.state,
            "saas_user",
            None,
        )

        if not user:
            session_token = request.cookies.get(
                SESSION_COOKIE
            )

            if session_token:
                user = session_user(
                    session_token
                )

        if not user:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "code": "LOGIN_REQUIRED",
                    "message": (
                        "Silakan login sebelum "
                        "memproses dokumen."
                    ),
                    "login_url": "/login",
                },
            )

        user_id_value = (
            user.get("user_id")
            or user.get("id")
            or user.get("uuid")
        )

        if user_id_value is None:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "code": (
                        "USER_ID_UNAVAILABLE"
                    ),
                    "message": (
                        "Identitas pengguna "
                        "tidak tersedia."
                    ),
                },
            )

        user_id = str(
            user_id_value
        )

        user_role = str(
            user.get("role")
            or ""
        ).lower()

        is_admin = (
            user_role == "admin"
            or bool(
                user.get("is_admin")
            )
        )

        if (
            is_admin
            and admin_bypass_enabled()
        ):
            response = await call_next(
                request
            )

            response.headers[
                "X-DocuRapi-Billing"
            ] = "admin-bypass"

            return response

        if mode == "monitor":
            response = await call_next(
                request
            )

            response.headers[
                "X-DocuRapi-Billing"
            ] = "monitor"

            response.headers[
                "X-DocuRapi-Service-Code"
            ] = service_code

            return response

        request_reference = (
            request.headers.get(
                "X-Request-ID"
            )
            or uuid4().hex
        )

        try:
            reservation = (
                reserve_processing_access(
                    user_id=user_id,
                    service_code=service_code,
                    operation=operation,
                    request_reference=(
                        request_reference
                    ),
                )
            )

        except ValueError:
            return JSONResponse(
                status_code=402,
                content={
                    "success": False,
                    "code": (
                        "PAYMENT_REQUIRED"
                    ),
                    "message": (
                        "Hak pemrosesan tidak tersedia. "
                        "Silakan membeli layanan "
                        "atau menukarkan kredit."
                    ),
                    "operation": operation,
                    "service_code": (
                        service_code
                    ),
                    "checkout_url": (
                        "/billing?service="
                        + service_code
                    ),
                },
            )

        reservation_token = reservation[
            "reservation_token"
        ]

        request.state.billing_reservation = (
            reservation
        )

        try:
            response = await call_next(
                request
            )

        except Exception:
            try:
                release_processing_access(
                    reservation_token=(
                        reservation_token
                    ),
                    reason=(
                        "unhandled_processing_error"
                    ),
                    user_id=user_id,
                )
            except Exception:
                pass

            raise

        if (
            response.status_code >= 200
            and response.status_code < 300
        ):
            processing_reference = (
                response.headers.get(
                    "X-DocuRapi-Job-ID"
                )
                or response.headers.get(
                    "X-Job-ID"
                )
                or request_reference
            )

            try:
                finalize_processing_access(
                    reservation_token=(
                        reservation_token
                    ),
                    processing_reference=(
                        processing_reference
                    ),
                    user_id=user_id,
                )

                response.headers[
                    "X-DocuRapi-Billing"
                ] = "consumed"

            except Exception:
                try:
                    release_processing_access(
                        reservation_token=(
                            reservation_token
                        ),
                        reason=(
                            "billing_finalize_failed"
                        ),
                        user_id=user_id,
                    )
                except Exception:
                    pass

                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "code": (
                            "BILLING_FINALIZE_FAILED"
                        ),
                        "message": (
                            "Proses dibuat, tetapi "
                            "finalisasi billing gagal."
                        ),
                    },
                )

        else:
            try:
                release_processing_access(
                    reservation_token=(
                        reservation_token
                    ),
                    reason=(
                        "processing_http_status_"
                        + str(
                            response.status_code
                        )
                    ),
                    user_id=user_id,
                )

                response.headers[
                    "X-DocuRapi-Billing"
                ] = "released"

            except Exception:
                response.headers[
                    "X-DocuRapi-Billing"
                ] = "release-failed"

        response.headers[
            "X-DocuRapi-Service-Code"
        ] = service_code

        response.headers[
            "X-DocuRapi-Reservation"
        ] = reservation_token

        return response
