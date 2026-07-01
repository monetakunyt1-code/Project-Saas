from __future__ import annotations


# DOCURAPI_PRODUCTION_ENV_LOADER_START
import os as _docurapi_os
from pathlib import Path as _DocuRapiPath


_docurapi_production_env_file = (
    _DocuRapiPath(__file__).resolve().parent
    / ".env.production"
)


if _docurapi_production_env_file.exists():
    for _docurapi_raw_line in (
        _docurapi_production_env_file.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    ):
        _docurapi_line = (
            _docurapi_raw_line.strip()
        )

        if (
            not _docurapi_line
            or _docurapi_line.startswith("#")
            or "=" not in _docurapi_line
        ):
            continue

        (
            _docurapi_name,
            _docurapi_value,
        ) = _docurapi_line.split(
            "=",
            1,
        )

        _docurapi_name = (
            _docurapi_name.strip()
        )

        _docurapi_value = (
            _docurapi_value.strip()
            .strip('"')
            .strip("'")
        )

        _docurapi_os.environ.setdefault(
            _docurapi_name,
            _docurapi_value,
        )


from services.runtime_secrets import (
    validate_runtime_secrets
    as _docurapi_validate_runtime_secrets,
)


_docurapi_validate_runtime_secrets()

# DOCURAPI_PRODUCTION_ENV_LOADER_END


import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import (
    ALLOWED_EXTENSION,
    MAX_FILE_SIZE,
    OUTPUT_DIR,
    REPORT_DIR,
    TEMPLATE_DIR,
    UPLOAD_DIR,
)
from database import (
    clear_job_history,
    complete_job,
    create_job,
    delete_job,
    delete_template,
    fail_job,
    get_job,
    get_template,
    initialize_database,
    list_jobs,
    list_templates,
    register_template,
    remove_job_files,
)
from logger import logger
from services.document_analyzer import analyze_document
from services.final_formatter import format_document
from services.journal_converter import convert_to_journal
from services.template_manager import extract_template_rules


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "templates" / "index.html"

app = FastAPI(
    title="DocuRapi",
    version="2.0.0",
)


# DOCURAPI_MIDTRANS_GATEWAY_START
from midtrans_gateway_api import (
    router as _docurapi_midtrans_router,
)


