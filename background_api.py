from __future__ import annotations

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    StreamingResponse,
)

from background_database import (
    BACKGROUND_DIRECTORY,
    create_background_job,
    delete_background_job,
    get_background_job,
    list_background_jobs,
    request_job_cancellation,
)
from config import MAX_FILE_SIZE
from services.auth_service import (
    require_user,
)
from services.background_job_manager import (
    submit_relay_job,
)
from services.workspace_service import (
    active_workspace_from_request,
)
from workspace_database import (
    claim_resource,
    remove_resource_owner,
)


BASE_DIR = Path(__file__).resolve().parent

TASK_CENTER_PAGE = (
    BASE_DIR
    / "templates"
    / "task_center.html"
)

router = APIRouter()


OPERATION_TARGETS = {
    "process": "/api/process",
    "batch": "/api/batch/process",
    "audit": "/api/audit/document",
    "journal": "/api/journal/build",
}

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "canceled",
}


def safe_filename(
    filename: str,
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "_",
        Path(filename).name,
    ).strip()

    return cleaned or "document.bin"


def authorize_job(
    job: dict[str, Any] | None,
    user: dict[str, Any],
    workspace: dict[str, Any],
) -> dict[str, Any]:
    if not job:
        raise HTTPException(
            status_code=404,
            detail=(
                "Pekerjaan tidak ditemukan."
            ),
        )

    if user.get("role") == "admin":
        return job

    if (
        job["workspace_id"]
        != workspace["workspace_id"]
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Pekerjaan tidak ditemukan "
                "pada workspace aktif."
            ),
        )

    return job


@router.get("/task-center")
def task_center_page() -> FileResponse:
    if not TASK_CENTER_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Halaman Task Center "
                "belum tersedia."
            ),
        )

    return FileResponse(
        TASK_CENTER_PAGE
    )


@router.post(
    "/api/background/submit/{operation}",
    status_code=202,
)
async def submit_background_operation(
    operation: str,
    request: Request,
    user=Depends(require_user),
) -> JSONResponse:
    target_path = OPERATION_TARGETS.get(
        operation
    )

    if not target_path:
        raise HTTPException(
            status_code=404,
            detail=(
                "Jenis pekerjaan tidak tersedia."
            ),
        )

    workspace = active_workspace_from_request(
        request,
        user,
    )

    job_id = uuid4().hex

    job_directory = (
        BACKGROUND_DIRECTORY
        / job_id
    )

    input_directory = (
        job_directory
        / "inputs"
    )

    input_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    form = await request.form()

    fields: list[
        tuple[str, str]
    ] = []

    files: list[
        dict[str, str]
    ] = []

    total_upload_size = 0

    try:
        for key, value in form.multi_items():
            if isinstance(value, UploadFile):
                original_name = (
                    value.filename
                    or "document.bin"
                )

                cleaned_name = safe_filename(
                    original_name
                )

                stored_name = (
                    f"{len(files) + 1:03d}_"
                    f"{cleaned_name}"
                )

                destination = (
                    input_directory
                    / stored_name
                )

                file_size = 0

                with destination.open(
                    "wb"
                ) as output:
                    while True:
                        chunk = await value.read(
                            1024 * 1024
                        )

                        if not chunk:
                            break

                        file_size += len(chunk)
                        total_upload_size += len(
                            chunk
                        )

                        if (
                            file_size
                            > MAX_FILE_SIZE
                        ):
                            raise HTTPException(
                                status_code=413,
                                detail=(
                                    f"File {original_name} "
                                    "melebihi batas ukuran."
                                ),
                            )

                        output.write(chunk)

                files.append(
                    {
                        "field_name": key,
                        "path": str(destination),
                        "filename": (
                            original_name
                        ),
                        "content_type": (
                            value.content_type
                            or (
                                "application/"
                                "octet-stream"
                            )
                        ),
                        "size_bytes": str(
                            file_size
                        ),
                    }
                )

            else:
                fields.append(
                    (
                        key,
                        str(value),
                    )
                )

        request_summary = {
            "field_names": sorted(
                {
                    key
                    for key, _ in fields
                }
            ),
            "files": [
                {
                    "field_name": item[
                        "field_name"
                    ],
                    "filename": item[
                        "filename"
                    ],
                    "size_bytes": int(
                        item["size_bytes"]
                    ),
                }
                for item in files
            ],
            "total_upload_size": (
                total_upload_size
            ),
        }

        job = create_background_job(
            job_id=job_id,
            user_id=user["user_id"],
            workspace_id=(
                workspace["workspace_id"]
            ),
            operation=operation,
            target_path=target_path,
            request_summary=(
                request_summary
            ),
        )

        claim_resource(
            resource_type="background_job",
            resource_id=job_id,
            workspace_id=(
                workspace["workspace_id"]
            ),
            owner_user_id=user["user_id"],
            metadata={
                "operation": operation,
                "target_path": target_path,
            },
        )

        runtime_payload = {
            "target_path": target_path,
            "fields": fields,
            "files": files,
            "cookie_header": (
                request.headers.get(
                    "cookie",
                    "",
                )
            ),
            "csrf_header": (
                request.headers.get(
                    "x-csrf-token",
                    "",
                )
            ),
            "job_directory": str(
                job_directory
            ),
        }

        submit_relay_job(
            job_id,
            runtime_payload,
        )

        return JSONResponse(
            status_code=202,
            content={
                "success": True,
                "message": (
                    "Pekerjaan dimasukkan "
                    "ke dalam antrean."
                ),
                "job_id": job_id,
                "job": job,
                "status_url": (
                    f"/api/background/jobs/"
                    f"{job_id}"
                ),
                "events_url": (
                    f"/api/background/jobs/"
                    f"{job_id}/events"
                ),
                "cancel_url": (
                    f"/api/background/jobs/"
                    f"{job_id}/cancel"
                ),
            },
        )

    except Exception:
        shutil.rmtree(
            job_directory,
            ignore_errors=True,
        )

        raise


