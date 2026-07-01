from __future__ import annotations

import json
import re
import shutil
import zipfile
from collections import Counter
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
from pydantic import BaseModel, Field

from config import (
    ALLOWED_EXTENSION,
    MAX_FILE_SIZE,
    OUTPUT_DIR,
    REPORT_DIR,
    UPLOAD_DIR,
)
from database import (
    complete_job,
    create_job,
    fail_job,
    get_job,
    get_template,
    list_jobs,
    list_templates,
)
from logger import logger
from services.batch_manager import (
    BATCH_DIRECTORY,
    create_batch_record,
    delete_batch_record,
    get_batch,
    list_batches,
)
from services.document_analyzer import analyze_document
from services.final_formatter import format_document
from services.format_rules import (
    FormatRuleError,
    merge_format_rules,
)
from services.journal_converter import convert_to_journal
from services.profile_manager import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)
from services.report_renderer import render_report_html
from services.template_manager import extract_template_rules


BASE_DIR = Path(__file__).resolve().parent
ADVANCED_PAGE = BASE_DIR / "templates" / "advanced.html"

MAX_BATCH_FILES = 20
MAX_BATCH_SIZE = 200 * 1024 * 1024

router = APIRouter()


class ProfilePayload(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
    )
    description: str = Field(
        default="",
        max_length=500,
    )
    rules: dict[str, Any]


def safe_filename(filename: str) -> str:
    clean_name = Path(filename).name

    clean_name = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "_",
        clean_name,
    )

    return clean_name.strip() or "document.docx"


def validate_docx(upload: UploadFile) -> None:
    filename = upload.filename or ""

    if Path(filename).suffix.lower() != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File {filename or 'tanpa nama'} "
                "harus menggunakan format .docx."
            ),
        )


