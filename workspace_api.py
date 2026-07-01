from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import (
    FileResponse,
    JSONResponse,
)

from services.auth_service import (
    require_user,
)
from services.workspace_service import (
    WORKSPACE_COOKIE,
    active_workspace_from_request,
    available_workspaces,
    create_workspace_invite,
    require_workspace_role,
    secure_cookie,
)
from workspace_database import (
    create_workspace,
    get_workspace,
    join_with_invite,
    list_workspace_members,
    remove_member,
    update_member_role,
    workspace_resource_counts,
)


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_PAGE = (
    BASE_DIR
    / "templates"
    / "workspaces.html"
)

router = APIRouter()


@router.get("/workspaces")
def workspace_page() -> FileResponse:
    if not WORKSPACE_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Halaman workspace belum tersedia."
            ),
        )

    return FileResponse(
        WORKSPACE_PAGE
    )


@router.get("/api/workspaces")
def workspace_list(
    request: Request,
    user=Depends(require_user),
) -> dict:
    active = active_workspace_from_request(
        request,
        user,
    )

    return {
        "workspaces": available_workspaces(
            user
        ),
        "active_workspace": active,
    }


@router.get("/api/workspaces/current")
def workspace_current(
    request: Request,
    user=Depends(require_user),
) -> dict:
    active = active_workspace_from_request(
        request,
        user,
    )

    return {
        "workspace": active,
        "resource_counts": (
            workspace_resource_counts(
                active["workspace_id"]
            )
        ),
    }


@router.post("/api/workspaces")
def workspace_create(
    name: str = Form(...),
    user=Depends(require_user),
) -> dict:
    try:
        workspace = create_workspace(
            name=name,
            owner_user_id=user["user_id"],
            workspace_type="team",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": "Workspace berhasil dibuat.",
        "workspace": workspace,
    }


@router.post("/api/workspaces/switch")
def workspace_switch(
    workspace_id: str = Form(...),
    user=Depends(require_user),
) -> JSONResponse:
    membership = require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="viewer",
    )

    workspace = get_workspace(
        workspace_id
    )

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace tidak ditemukan.",
        )

    workspace["role"] = membership["role"]

    response = JSONResponse(
        {
            "success": True,
            "message": (
                "Workspace aktif berhasil diubah."
            ),
            "workspace": workspace,
        }
    )

    response.set_cookie(
        key=WORKSPACE_COOKIE,
        value=workspace_id,
        max_age=365 * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
        path="/",
    )

    return response


@router.post(
    "/api/workspaces/{workspace_id}/invites"
)
def workspace_invite_create(
    workspace_id: str,
    role: str = Form("member"),
    expires_hours: int = Form(72),
    max_uses: int = Form(1),
    user=Depends(require_user),
) -> dict:
    require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="admin",
    )

    try:
        token = create_workspace_invite(
            workspace_id=workspace_id,
            created_by=user["user_id"],
            role=role,
            expires_hours=expires_hours,
            max_uses=max_uses,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Kode undangan berhasil dibuat."
        ),
        "invite_code": token,
        "role": role,
        "expires_hours": expires_hours,
        "max_uses": max_uses,
    }


@router.post("/api/workspaces/join")
def workspace_join(
    invite_code: str = Form(...),
    user=Depends(require_user),
) -> JSONResponse:
    try:
        workspace = join_with_invite(
            raw_token=invite_code,
            user_id=user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    response = JSONResponse(
        {
            "success": True,
            "message": (
                "Berhasil bergabung ke workspace."
            ),
            "workspace": workspace,
        }
    )

    response.set_cookie(
        key=WORKSPACE_COOKIE,
        value=workspace["workspace_id"],
        max_age=365 * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
        path="/",
    )

    return response


@router.get(
    "/api/workspaces/{workspace_id}/members"
)
def workspace_members(
    workspace_id: str,
    user=Depends(require_user),
) -> dict:
    require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="viewer",
    )

    return {
        "members": list_workspace_members(
            workspace_id
        )
    }


@router.post(
    "/api/workspaces/{workspace_id}/members/"
    "{member_user_id}/role"
)
def workspace_member_role(
    workspace_id: str,
    member_user_id: str,
    role: str = Form(...),
    user=Depends(require_user),
) -> dict:
    require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="admin",
    )

    try:
        update_member_role(
            workspace_id=workspace_id,
            user_id=member_user_id,
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Peran anggota berhasil diperbarui."
        ),
    }


@router.delete(
    "/api/workspaces/{workspace_id}/members/"
    "{member_user_id}"
)
def workspace_member_remove(
    workspace_id: str,
    member_user_id: str,
    user=Depends(require_user),
) -> dict:
    require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="admin",
    )

    try:
        remove_member(
            workspace_id=workspace_id,
            user_id=member_user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "message": (
            "Anggota berhasil dikeluarkan."
        ),
    }


@router.get(
    "/api/workspaces/{workspace_id}/summary"
)
def workspace_summary(
    workspace_id: str,
    user=Depends(require_user),
) -> dict:
    require_workspace_role(
        workspace_id=workspace_id,
        user_id=user["user_id"],
        minimum_role="viewer",
    )

    return {
        "workspace": get_workspace(
            workspace_id
        ),
        "resource_counts": (
            workspace_resource_counts(
                workspace_id
            )
        ),
    }