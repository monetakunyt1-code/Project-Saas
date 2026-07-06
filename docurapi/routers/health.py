from __future__ import annotations

from fastapi import APIRouter

from docurapi.core.settings import settings
from docurapi.schemas.common import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
