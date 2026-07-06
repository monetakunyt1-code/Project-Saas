from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from docurapi.core.settings import settings

router = APIRouter(tags=["frontend"])


@router.get("/")
def frontend_home():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "index.html")