_docurapi_midtrans_signatures = {
    (
        getattr(route, "path", None),
        tuple(
            sorted(
                getattr(
                    route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )
    for route in getattr(
        app,
        "routes",
        [],
    )
}


for _docurapi_midtrans_route in getattr(
    _docurapi_midtrans_router,
    "routes",
    [],
):
    _docurapi_midtrans_signature = (
        getattr(
            _docurapi_midtrans_route,
            "path",
            None,
        ),
        tuple(
            sorted(
                getattr(
                    _docurapi_midtrans_route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )

    if (
        _docurapi_midtrans_signature
        in _docurapi_midtrans_signatures
    ):
        continue

    app.router.routes.append(
        _docurapi_midtrans_route
    )

    _docurapi_midtrans_signatures.add(
        _docurapi_midtrans_signature
    )

# DOCURAPI_MIDTRANS_GATEWAY_END



# DOCURAPI_BILLING_ENFORCEMENT_START
from billing_enforcement_api import (
    router as _docurapi_billing_enforcement_router,
)
from services.billing_enforcement_middleware import (
    BillingEnforcementMiddleware as _DocuRapiBillingEnforcementMiddleware,
)


_docurapi_billing_middleware_exists = any(
    getattr(
        middleware,
        "cls",
        None,
    ).__name__
    == "_DocuRapiBillingEnforcementMiddleware"
    if getattr(
        middleware,
        "cls",
        None,
    )
    else False
    for middleware in getattr(
        app,
        "user_middleware",
        [],
    )
)


if not _docurapi_billing_middleware_exists:
    app.add_middleware(
        _DocuRapiBillingEnforcementMiddleware
    )


_docurapi_billing_enforcement_signatures = {
    (
        getattr(route, "path", None),
        tuple(
            sorted(
                getattr(
                    route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )
    for route in getattr(
        app,
        "routes",
        [],
    )
}


for _docurapi_billing_enforcement_route in getattr(
    _docurapi_billing_enforcement_router,
    "routes",
    [],
):
    _docurapi_billing_enforcement_signature = (
        getattr(
            _docurapi_billing_enforcement_route,
            "path",
            None,
        ),
        tuple(
            sorted(
                getattr(
                    _docurapi_billing_enforcement_route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )

    if (
        _docurapi_billing_enforcement_signature
        in _docurapi_billing_enforcement_signatures
    ):
        continue

    app.router.routes.append(
        _docurapi_billing_enforcement_route
    )

    _docurapi_billing_enforcement_signatures.add(
        _docurapi_billing_enforcement_signature
    )

# DOCURAPI_BILLING_ENFORCEMENT_END



# DOCURAPI_BILLING_BINDING_START
from billing_api import router as _docurapi_billing_router


_docurapi_billing_route_signatures = {
    (
        getattr(route, "path", None),
        tuple(
            sorted(
                getattr(
                    route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )
    for route in getattr(
        app,
        "routes",
        [],
    )
}


for _docurapi_billing_route in getattr(
    _docurapi_billing_router,
    "routes",
    [],
):
    _docurapi_billing_signature = (
        getattr(
            _docurapi_billing_route,
            "path",
            None,
        ),
        tuple(
            sorted(
                getattr(
                    _docurapi_billing_route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )

    if (
        _docurapi_billing_signature
        in _docurapi_billing_route_signatures
    ):
        continue

    app.router.routes.append(
        _docurapi_billing_route
    )

    _docurapi_billing_route_signatures.add(
        _docurapi_billing_signature
    )

# DOCURAPI_BILLING_BINDING_END







# DOCURAPI_NOTIFICATION_BINDING_V3_START
# Dipasang segera setelah objek FastAPI terakhir dibuat.
from notification_api import router as _docurapi_notification_router_v3


def _docurapi_notification_signature_v3(route):
    return (
        getattr(route, "path", None),
        tuple(
            sorted(
                getattr(
                    route,
                    "methods",
                    None,
                )
                or []
            )
        ),
    )


_docurapi_existing_notification_routes_v3 = {
    _docurapi_notification_signature_v3(route)
    for route in getattr(
        app,
        "routes",
        [],
    )
}


for _docurapi_notification_route_v3 in getattr(
    _docurapi_notification_router_v3,
    "routes",
    [],
):
    _docurapi_notification_route_signature_v3 = (
        _docurapi_notification_signature_v3(
            _docurapi_notification_route_v3
        )
    )

    if (
        _docurapi_notification_route_signature_v3
        in _docurapi_existing_notification_routes_v3
    ):
        continue

    app.router.routes.append(
        _docurapi_notification_route_v3
    )

    _docurapi_existing_notification_routes_v3.add(
        _docurapi_notification_route_signature_v3
    )

# DOCURAPI_NOTIFICATION_BINDING_V3_END


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.on_event("startup")
def startup_event() -> None:
    initialize_database()
    logger.info("DocuRapi dimulai.")


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

    destination.write_bytes(content)
    return len(content)


def validate_docx(upload: UploadFile) -> None:
    filename = upload.filename or ""

    if Path(filename).suffix.lower() != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail="File harus menggunakan format .docx.",
        )


def write_report(
    report_path: Path,
    payload: dict[str, Any],
) -> None:
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


@app.get("/")
def home() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=500,
            detail="File antarmuka belum tersedia.",
        )

    return FileResponse(INDEX_FILE)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "application": "DocuRapi",
        "version": "2.0.0",
    }


@app.post("/api/process")
async def process_document(
    file: UploadFile = File(...),
    mode: str = Form("format"),
    preset: str = Form("skripsi"),
    template_id: str = Form(""),
    include_toc: bool = Form(True),
    include_table_list: bool = Form(True),
    include_figure_list: bool = Form(True),
    include_appendix_list: bool = Form(True),
    include_page_numbers: bool = Form(True),
) -> dict[str, Any]:
    validate_docx(file)

    normalized_mode = mode.lower().strip()

    if normalized_mode not in {
        "format",
        "analyze",
        "journal",
    }:
        raise HTTPException(
            status_code=400,
            detail="Mode pemrosesan tidak valid.",
        )

    job_id = uuid4().hex
    original_name = safe_filename(
        file.filename or "document.docx"
    )

    input_path = UPLOAD_DIR / f"{job_id}_{original_name}"

    output_prefix = {
        "format": "rapi",
        "analyze": "analisis",
        "journal": "draft_jurnal",
    }[normalized_mode]

    output_name = (
        f"{output_prefix}_{Path(original_name).stem}.docx"
    )

    output_path = OUTPUT_DIR / f"{job_id}_{output_name}"
    report_path = REPORT_DIR / f"{job_id}.json"

    try:
        input_size = await save_upload(
            file,
            input_path,
        )

        create_job(
            job_id=job_id,
            original_name=original_name,
            mode=normalized_mode,
            preset=preset,
            input_size=input_size,
        )

        analysis_before = analyze_document(
            input_path
        )

        custom_rules = None
        selected_template = None

        if template_id:
            selected_template = get_template(
                template_id
            )

            if not selected_template:
                raise ValueError(
                    "Template khusus tidak ditemukan."
                )

            custom_rules = extract_template_rules(
                selected_template["file_path"]
            )

        processing_result: dict[str, Any]

        if normalized_mode == "format":
            processing_result = format_document(
                input_path=input_path,
                output_path=output_path,
                preset=preset,
                custom_rules=custom_rules,
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
                    "Dokumen dianalisis tanpa mengubah file."
                )
            }

        analysis_after = analyze_document(
            output_path
        )

        report_payload = {
            "job_id": job_id,
            "original_name": original_name,
            "mode": normalized_mode,
            "preset": preset,
            "template": selected_template,
            "analysis_before": analysis_before,
            "processing": processing_result,
            "analysis_after": analysis_after,
        }

        write_report(
            report_path,
            report_payload,
        )

        complete_job(
            job_id=job_id,
            output_name=output_name,
            output_path=str(output_path),
            report_path=str(report_path),
        )

        input_path.unlink(
            missing_ok=True
        )

        logger.info(
            "Job %s selesai. Mode=%s",
            job_id,
            normalized_mode,
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": "Dokumen berhasil diproses.",
            "download_url": f"/api/jobs/{job_id}/download",
            "report_url": f"/api/jobs/{job_id}/report",
            "summary": analysis_after["summary"],
        }

    except HTTPException:
        input_path.unlink(
            missing_ok=True
        )
        raise

    except Exception as exc:
        logger.exception(
            "Job %s gagal.",
            job_id,
        )

        try:
            fail_job(
                job_id,
                str(exc),
            )
        except Exception:
            logger.exception(
                "Gagal memperbarui status job."
            )

        input_path.unlink(
            missing_ok=True
        )
        output_path.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=500,
            detail=f"Pemrosesan gagal: {exc}",
        ) from exc


@app.get("/api/jobs")
def history(
    limit: int = 25,
) -> dict[str, Any]:
    jobs = list_jobs(
        limit=limit
    )

    cleaned_jobs = []

    for job in jobs:
        cleaned_jobs.append(
            {
                "job_id": job["job_id"],
                "original_name": job["original_name"],
                "mode": job["mode"],
                "preset": job["preset"],
                "status": job["status"],
                "output_name": job["output_name"],
                "error_message": job["error_message"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "download_url": (
                    f"/api/jobs/{job['job_id']}/download"
                    if job["status"] == "completed"
                    else None
                ),
                "report_url": (
                    f"/api/jobs/{job['job_id']}/report"
                    if job["status"] == "completed"
                    else None
                ),
            }
        )

    return {
        "jobs": cleaned_jobs
    }


@app.get("/api/jobs/{job_id}/download")
def download_job(
    job_id: str,
) -> FileResponse:
    job = get_job(job_id)

    if not job or job["status"] != "completed":
        raise HTTPException(
            status_code=404,
            detail="Hasil dokumen tidak ditemukan.",
        )

    output_path = Path(job["output_path"])

    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File hasil sudah tidak tersedia.",
        )

    return FileResponse(
        output_path,
        filename=job["output_name"],
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )


@app.get("/api/jobs/{job_id}/report")
def download_report(
    job_id: str,
) -> FileResponse:
    job = get_job(job_id)

    if not job or job["status"] != "completed":
        raise HTTPException(
            status_code=404,
            detail="Laporan tidak ditemukan.",
        )

    report_path = Path(job["report_path"])

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File laporan sudah tidak tersedia.",
        )

    return FileResponse(
        report_path,
        filename=f"laporan_{job_id}.json",
        media_type="application/json",
    )


@app.delete("/api/jobs/{job_id}")
def remove_job(
    job_id: str,
) -> dict[str, Any]:
    job = delete_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Riwayat tidak ditemukan.",
        )

    remove_job_files(job)

    return {
        "success": True,
        "message": "Riwayat berhasil dihapus.",
    }


@app.delete("/api/jobs")
def remove_all_jobs() -> dict[str, Any]:
    jobs = clear_job_history()

    for job in jobs:
        remove_job_files(job)

    return {
        "success": True,
        "deleted": len(jobs),
    }


@app.get("/api/templates")
def templates_list() -> dict[str, Any]:
    templates = list_templates()

    return {
        "templates": [
            {
                "template_id": item["template_id"],
                "template_name": item["template_name"],
                "institution_name": item["institution_name"],
                "document_type": item["document_type"],
                "file_name": item["file_name"],
                "created_at": item["created_at"],
            }
            for item in templates
        ]
    }


@app.post("/api/templates")
async def upload_template(
    file: UploadFile = File(...),
    template_name: str = Form(...),
    institution_name: str = Form(""),
    document_type: str = Form("skripsi"),
) -> dict[str, Any]:
    validate_docx(file)

    template_id = uuid4().hex
    original_name = safe_filename(
        file.filename or "template.docx"
    )

    destination = (
        TEMPLATE_DIR
        / f"{template_id}_{original_name}"
    )

    await save_upload(
        file,
        destination,
    )

    try:
        rules = extract_template_rules(
            destination
        )

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
            "rules": rules,
        }

    except Exception as exc:
        destination.unlink(
            missing_ok=True
        )

        raise HTTPException(
            status_code=400,
            detail=f"Template tidak dapat dibaca: {exc}",
        ) from exc


@app.delete("/api/templates/{template_id}")
def remove_template(
    template_id: str,
) -> dict[str, Any]:
    template = delete_template(
        template_id
    )

    if not template:
        raise HTTPException(
            status_code=404,
            detail="Template tidak ditemukan.",
        )

    template_path = Path(
        template["file_path"]
    )

    template_path.unlink(
        missing_ok=True
    )

    return {
        "success": True,
        "message": "Template berhasil dihapus.",
    }

# DOCURAPI_ADVANCED_ROUTER
from advanced_api import router as advanced_router

app.include_router(advanced_router)


# DOCURAPI_ACADEMIC_ROUTER
from academic_api import router as academic_router

app.include_router(academic_router)


# DOCURAPI_JOURNAL_STUDIO_ROUTER
from journal_api import router as journal_studio_router

app.include_router(journal_studio_router)


# DOCURAPI_SAAS_ROUTER
from saas_api import router as saas_router
from services.saas_middleware import SaaSQuotaMiddleware
app.include_router(saas_router)
app.add_middleware(SaaSQuotaMiddleware)

# DOCURAPI_SECURITY_ROUTER
from security_api import router as security_router
from services.security_service import SecurityMiddleware

app.include_router(security_router)
app.add_middleware(SecurityMiddleware)


# DOCURAPI_WORKSPACE_ROUTER
from workspace_api import router as workspace_router
from services.workspace_middleware import WorkspaceIsolationMiddleware

app.include_router(workspace_router)
app.add_middleware(WorkspaceIsolationMiddleware)


# DOCURAPI_BACKGROUND_ROUTER
from background_api import router as background_router

app.include_router(background_router)


# DOCURAPI_SYSTEM_HEALTH
from system_api import router as system_router
from services.system_observability import SystemObservabilityMiddleware
from services.backup_service import start_auto_backup

app.include_router(system_router)
app.add_middleware(SystemObservabilityMiddleware)


# DOCURAPI_TEST_CENTER
from test_center_api import router as test_center_router

app.include_router(test_center_router)


# DOCURAPI_ROUTE_RECOVERY_V2
# Memastikan seluruh router terpasang pada objek FastAPI aktif.
import importlib as _docurapi_importlib


_docurapi_router_modules = [
    "saas_api",
    "advanced_api",
    "academic_api",
    "journal_api",
    "security_api",
    "workspace_api",
    "background_api",
    "system_api",
    "test_center_api",
]


def _docurapi_route_signature(route):
    path = getattr(
        route,
        "path",
        None,
    )

    methods = getattr(
        route,
        "methods",
        None,
    )

    return (
        path,
        tuple(sorted(methods or [])),
    )


_docurapi_existing_routes = {
    _docurapi_route_signature(route)
    for route in getattr(
        app,
        "routes",
        [],
    )
}


for _docurapi_module_name in _docurapi_router_modules:
    try:
        _docurapi_module = _docurapi_importlib.import_module(
            _docurapi_module_name
        )

    except Exception:
        continue

    _docurapi_router = getattr(
        _docurapi_module,
        "router",
        None,
    )

    if _docurapi_router is None:
        _docurapi_router = getattr(
            _docurapi_module,
            "api_router",
            None,
        )

    if _docurapi_router is None:
        continue

    for _docurapi_route in getattr(
        _docurapi_router,
        "routes",
        [],
    ):
        _docurapi_signature = _docurapi_route_signature(
            _docurapi_route
        )

        if _docurapi_signature in _docurapi_existing_routes:
            continue

        app.router.routes.append(
            _docurapi_route
        )

        _docurapi_existing_routes.add(
            _docurapi_signature
        )


# DOCURAPI_NOTIFICATION_CENTER
from notification_api import router as notification_router

if not any(
    getattr(route, "path", None)
    == "/notifications"
    for route in app.routes
):
    app.include_router(notification_router)
# DOCURAPI_NOTIFICATION_ROUTE_FINAL_V2
# Router dipasang pada objek FastAPI terakhir yang aktif.
from notification_api import router as _docurapi_notification_router


_docurapi_notification_paths = {
    getattr(route, "path", None)
    for route in getattr(
        app,
        "routes",
        [],
    )
}


if "/notifications" not in _docurapi_notification_paths:
    app.include_router(
        _docurapi_notification_router
    )

