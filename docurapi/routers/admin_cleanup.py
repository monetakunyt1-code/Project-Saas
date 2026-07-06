from __future__ import annotations

from fastapi import APIRouter, Query

from docurapi.services.cleanup_service import run_storage_cleanup

router = APIRouter(prefix="/api/admin/cleanup", tags=["admin-cleanup"])


@router.post("/run")
def run_cleanup(
    secret: str = Query(...),
    dry_run: bool = Query(True),
):
    return run_storage_cleanup(secret=secret, dry_run=dry_run)
