from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
)

from config import (
    ALLOWED_EXTENSION,
    MAX_FILE_SIZE,
)
from services.academic_auditor import (
    DEFAULT_POLICIES,
    audit_document,
)
from services.academic_report_renderer import (
    render_academic_report,
)


BASE_DIR = Path(__file__).resolve().parent
AUDIT_PAGE = BASE_DIR / "templates" / "audit.html"
AUDIT_DIRECTORY = BASE_DIR / "storage" / "audits"

AUDIT_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

router = APIRouter()


def safe_filename(filename: str) -> str:
    name = Path(filename).name

    name = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "_",
        name,
    )

    return name.strip() or "document.docx"


async def save_upload(
    upload: UploadFile,
    destination: Path,
) -> int:
    content = await upload.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="File kosong.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Ukuran file melebihi batas 20 MB.",
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_bytes(
        content
    )

    return len(content)


def parse_optional_float(
    value: str,
) -> float | None:
    cleaned = value.strip()

    if not cleaned:
        return None

    try:
        return float(
            cleaned.replace(
                ",",
                ".",
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nilai '{value}' harus berupa angka."
            ),
        ) from exc


def metadata_path(
    audit_id: str,
) -> Path:
    return (
        AUDIT_DIRECTORY
        / audit_id
        / "metadata.json"
    )


def read_metadata(
    audit_id: str,
) -> dict[str, Any] | None:
    path = metadata_path(
        audit_id
    )

    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None


@router.get("/audit")
def audit_page() -> FileResponse:
    if not AUDIT_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail="Halaman audit belum tersedia.",
        )

    return FileResponse(
        AUDIT_PAGE
    )


@router.get("/api/audit/policies")
def audit_policies() -> dict[str, Any]:
    return {
        "policies": DEFAULT_POLICIES
    }


@router.post("/api/audit/document")
async def audit_upload(
    file: UploadFile = File(...),
    document_type: str = Form("skripsi"),
    font: str = Form(""),
    font_size: str = Form(""),
    line_spacing: str = Form(""),
    margin_top_cm: str = Form(""),
    margin_bottom_cm: str = Form(""),
    margin_left_cm: str = Form(""),
    margin_right_cm: str = Form(""),
) -> dict[str, Any]:
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail="File harus berformat .docx.",
        )

    audit_id = uuid4().hex
    safe_name = safe_filename(
        filename
    )

    audit_folder = (
        AUDIT_DIRECTORY
        / audit_id
    )

    audit_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_path = (
        audit_folder
        / f"source_{safe_name}"
    )

    json_path = (
        audit_folder
        / "report.json"
    )

    html_path = (
        audit_folder
        / "report.html"
    )

    metadata_file = (
        audit_folder
        / "metadata.json"
    )

    try:
        file_size = await save_upload(
            file,
            source_path,
        )

        custom_policy: dict[str, Any] = {}

        if font.strip():
            custom_policy[
                "font"
            ] = font.strip()

        numeric_fields = {
            "font_size": font_size,
            "line_spacing": line_spacing,
            "margin_top_cm": margin_top_cm,
            "margin_bottom_cm": margin_bottom_cm,
            "margin_left_cm": margin_left_cm,
            "margin_right_cm": margin_right_cm,
        }

        for key, raw_value in numeric_fields.items():
            parsed_value = parse_optional_float(
                raw_value
            )

            if parsed_value is not None:
                custom_policy[
                    key
                ] = parsed_value

        report = audit_document(
            file_path=source_path,
            document_type=document_type,
            custom_policy=custom_policy,
        )

        html_report = render_academic_report(
            report
        )

        json_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        html_path.write_text(
            html_report,
            encoding="utf-8",
        )

        metadata = {
            "audit_id": audit_id,
            "original_name": safe_name,
            "document_type": report[
                "document_type"
            ],
            "score": report[
                "score"
            ]["score"],
            "grade": report[
                "score"
            ]["grade"],
            "findings_total": report[
                "summary"
            ]["findings_total"],
            "file_size": file_size,
            "created_at": report[
                "audited_at"
            ],
            "json_path": str(
                json_path
            ),
            "html_path": str(
                html_path
            ),
            "source_path": str(
                source_path
            ),
        }

        metadata_file.write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "success": True,
            "audit_id": audit_id,
            "message": "Audit akademik selesai.",
            "score": report["score"],
            "summary": report["summary"],
            "findings_preview": report[
                "findings"
            ][:10],
            "html_report_url": (
                f"/api/audits/{audit_id}/html"
            ),
            "json_report_url": (
                f"/api/audits/{audit_id}/json"
            ),
        }

    except HTTPException:
        shutil.rmtree(
            audit_folder,
            ignore_errors=True,
        )
        raise

    except Exception as exc:
        shutil.rmtree(
            audit_folder,
            ignore_errors=True,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Audit gagal: {exc}",
        ) from exc


@router.get("/api/audits")
def audit_history() -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for folder in AUDIT_DIRECTORY.iterdir():
        if not folder.is_dir():
            continue

        metadata_file = (
            folder
            / "metadata.json"
        )

        if not metadata_file.exists():
            continue

        try:
            metadata = json.loads(
                metadata_file.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            continue

        audit_id = metadata.get(
            "audit_id"
        )

        metadata[
            "html_report_url"
        ] = (
            f"/api/audits/{audit_id}/html"
        )

        metadata[
            "json_report_url"
        ] = (
            f"/api/audits/{audit_id}/json"
        )

        records.append(
            metadata
        )

    records.sort(
        key=lambda item: item.get(
            "created_at",
            "",
        ),
        reverse=True,
    )

    return {
        "audits": records
    }


@router.get("/api/audits/{audit_id}/html")
def audit_html(
    audit_id: str,
) -> HTMLResponse:
    metadata = read_metadata(
        audit_id
    )

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Audit tidak ditemukan.",
        )

    html_path = Path(
        metadata["html_path"]
    )

    if not html_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Laporan HTML tidak tersedia.",
        )

    return HTMLResponse(
        content=html_path.read_text(
            encoding="utf-8"
        )
    )


@router.get("/api/audits/{audit_id}/json")
def audit_json(
    audit_id: str,
) -> FileResponse:
    metadata = read_metadata(
        audit_id
    )

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Audit tidak ditemukan.",
        )

    json_path = Path(
        metadata["json_path"]
    )

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Laporan JSON tidak tersedia.",
        )

    return FileResponse(
        json_path,
        filename=(
            f"Audit_DocuRapi_"
            f"{audit_id[:8]}.json"
        ),
        media_type="application/json",
    )


@router.delete("/api/audits/{audit_id}")
def audit_delete(
    audit_id: str,
) -> dict[str, Any]:
    audit_folder = (
        AUDIT_DIRECTORY
        / audit_id
    )

    if not audit_folder.exists():
        raise HTTPException(
            status_code=404,
            detail="Audit tidak ditemukan.",
        )

    shutil.rmtree(
        audit_folder,
        ignore_errors=True,
    )

    return {
        "success": True,
        "message": "Riwayat audit berhasil dihapus.",
    }