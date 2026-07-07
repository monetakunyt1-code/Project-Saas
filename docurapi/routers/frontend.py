from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

from docurapi.core.settings import settings

router = APIRouter(tags=["frontend"])


@router.get("/")
def frontend_home():
    return RedirectResponse(url="/mvp", status_code=302)


@router.get("/mvp")
def frontend_mvp():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "index.html")


@router.get("/admin")
def frontend_admin():
    return RedirectResponse(url="/admin-mvp", status_code=302)


@router.get("/admin-mvp")
def frontend_admin_mvp():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "admin.html")


@router.get("/status-mvp")
def frontend_status_mvp():
    return FileResponse(settings.BASE_DIR / "static" / "app" / "status.html")
