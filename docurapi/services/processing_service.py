from __future__ import annotations

import json
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from docurapi.core.logging_config import logger
from docurapi.core.settings import settings
from docurapi.db.jobs_repository import complete_job, create_job, fail_job
from docurapi.services.document_analyzer import analyze_document
from docurapi.services.document_formatter import apply_document_format
from docurapi.services.file_service import safe_filename, save_upload, validate_docx
from docurapi.services.journal_service import create_journal_draft


PRICE_TABLE = {
    "analyze": 7000,
    "format": 12000,
    "journal": 20000,
}


def get_processing_price(mode: str) -> int:
    return PRICE_TABLE.get(mode, PRICE_TABLE["format"])


def generate_unique_payment_amount(base_amount: int) -> tuple[int, int]:
    unique_code = secrets.randbelow(
        settings.UNIQUE_CODE_MAX - settings.UNIQUE_CODE_MIN + 1
    ) + settings.UNIQUE_CODE_MIN

    return base_amount + unique_code, unique_code


def calculate_invoice_expiry() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(hours=settings.PAYMENT_EXPIRY_HOURS)
    ).isoformat()


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def process_uploaded_document(
    file: UploadFile,
    mode: str = "format",
    preset: str = "skripsi",
) -> dict[str, Any]:
    validate_docx(file)

    normalized_mode = mode.lower().strip()

    if normalized_mode not in {"format", "analyze", "journal"}:
        raise HTTPException(
            status_code=400,
            detail="Mode pemrosesan tidak valid.",
        )

    job_id = uuid4().hex
    access_token = secrets.token_urlsafe(32)
    original_name = safe_filename(file.filename or "document.docx")
    base_amount = get_processing_price(normalized_mode)
    amount, unique_code = generate_unique_payment_amount(base_amount)
    invoice_expires_at = calculate_invoice_expiry()

    input_path = settings.UPLOAD_DIR / f"{job_id}_{original_name}"

    output_prefix = {
        "format": "rapi",
        "analyze": "analisis",
        "journal": "draft_jurnal",
    }[normalized_mode]

    output_name = f"{output_prefix}_{Path(original_name).stem}.docx"
    output_path = settings.OUTPUT_DIR / f"{job_id}_{output_name}"
    report_path = settings.REPORT_DIR / f"{job_id}.json"

    try:
        input_size = await save_upload(file, input_path)

        create_job(
            job_id=job_id,
            original_name=original_name,
            mode=normalized_mode,
            preset=preset,
            input_size=input_size,
            amount=amount,
            access_token=access_token,
            base_amount=base_amount,
            unique_code=unique_code,
            invoice_expires_at=invoice_expires_at,
        )

        analysis_before = analyze_document(input_path)

        if normalized_mode == "format":
            processing_result = apply_document_format(input_path, output_path, preset)
        elif normalized_mode == "journal":
            processing_result = create_journal_draft(input_path, output_path)
        else:
            shutil.copy2(input_path, output_path)
            processing_result = {
                "message": "Dokumen dianalisis tanpa perubahan isi file."
            }

        analysis_after = analyze_document(output_path)

        report_payload = {
            "job_id": job_id,
            "original_name": original_name,
            "mode": normalized_mode,
            "preset": preset,
            "payment_status": "unpaid",
            "amount": amount,
            "base_amount": base_amount,
            "unique_code": unique_code,
            "invoice_expires_at": invoice_expires_at,
            "analysis_before": analysis_before,
            "processing": processing_result,
            "analysis_after": analysis_after,
        }

        write_report(report_path, report_payload)

        complete_job(
            job_id=job_id,
            output_name=output_name,
            output_path=str(output_path),
            report_path=str(report_path),
        )

        input_path.unlink(missing_ok=True)

        logger.info("Job %s selesai. Mode=%s Payment=unpaid", job_id, normalized_mode)

        return {
            "success": True,
            "job_id": job_id,
            "message": "Dokumen berhasil diproses. Preview tersedia, download dibuka setelah pembayaran.",
            "preview_url": f"/api/jobs/{job_id}/preview?token={access_token}",
            "report_url": f"/api/jobs/{job_id}/report?token={access_token}",
            "payment_url": f"/api/payments/{job_id}/checkout?token={access_token}",
            "download_url": None,
            "payment_status": "unpaid",
            "amount": amount,
            "base_amount": base_amount,
            "unique_code": unique_code,
            "invoice_expires_at": invoice_expires_at,
            "summary": analysis_after["summary"],
        }

    except HTTPException:
        input_path.unlink(missing_ok=True)
        raise

    except Exception as exc:
        logger.exception("Job %s gagal.", job_id)

        try:
            fail_job(job_id, str(exc))
        except Exception:
            logger.exception("Gagal memperbarui status job.")

        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=500,
            detail=f"Pemrosesan gagal: {exc}",
        ) from exc
