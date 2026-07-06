from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from docurapi.routers.admin_auth import get_admin_secret
from docurapi.services.cleanup_service import run_storage_cleanup

router = APIRouter(prefix="/api/admin/cleanup", tags=["admin-cleanup"])


@router.post("/run")
def run_cleanup(
    admin_secret: str = Depends(get_admin_secret),
    dry_run: bool = Query(True),
):
    return run_storage_cleanup(secret=admin_secret, dry_run=dry_run)
