from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from docurapi.schemas.common import ProcessingResponse
from docurapi.services.processing_service import process_uploaded_document

router = APIRouter(prefix="/api", tags=["processing"])


@router.post("/process", response_model=ProcessingResponse)
async def process_document(
    file: UploadFile = File(...),
    mode: str = Form("format"),
    preset: str = Form("skripsi"),
):
    return await process_uploaded_document(file=file, mode=mode, preset=preset)
