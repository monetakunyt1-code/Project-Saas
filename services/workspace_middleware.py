from __future__ import annotations

import json
import re
from typing import Any

from fastapi import Request
from fastapi.responses import (
    JSONResponse,
    Response,
)
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from services.auth_service import (
    SESSION_COOKIE,
    session_user,
)
from services.workspace_service import (
    WORKSPACE_COOKIE,
    resolve_workspace,
)
from workspace_database import (
    claim_resource,
    get_resource_owner,
    list_resource_ids,
    remove_resource_owner,
    workspace_resource_counts,
)


LIST_RULES = {
    "/api/jobs": {
        "container": "jobs",
        "type": "job",
        "id": "job_id",
    },
    "/api/templates": {
        "container": "templates",
        "type": "template",
        "id": "template_id",
    },
    "/api/profiles": {
        "container": "profiles",
        "type": "profile",
        "id": "profile_id",
    },
    "/api/batches": {
        "container": "batches",
        "type": "batch",
        "id": "batch_id",
    },
    "/api/audits": {
        "container": "audits",
        "type": "audit",
        "id": "audit_id",
    },
    "/api/journal/jobs": {
        "container": "jobs",
        "type": "journal",
        "id": "job_id",
    },
}


CREATE_RULES = {
    ("POST", "/api/process"): {
        "type": "job",
        "ids": ["job_id"],
    },
    ("POST", "/api/templates"): {
        "type": "template",
        "ids": ["template_id"],
    },
    ("POST", "/api/profiles"): {
        "type": "profile",
        "ids": ["profile_id"],
    },
    ("POST", "/api/batch/process"): {
        "type": "batch",
        "ids": ["batch_id"],
    },
    ("POST", "/api/audit/document"): {
        "type": "audit",
        "ids": ["audit_id"],
    },
    ("POST", "/api/journal/build"): {
        "type": "journal",
        "ids": ["job_id"],
    },
}


DETAIL_PATTERNS = [
    (
        re.compile(
            r"^/api/journal/jobs/"
            r"([^/]+)(?:/.*)?$"
        ),
        "journal",
    ),
    (
        re.compile(
            r"^/api/jobs/"
            r"([^/]+)(?:/.*)?$"
        ),
        "job",
    ),
    (
        re.compile(
            r"^/api/templates/"
            r"([^/]+)(?:/.*)?$"
        ),
        "template",
    ),
    (
        re.compile(
            r"^/api/profiles/"
            r"([^/]+)(?:/.*)?$"
        ),
        "profile",
    ),
    (
        re.compile(
            r"^/api/batches/"
            r"([^/]+)(?:/.*)?$"
        ),
        "batch",
    ),
    (
        re.compile(
            r"^/api/audits/"
            r"([^/]+)(?:/.*)?$"
        ),
        "audit",
    ),
]


def find_identifier(
    payload: Any,
    field_names: list[str],
) -> str | None:
    if isinstance(payload, dict):
        for field_name in field_names:
            value = payload.get(
                field_name
            )

            if value is not None:
                return str(value)

        for value in payload.values():
            found = find_identifier(
                value,
                field_names,
            )

            if found:
                return found

    elif isinstance(payload, list):
        for item in payload:
            found = find_identifier(
                item,
                field_names,
            )

            if found:
                return found

    return None


def detail_resource(
    path: str,
) -> tuple[str, str] | None:
    for pattern, resource_type in (
        DETAIL_PATTERNS
    ):
        match = pattern.match(path)

        if match:
            return (
                resource_type,
                match.group(1),
            )

    return None


async def read_response_body(
    response: Any,
) -> bytes:
    chunks: list[bytes] = []

    async for chunk in response.body_iterator:
        if isinstance(chunk, str):
            chunks.append(
                chunk.encode("utf-8")
            )
        else:
            chunks.append(chunk)

    return b"".join(_docurapi_body_chunk_to_bytes(chunk) for chunk in chunks)



def _docurapi_body_chunk_to_bytes(chunk: object) -> bytes:
    """Normalisasi response-body chunk menjadi bytes."""

    if chunk is None:
        return b""

    if isinstance(chunk, bytes):
        return chunk

    if isinstance(chunk, bytearray):
        return bytes(chunk)

    if isinstance(chunk, memoryview):
        return chunk.tobytes()

    if isinstance(chunk, str):
        return chunk.encode("utf-8")

    if isinstance(chunk, tuple):
        # Bentuk umum iterator ASGI:
        # (body, more_body)
        if (
            len(chunk) == 2
            and isinstance(chunk[1], bool)
        ):
            return _docurapi_body_chunk_to_bytes(
                chunk[0]
            )

        return b"".join(
            _docurapi_body_chunk_to_bytes(part)
            for part in chunk
        )

    if isinstance(chunk, list):
        return b"".join(
            _docurapi_body_chunk_to_bytes(part)
            for part in chunk
        )

    raise TypeError(
        "Unsupported response body chunk type: "
        f"{type(chunk).__module__}."
        f"{type(chunk).__qualname__}"
    )


