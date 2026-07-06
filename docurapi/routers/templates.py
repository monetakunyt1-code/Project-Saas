from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from docurapi.core.settings import settings
from docurapi.db.templates_repository import (
    delete_template,
    list_templates,
    register_template,
    remove_template_file,
)
from docurapi.services.file_service import safe_filename, save_upload, validate_docx

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def templates_list() -> dict[str, Any]:
    return {
        "templates": list_templates()
    }


@router.post("")
async def upload_template(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    institution_name: str = Form(""),
    document_type: str = Form("skripsi"),
) -> dict[str, Any]:
    validate_docx(file)

    template_id = uuid4().hex
    original_name = safe_filename(file.filename or "template.docx")
    destination = settings.TEMPLATE_DIR / f"{template_id}_{original_name}"

    await save_upload(file, destination)

    register_template(
        template_id=template_id,
        template_name=template_name.strip(),
        institution_name=institution_name.strip(),
        document_type=document_type.strip(),
        file_name=original_name,
        file_path=str(destination),
    )

    return {
        "success": True,
        "template_id": template_id,
        "message": "Template berhasil disimpan.",
    }


@router.delete("/{template_id}")
def remove_template(template_id: str) -> dict[str, Any]:
    template = delete_template(template_id)

    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template tidak ditemukan.",
        )

    remove_template_file(template)

    return {
        "success": True,
        "message": "Template berhasil dihapus.",
    }
