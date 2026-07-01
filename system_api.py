from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
)
from fastapi.responses import (
    FileResponse,
)

from services.auth_service import (
    require_admin,
)
from services.backup_service import (
    create_backup,
    delete_backup,
    get_backup_record,
    list_backups,
    prune_backups,
    restore_plan,
    verify_backup,
)
from services.system_health_service import (
    build_health_snapshot,
)
from system_database import (
    list_errors,
    list_system_events,
    request_summary,
    resolve_error,
)


BASE_DIR = Path(__file__).resolve().parent

SYSTEM_HEALTH_PAGE = (
    BASE_DIR
    / "templates"
    / "system_health.html"
)

router = APIRouter()


def public_backup(
    record: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {
            "folder_path",
            "archive_path",
        }
    }


@router.get("/system-health")
def system_health_page() -> FileResponse:
    if not SYSTEM_HEALTH_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Halaman System Health "
                "belum tersedia."
            ),
        )

    return FileResponse(
        SYSTEM_HEALTH_PAGE
    )


@router.get("/api/system/health")
def public_system_health() -> dict[str, Any]:
    snapshot = build_health_snapshot(
        include_sensitive_paths=False
    )

    return {
        "status": snapshot["status"],
        "checked_at": (
            snapshot["checked_at"]
        ),
        "application": (
            snapshot["application"]
        ),
        "database_count": (
            snapshot["database_count"]
        ),
        "database_errors": (
            snapshot["database_errors"]
        ),
        "unresolved_errors": (
            snapshot["unresolved_errors"]
        ),
        "backup_available": (
            snapshot["backups"]["total"]
            > 0
        ),
    }


@router.get("/api/system/health/detail")
def detailed_system_health(
    admin=Depends(require_admin),
) -> dict[str, Any]:
    snapshot = build_health_snapshot(
        include_sensitive_paths=True
    )

    snapshot["requested_by"] = (
        admin["email"]
    )

    return snapshot


@router.get("/api/system/metrics")
def system_metrics(
    hours: int = 24,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "metrics": request_summary(
            hours=hours
        ),
        "requested_by": admin["email"],
    }


@router.get("/api/system/errors")
def system_errors(
    limit: int = 100,
    unresolved_only: bool = False,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "errors": list_errors(
            limit=limit,
            unresolved_only=(
                unresolved_only
            ),
        ),
        "requested_by": admin["email"],
    }


@router.post(
    "/api/system/errors/{error_id}/resolve"
)
def system_error_resolve(
    error_id: int,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    updated = resolve_error(
        error_id
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Error tidak ditemukan.",
        )

    return {
        "success": True,
        "message": (
            "Error ditandai selesai."
        ),
        "requested_by": admin["email"],
    }


@router.get("/api/system/events")
def system_events(
    limit: int = 100,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "events": list_system_events(
            limit=limit
        ),
        "requested_by": admin["email"],
    }


@router.get("/api/system/backups")
def system_backups(
    admin=Depends(require_admin),
) -> dict[str, Any]:
    return {
        "backups": [
            public_backup(record)
            for record in list_backups()
        ],
        "requested_by": admin["email"],
    }


@router.post("/api/system/backups")
def system_backup_create(
    label: str = Form("manual"),
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        record = create_backup(
            label=label,
            initiated_by=admin["email"],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Backup gagal dibuat: "
                + str(exc)
            ),
        ) from exc

    return {
        "success": True,
        "message": (
            "Backup berhasil dibuat."
        ),
        "backup": public_backup(record),
    }


@router.get(
    "/api/system/backups/{backup_id}/download"
)
def system_backup_download(
    backup_id: str,
    admin=Depends(require_admin),
) -> FileResponse:
    try:
        record = get_backup_record(
            backup_id
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    archive_path = Path(
        record["archive_path"]
    )

    if not archive_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Arsip ZIP backup "
                "tidak ditemukan."
            ),
        )

    return FileResponse(
        archive_path,
        filename=(
            f"DocuRapi_Backup_"
            f"{backup_id}.zip"
        ),
        media_type="application/zip",
    )


@router.get(
    "/api/system/backups/{backup_id}/verify"
)
def system_backup_verify(
    backup_id: str,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        result = verify_backup(
            backup_id
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    result["requested_by"] = (
        admin["email"]
    )

    return result


@router.get(
    "/api/system/backups/{backup_id}/restore-plan"
)
def system_backup_restore_plan(
    backup_id: str,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        plan = restore_plan(
            backup_id
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    plan["restore_command"] = (
        ".\\.venv\\Scripts\\python.exe "
        ".\\system_maintenance.py restore "
        f"--backup-id {backup_id} --apply"
    )

    plan["requested_by"] = (
        admin["email"]
    )

    return plan


@router.delete(
    "/api/system/backups/{backup_id}"
)
def system_backup_delete(
    backup_id: str,
    admin=Depends(require_admin),
) -> dict[str, Any]:
    try:
        delete_backup(
            backup_id
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Backup berhasil dihapus."
        ),
        "requested_by": admin["email"],
    }


@router.post("/api/system/backups/prune")
def system_backup_prune(
    keep: int = Form(14),
    admin=Depends(require_admin),
) -> dict[str, Any]:
    result = prune_backups(
        keep=keep
    )

    result["success"] = True
    result["requested_by"] = (
        admin["email"]
    )

    return result