def rebuild_response(
    original_response: Any,
    body: bytes,
    media_type: str | None = None,
) -> Response:
    headers = dict(
        original_response.headers
    )

    headers.pop(
        "content-length",
        None,
    )

    return Response(
        content=body,
        status_code=(
            original_response.status_code
        ),
        headers=headers,
        media_type=(
            media_type
            or original_response.media_type
        ),
    )


def filter_list_payload(
    payload: dict[str, Any],
    rule: dict[str, str],
    workspace_id: str,
) -> dict[str, Any]:
    items = payload.get(
        rule["container"],
        [],
    )

    if not isinstance(items, list):
        return payload

    allowed_ids = set(
        list_resource_ids(
            workspace_id,
            rule["type"],
        )
    )

    payload[rule["container"]] = [
        item
        for item in items
        if isinstance(item, dict)
        and str(
            item.get(rule["id"], "")
        ) in allowed_ids
    ]

    return payload


def filter_dashboard(
    payload: dict[str, Any],
    workspace_id: str,
) -> dict[str, Any]:
    allowed_jobs = set(
        list_resource_ids(
            workspace_id,
            "job",
        )
    )

    recent_jobs = payload.get(
        "recent_jobs",
        [],
    )

    if isinstance(recent_jobs, list):
        payload["recent_jobs"] = [
            job
            for job in recent_jobs
            if isinstance(job, dict)
            and str(
                job.get("job_id", "")
            ) in allowed_jobs
        ]

    counts = workspace_resource_counts(
        workspace_id
    )

    summary = payload.get(
        "summary",
        {},
    )

    if not isinstance(summary, dict):
        summary = {}

    summary.update(
        {
            "jobs_total": counts.get(
                "job",
                0,
            ),
            "profiles_total": counts.get(
                "profile",
                0,
            ),
            "templates_total": counts.get(
                "template",
                0,
            ),
            "batches_total": counts.get(
                "batch",
                0,
            ),
            "audits_total": counts.get(
                "audit",
                0,
            ),
            "journals_total": counts.get(
                "journal",
                0,
            ),
            "scope": "workspace",
        }
    )

    payload["summary"] = summary

    return payload


class WorkspaceIsolationMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        user = session_user(
            request.cookies.get(
                SESSION_COOKIE
            )
        )

        if not user:
            return await call_next(
                request
            )

        workspace = resolve_workspace(
            user=user,
            requested_workspace_id=(
                request.cookies.get(
                    WORKSPACE_COOKIE
                )
            ),
        )

        request.state.workspace = workspace

        path = request.url.path
        method = request.method.upper()

        detail = detail_resource(
            path
        )

        if detail:
            resource_type, resource_id = detail

            owner = get_resource_owner(
                resource_type,
                resource_id,
            )

            is_system_admin = (
                user.get("role") == "admin"
            )

            if (
                owner
                and owner["workspace_id"]
                != workspace["workspace_id"]
                and not is_system_admin
            ):
                return JSONResponse(
                    status_code=404,
                    content={
                        "detail": (
                            "Resource tidak ditemukan "
                            "pada workspace aktif."
                        )
                    },
                )

            if (
                not owner
                and not is_system_admin
            ):
                return JSONResponse(
                    status_code=404,
                    content={
                        "detail": (
                            "Resource belum memiliki "
                            "kepemilikan workspace."
                        )
                    },
                )

        response = await call_next(
            request
        )

        content_type = response.headers.get(
            "content-type",
            "",
        )

        should_parse = (
            response.status_code
            >= 200
            and response.status_code
            < 300
            and "application/json"
            in content_type
            and (
                path in LIST_RULES
                or path == "/api/dashboard"
                or (
                    method,
                    path,
                ) in CREATE_RULES
                or (
                    detail is not None
                    and method == "DELETE"
                )
            )
        )

        if not should_parse:
            return response

        body = await read_response_body(
            response
        )

        try:
            payload = json.loads(
                body.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return rebuild_response(
                response,
                body,
            )

        is_system_admin = (
            user.get("role") == "admin"
        )

        list_rule = LIST_RULES.get(
            path
        )

        if (
            list_rule
            and isinstance(payload, dict)
            and not is_system_admin
        ):
            payload = filter_list_payload(
                payload,
                list_rule,
                workspace["workspace_id"],
            )

        if (
            path == "/api/dashboard"
            and isinstance(payload, dict)
            and not is_system_admin
        ):
            payload = filter_dashboard(
                payload,
                workspace["workspace_id"],
            )

        create_rule = CREATE_RULES.get(
            (
                method,
                path,
            )
        )

        if (
            create_rule
            and isinstance(payload, dict)
        ):
            resource_id = find_identifier(
                payload,
                create_rule["ids"],
            )

            if resource_id:
                claim_resource(
                    resource_type=(
                        create_rule["type"]
                    ),
                    resource_id=resource_id,
                    workspace_id=(
                        workspace[
                            "workspace_id"
                        ]
                    ),
                    owner_user_id=(
                        user["user_id"]
                    ),
                    metadata={
                        "endpoint": path,
                        "created_via": (
                            "workspace_middleware"
                        ),
                    },
                )

        if (
            detail
            and method == "DELETE"
        ):
            remove_resource_owner(
                detail[0],
                detail[1],
            )

        updated_body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        return rebuild_response(
            response,
            updated_body,
            media_type="application/json",
        )