async def save_upload(
    upload: UploadFile,
    destination: Path,
) -> int:
    content = await upload.read()

    if not content:
        raise ValueError("File kosong.")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError(
            "Ukuran satu file melebihi batas 20 MB."
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_bytes(content)
    return len(content)


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def resolve_format_rules(
    profile_id: str,
    template_id: str,
    custom_rules_json: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    profile = None
    profile_rules = None

    if profile_id:
        profile = get_profile(profile_id)

        if not profile:
            raise ValueError(
                "Profil format tidak ditemukan."
            )

        profile_rules = profile.get(
            "rules",
            {},
        )

    template = None
    template_rules = None

    if template_id:
        template = get_template(template_id)

        if not template:
            raise ValueError(
                "Template dokumen tidak ditemukan."
            )

        template_rules = extract_template_rules(
            template["file_path"]
        )

    custom_rules: dict[str, Any] = {}

    if custom_rules_json.strip():
        try:
            parsed_rules = json.loads(
                custom_rules_json
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Aturan manual harus menggunakan JSON yang valid."
            ) from exc

        if not isinstance(parsed_rules, dict):
            raise ValueError(
                "Aturan manual harus berupa objek JSON."
            )

        custom_rules = parsed_rules

    merged_rules = merge_format_rules(
        template_rules,
        profile_rules,
        custom_rules,
    )

    return (
        merged_rules,
        profile,
        template,
    )


@router.get("/advanced")
def advanced_page() -> FileResponse:
    if not ADVANCED_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail="Halaman fitur lanjutan belum tersedia.",
        )

    return FileResponse(ADVANCED_PAGE)


@router.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    jobs = list_jobs(limit=100)
    profiles = list_profiles()
    templates = list_templates()
    batches = list_batches()

    status_counter = Counter(
        job.get("status", "unknown")
        for job in jobs
    )

    mode_counter = Counter(
        job.get("mode", "unknown")
        for job in jobs
    )

    completed_jobs = [
        job
        for job in jobs
        if job.get("status") == "completed"
    ]

    failed_jobs = [
        job
        for job in jobs
        if job.get("status") == "failed"
    ]

    total_output_size = 0

    for job in completed_jobs:
        output_path = job.get("output_path")

        if not output_path:
            continue

        path = Path(output_path)

        if path.exists():
            total_output_size += path.stat().st_size

    total_batch_success = sum(
        int(batch.get("success_count", 0))
        for batch in batches
    )

    total_batch_failed = sum(
        int(batch.get("failed_count", 0))
        for batch in batches
    )

    recent_jobs = []

    for job in jobs[:10]:
        recent_jobs.append(
            {
                "job_id": job.get("job_id"),
                "original_name": job.get("original_name"),
                "mode": job.get("mode"),
                "preset": job.get("preset"),
                "status": job.get("status"),
                "created_at": job.get("created_at"),
                "download_url": (
                    f"/api/jobs/{job['job_id']}/download"
                    if job.get("status") == "completed"
                    else None
                ),
                "json_report_url": (
                    f"/api/jobs/{job['job_id']}/report"
                    if job.get("status") == "completed"
                    else None
                ),
                "html_report_url": (
                    f"/api/jobs/{job['job_id']}/report/html"
                    if job.get("status") == "completed"
                    else None
                ),
            }
        )

    return {
        "summary": {
            "jobs_total": len(jobs),
            "jobs_completed": len(completed_jobs),
            "jobs_failed": len(failed_jobs),
            "profiles_total": len(profiles),
            "templates_total": len(templates),
            "batches_total": len(batches),
            "batch_files_success": total_batch_success,
            "batch_files_failed": total_batch_failed,
            "output_size_bytes": total_output_size,
        },
        "status_distribution": dict(status_counter),
        "mode_distribution": dict(mode_counter),
        "recent_jobs": recent_jobs,
    }


@router.get("/api/profiles")
def profiles_index() -> dict[str, Any]:
    return {
        "profiles": list_profiles()
    }


@router.post("/api/profiles")
def profiles_create(
    payload: ProfilePayload,
) -> dict[str, Any]:
    try:
        profile = create_profile(
            name=payload.name,
            description=payload.description,
            rules=payload.rules,
        )
    except (
        ValueError,
        FormatRuleError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "profile": profile,
    }


@router.put("/api/profiles/{profile_id}")
def profiles_update(
    profile_id: str,
    payload: ProfilePayload,
) -> dict[str, Any]:
    try:
        profile = update_profile(
            profile_id=profile_id,
            name=payload.name,
            description=payload.description,
            rules=payload.rules,
        )
    except (
        ValueError,
        FormatRuleError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profil format tidak ditemukan.",
        )

    return {
        "success": True,
        "profile": profile,
    }


@router.delete("/api/profiles/{profile_id}")
def profiles_delete(
    profile_id: str,
) -> dict[str, Any]:
    profile = delete_profile(profile_id)

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profil format tidak ditemukan.",
        )

    return {
        "success": True,
        "message": "Profil format berhasil dihapus.",
    }


@router.get("/api/jobs/{job_id}/report/html")
def job_report_html(
    job_id: str,
) -> HTMLResponse:
    job = get_job(job_id)

    if not job or job.get("status") != "completed":
        raise HTTPException(
            status_code=404,
            detail="Laporan pekerjaan tidak ditemukan.",
        )

    report_path_value = job.get("report_path")

    if not report_path_value:
        raise HTTPException(
            status_code=404,
            detail="Path laporan tidak tersedia.",
        )

    report_path = Path(report_path_value)

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File laporan tidak tersedia.",
        )

    try:
        payload = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="Laporan JSON tidak dapat dibaca.",
        ) from exc

    html = render_report_html(payload)

    return HTMLResponse(
        content=html,
        status_code=200,
    )


