from __future__ import annotations

from fastapi import APIRouter, Depends

from docurapi.routers.admin_auth import get_admin_secret
from docurapi.services.system_readiness_service import get_system_readiness

router = APIRouter(prefix="/api/admin/system", tags=["admin-system"])


@router.get("/readiness")
def readiness(admin_secret: str = Depends(get_admin_secret)):
    return get_system_readiness(secret=admin_secret)
