from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

from docurapi.core.settings import settings


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name.strip() or "document.docx"


def validate_docx(upload: UploadFile) -> None:
    filename = upload.filename or ""

    if Path(filename).suffix.lower() != settings.ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail="File harus berformat .docx.",
        )


async def save_upload(upload: UploadFile, destination: Path) -> int:
    content = await upload.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="File kosong.",
        )

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Ukuran file melebihi batas 20 MB.",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    return len(content)