@router.post("/api/batch/process")
async def batch_process(
    files: list[UploadFile] = File(...),
    mode: str = Form("format"),
    preset: str = Form("skripsi"),
    profile_id: str = Form(""),
    template_id: str = Form(""),
    custom_rules_json: str = Form(""),
    include_toc: bool = Form(True),
    include_table_list: bool = Form(True),
    include_figure_list: bool = Form(True),
    include_appendix_list: bool = Form(True),
    include_page_numbers: bool = Form(True),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Sedikitnya satu dokumen harus dipilih.",
        )

    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch maksimal berisi "
                f"{MAX_BATCH_FILES} dokumen."
            ),
        )

    normalized_mode = mode.lower().strip()

    if normalized_mode not in {
        "format",
        "analyze",
        "journal",
    }:
        raise HTTPException(
            status_code=400,
            detail="Mode batch tidak valid.",
        )

    try:
        (
            merged_rules,
            selected_profile,
            selected_template,
        ) = resolve_format_rules(
            profile_id=profile_id,
            template_id=template_id,
            custom_rules_json=custom_rules_json,
        )
    except (
        ValueError,
        FormatRuleError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    batch_id = uuid4().hex
    batch_work_directory = (
        BATCH_DIRECTORY
        / f"work_{batch_id}"
    )

    batch_work_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    zip_path = (
        BATCH_DIRECTORY
        / f"docurapi_batch_{batch_id}.zip"
    )

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    total_size = 0

    try:
        for position, upload in enumerate(
            files,
            start=1,
        ):
            original_name = safe_filename(
                upload.filename or f"dokumen_{position}.docx"
            )

            job_id = uuid4().hex
            input_path = (
                UPLOAD_DIR
                / f"{job_id}_{original_name}"
            )

            output_prefix = {
                "format": "rapi",
                "analyze": "analisis",
                "journal": "draft_jurnal",
            }[normalized_mode]

            output_name = (
                f"{output_prefix}_"
                f"{Path(original_name).stem}.docx"
            )

            output_path = (
                OUTPUT_DIR
                / f"{job_id}_{output_name}"
            )

            report_path = (
                REPORT_DIR
                / f"{job_id}.json"
            )

            job_created = False

            try:
                validate_docx(upload)

                input_size = await save_upload(
                    upload,
                    input_path,
                )

                total_size += input_size

                if total_size > MAX_BATCH_SIZE:
                    raise ValueError(
                        "Total ukuran batch melebihi batas 200 MB."
                    )

                create_job(
                    job_id=job_id,
                    original_name=original_name,
                    mode=normalized_mode,
                    preset=preset,
                    input_size=input_size,
                )

                job_created = True

                analysis_before = analyze_document(
                    input_path
                )

                if normalized_mode == "format":
                    processing_result = format_document(
                        input_path=input_path,
                        output_path=output_path,
                        preset=preset,
                        custom_rules=merged_rules,
                        include_toc=include_toc,
                        include_table_list=include_table_list,
                        include_figure_list=include_figure_list,
                        include_appendix_list=include_appendix_list,
                        include_page_numbers=include_page_numbers,
                    )

                elif normalized_mode == "journal":
                    processing_result = convert_to_journal(
                        input_path=input_path,
                        output_path=output_path,
                    )

                else:
                    shutil.copy2(
                        input_path,
                        output_path,
                    )

                    processing_result = {
                        "message": (
                            "Dokumen dianalisis tanpa perubahan isi."
                        )
                    }

                analysis_after = analyze_document(
                    output_path
                )

                report_payload = {
                    "job_id": job_id,
                    "batch_id": batch_id,
                    "original_name": original_name,
                    "mode": normalized_mode,
                    "preset": preset,
                    "profile": selected_profile,
                    "template": selected_template,
                    "custom_rules": merged_rules,
                    "analysis_before": analysis_before,
                    "processing": processing_result,
                    "analysis_after": analysis_after,
                }

                write_json(
                    report_path,
                    report_payload,
                )

                complete_job(
                    job_id=job_id,
                    output_name=output_name,
                    output_path=str(output_path),
                    report_path=str(report_path),
                )

                successes.append(
                    {
                        "position": position,
                        "job_id": job_id,
                        "original_name": original_name,
                        "output_name": output_name,
                        "output_path": str(output_path),
                        "report_path": str(report_path),
                        "summary": analysis_after.get(
                            "summary",
                            {},
                        ),
                    }
                )

            except Exception as exc:
                logger.exception(
                    "Batch %s gagal memproses %s.",
                    batch_id,
                    original_name,
                )

                if job_created:
                    try:
                        fail_job(
                            job_id,
                            str(exc),
                        )
                    except Exception:
                        logger.exception(
                            "Gagal memperbarui status job %s.",
                            job_id,
                        )

                output_path.unlink(
                    missing_ok=True
                )

                report_path.unlink(
                    missing_ok=True
                )

                failures.append(
                    {
                        "file": original_name,
                        "error": str(exc),
                    }
                )

            finally:
                input_path.unlink(
                    missing_ok=True
                )

        if not successes:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Tidak ada dokumen yang berhasil diproses."
                    ),
                    "failures": failures,
                },
            )

        summary_payload = {
            "batch_id": batch_id,
            "mode": normalized_mode,
            "preset": preset,
            "profile": selected_profile,
            "template": selected_template,
            "rules": merged_rules,
            "total_files": len(files),
            "success_count": len(successes),
            "failed_count": len(failures),
            "successes": successes,
            "failures": failures,
        }

        write_json(
            batch_work_directory / "ringkasan_batch.json",
            summary_payload,
        )

        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.write(
                batch_work_directory / "ringkasan_batch.json",
                arcname="ringkasan_batch.json",
            )

            for item in successes:
                document_path = Path(
                    item["output_path"]
                )

                report_file_path = Path(
                    item["report_path"]
                )

                unique_prefix = item["job_id"][:8]

                archive.write(
                    document_path,
                    arcname=(
                        "dokumen/"
                        f"{unique_prefix}_"
                        f"{item['output_name']}"
                    ),
                )

                archive.write(
                    report_file_path,
                    arcname=(
                        "laporan/"
                        f"{unique_prefix}_"
                        f"{Path(item['original_name']).stem}.json"
                    ),
                )

        create_batch_record(
            batch_id=batch_id,
            mode=normalized_mode,
            preset=preset,
            total_files=len(files),
            success_count=len(successes),
            failed_count=len(failures),
            zip_path=str(zip_path),
            failures=failures,
        )

        return {
            "success": True,
            "batch_id": batch_id,
            "message": (
                f"{len(successes)} dokumen berhasil diproses."
            ),
            "total_files": len(files),
            "success_count": len(successes),
            "failed_count": len(failures),
            "failures": failures,
            "download_url": (
                f"/api/batches/{batch_id}/download"
            ),
        }

    finally:
        shutil.rmtree(
            batch_work_directory,
            ignore_errors=True,
        )