@router.get("/api/background/jobs")
def background_jobs(
    request: Request,
    limit: int = 100,
    user=Depends(require_user),
) -> dict[str, Any]:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    return {
        "workspace": {
            "workspace_id": (
                workspace["workspace_id"]
            ),
            "name": workspace["name"],
        },
        "jobs": list_background_jobs(
            workspace_id=(
                workspace["workspace_id"]
            ),
            limit=limit,
        ),
    }


@router.get(
    "/api/background/jobs/{job_id}"
)
def background_job_detail(
    job_id: str,
    request: Request,
    user=Depends(require_user),
) -> dict[str, Any]:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    job = authorize_job(
        get_background_job(job_id),
        user,
        workspace,
    )

    return {
        "job": job
    }


@router.get(
    "/api/background/jobs/{job_id}/events"
)
async def background_job_events(
    job_id: str,
    request: Request,
    user=Depends(require_user),
) -> StreamingResponse:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    authorize_job(
        get_background_job(job_id),
        user,
        workspace,
    )

    async def event_stream():
        previous_signature = None

        while True:
            if await request.is_disconnected():
                break

            job = authorize_job(
                get_background_job(job_id),
                user,
                workspace,
            )

            signature = (
                job["status"],
                job["progress"],
                job["message"],
                job["updated_at"],
            )

            if signature != previous_signature:
                payload = json.dumps(
                    {
                        "job": job
                    },
                    ensure_ascii=False,
                )

                yield (
                    f"data: {payload}\n\n"
                )

                previous_signature = (
                    signature
                )

            if job["status"] in TERMINAL_STATUSES:
                break

            await asyncio.sleep(0.75)

    return StreamingResponse(
        event_stream(),
        media_type=(
            "text/event-stream"
        ),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/api/background/jobs/{job_id}/cancel"
)
def background_job_cancel(
    job_id: str,
    request: Request,
    user=Depends(require_user),
) -> dict[str, Any]:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    job = authorize_job(
        get_background_job(job_id),
        user,
        workspace,
    )

    if job["status"] in TERMINAL_STATUSES:
        return {
            "success": False,
            "message": (
                "Pekerjaan sudah selesai "
                "dan tidak dapat dibatalkan."
            ),
            "job": job,
        }

    updated = request_job_cancellation(
        job_id
    )

    return {
        "success": True,
        "message": (
            "Permintaan pembatalan diterima."
        ),
        "job": updated,
    }


@router.get(
    "/api/background/jobs/{job_id}/artifact"
)
def background_job_artifact(
    job_id: str,
    request: Request,
    user=Depends(require_user),
) -> FileResponse:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    job = authorize_job(
        get_background_job(job_id),
        user,
        workspace,
    )

    artifact_path = job.get(
        "artifact_path"
    )

    if not artifact_path:
        raise HTTPException(
            status_code=404,
            detail=(
                "Pekerjaan tidak memiliki "
                "file hasil."
            ),
        )

    path = Path(
        artifact_path
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "File hasil tidak tersedia."
            ),
        )

    return FileResponse(
        path,
        filename=(
            job.get(
                "artifact_filename"
            )
            or path.name
        ),
    )


@router.delete(
    "/api/background/jobs/{job_id}"
)
def background_job_delete(
    job_id: str,
    request: Request,
    user=Depends(require_user),
) -> dict[str, Any]:
    workspace = active_workspace_from_request(
        request,
        user,
    )

    job = authorize_job(
        get_background_job(job_id),
        user,
        workspace,
    )

    if job["status"] not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                "Pekerjaan aktif belum dapat dihapus."
            ),
        )

    job_directory = (
        BACKGROUND_DIRECTORY
        / job_id
    )

    shutil.rmtree(
        job_directory,
        ignore_errors=True,
    )

    delete_background_job(
        job_id
    )

    remove_resource_owner(
        "background_job",
        job_id,
    )

    return {
        "success": True,
        "message": (
            "Riwayat pekerjaan berhasil dihapus."
        ),
    }


@router.get("/api/background/health")
def background_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "operations": list(
            OPERATION_TARGETS.keys()
        ),
        "realtime_events": True,
        "cancellation": True,
    }