@router.get("/api/batches")
def batches_index() -> dict[str, Any]:
    records = []

    for batch in list_batches():
        batch_id = batch.get("batch_id")

        records.append(
            {
                **batch,
                "download_url": (
                    f"/api/batches/{batch_id}/download"
                ),
            }
        )

    return {
        "batches": records
    }


@router.get("/api/batches/{batch_id}/download")
def batch_download(
    batch_id: str,
) -> FileResponse:
    batch = get_batch(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch tidak ditemukan.",
        )

    raw_zip_path = batch.get("zip_path")

    if not raw_zip_path:
        raise HTTPException(
            status_code=404,
            detail="Lokasi arsip batch tidak tersedia.",
        )

    zip_path = Path(raw_zip_path)

    if not zip_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Arsip ZIP batch sudah tidak tersedia.",
        )

    return FileResponse(
        zip_path,
        filename=f"DocuRapi_Batch_{batch_id[:8]}.zip",
        media_type="application/zip",
    )


@router.delete("/api/batches/{batch_id}")
def batch_delete(
    batch_id: str,
) -> dict[str, Any]:
    batch = delete_batch_record(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch tidak ditemukan.",
        )

    raw_zip_path = batch.get("zip_path")

    if raw_zip_path:
        Path(raw_zip_path).unlink(
            missing_ok=True
        )

    return {
        "success": True,
        "message": "Riwayat batch berhasil dihapus.",
    }