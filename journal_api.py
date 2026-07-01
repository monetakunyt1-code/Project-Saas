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
from fastapi.responses import FileResponse

from config import (
    ALLOWED_EXTENSION,
    MAX_FILE_SIZE,
)
from database import get_template
from services.journal_transformer import (
    build_journal_article,
)
from services.template_manager import (
    extract_template_rules,
)


BASE_DIR = Path(__file__).resolve().parent
JOURNAL_PAGE = (
    BASE_DIR
    / "templates"
    / "journal_studio.html"
)

JOURNAL_DIRECTORY = (
    BASE_DIR
    / "storage"
    / "journals"
)

JOURNAL_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

router = APIRouter()


def safe_filename(
    filename: str,
) -> str:
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


def parse_positive_integer(
    value: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    cleaned = value.strip()

    if not cleaned:
        return default

    try:
        number = int(cleaned)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nilai '{value}' harus berupa bilangan bulat."
            ),
        ) from exc

    if number < minimum or number > maximum:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nilai harus berada antara "
                f"{minimum} dan {maximum}."
            ),
        )

    return number


def metadata_path(
    job_id: str,
) -> Path:
    return (
        JOURNAL_DIRECTORY
        / job_id
        / "metadata.json"
    )


def read_metadata(
    job_id: str,
) -> dict[str, Any] | None:
    path = metadata_path(
        job_id
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


@router.get("/journal-studio")
def journal_studio_page() -> FileResponse:
    if not JOURNAL_PAGE.exists():
        raise HTTPException(
            status_code=500,
            detail="Halaman Journal Studio belum tersedia.",
        )

    return FileResponse(
        JOURNAL_PAGE
    )


@router.post("/api/journal/build")
async def journal_build(
    file: UploadFile = File(...),
    title: str = Form(""),
    author_name: str = Form(""),
    affiliation: str = Form(""),
    email: str = Form(""),
    keywords: str = Form(""),
    reduction_mode: str = Form("extractive"),
    include_literature: bool = Form(True),
    target_abstract_words: str = Form("200"),
    target_introduction_words: str = Form("1200"),
    target_methods_words: str = Form("700"),
    target_results_words: str = Form("1800"),
    target_conclusion_words: str = Form("300"),
    template_id: str = Form(""),
) -> dict[str, Any]:
    filename = file.filename or ""

    if Path(filename).suffix.lower() != ALLOWED_EXTENSION:
        raise HTTPException(
            status_code=400,
            detail="File harus menggunakan format .docx.",
        )

    normalized_mode = reduction_mode.lower().strip()

    if normalized_mode not in {
        "preserve",
        "extractive",
    }:
        raise HTTPException(
            status_code=400,
            detail="Mode transformasi tidak valid.",
        )

    targets = {
        "abstract": parse_positive_integer(
            target_abstract_words,
            200,
            50,
            500,
        ),
        "introduction": parse_positive_integer(
            target_introduction_words,
            1200,
            100,
            5000,
        ),
        "methods": parse_positive_integer(
            target_methods_words,
            700,
            100,
            3000,
        ),
        "results": parse_positive_integer(
            target_results_words,
            1800,
            100,
            8000,
        ),
        "conclusion": parse_positive_integer(
            target_conclusion_words,
            300,
            50,
            1500,
        ),
    }

    job_id = uuid4().hex
    original_name = safe_filename(
        filename
    )

    job_directory = (
        JOURNAL_DIRECTORY
        / job_id
    )

    job_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_path = (
        job_directory
        / f"source_{original_name}"
    )

    output_name = (
        "Draft_Jurnal_"
        f"{Path(original_name).stem}.docx"
    )

    output_path = (
        job_directory
        / output_name
    )

    report_path = (
        job_directory
        / "report.json"
    )

    metadata_file = (
        job_directory
        / "metadata.json"
    )

    try:
        file_size = await save_upload(
            file,
            source_path,
        )

        custom_rules = None
        selected_template = None

        if template_id.strip():
            selected_template = get_template(
                template_id.strip()
            )

            if not selected_template:
                raise HTTPException(
                    status_code=404,
                    detail="Template jurnal tidak ditemukan.",
                )

            custom_rules = extract_template_rules(
                selected_template["file_path"]
            )

        keyword_list = [
            item.strip()
            for item in re.split(
                r"[;,]",
                keywords,
            )
            if item.strip()
        ]

        report = build_journal_article(
            input_path=source_path,
            output_path=output_path,
            title=title,
            author_name=author_name,
            affiliation=affiliation,
            email=email,
            keywords=keyword_list,
            reduction_mode=normalized_mode,
            include_literature=include_literature,
            target_abstract_words=targets["abstract"],
            target_introduction_words=targets[
                "introduction"
            ],
            target_methods_words=targets["methods"],
            target_results_words=targets["results"],
            target_conclusion_words=targets[
                "conclusion"
            ],
            custom_rules=custom_rules,
        )

        report[
            "template"
        ] = selected_template

        report_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        metadata = {
            "job_id": job_id,
            "original_name": original_name,
            "output_name": output_name,
            "title": report["title"],
            "author_name": author_name.strip(),
            "reduction_mode": normalized_mode,
            "source_total_words": report[
                "source_total_words"
            ],
            "output_total_words": report[
                "output_total_words"
            ],
            "warnings_total": len(
                report["warnings"]
            ),
            "file_size": file_size,
            "created_at": report[
                "created_at"
            ],
            "output_path": str(
                output_path
            ),
            "report_path": str(
                report_path
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
            "job_id": job_id,
            "message": (
                "Draft artikel jurnal berhasil dibuat."
            ),
            "title": report["title"],
            "source_total_words": report[
                "source_total_words"
            ],
            "output_total_words": report[
                "output_total_words"
            ],
            "section_word_counts": report[
                "output_word_counts"
            ],
            "warnings": report["warnings"],
            "download_url": (
                f"/api/journal/jobs/{job_id}/download"
            ),
            "report_url": (
                f"/api/journal/jobs/{job_id}/report"
            ),
        }

    except HTTPException:
        shutil.rmtree(
            job_directory,
            ignore_errors=True,
        )
        raise

    except Exception as exc:
        shutil.rmtree(
            job_directory,
            ignore_errors=True,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Transformasi jurnal gagal: {exc}",
        ) from exc


@router.get("/api/journal/jobs")
def journal_jobs() -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for folder in JOURNAL_DIRECTORY.iterdir():
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

        job_id = metadata.get(
            "job_id"
        )

        metadata[
            "download_url"
        ] = (
            f"/api/journal/jobs/{job_id}/download"
        )

        metadata[
            "report_url"
        ] = (
            f"/api/journal/jobs/{job_id}/report"
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
        "jobs": records
    }


@router.get("/api/journal/jobs/{job_id}/download")
def journal_download(
    job_id: str,
) -> FileResponse:
    metadata = read_metadata(
        job_id
    )

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Hasil jurnal tidak ditemukan.",
        )

    output_path = Path(
        metadata["output_path"]
    )

    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File hasil jurnal tidak tersedia.",
        )

    return FileResponse(
        output_path,
        filename=metadata["output_name"],
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )


@router.get("/api/journal/jobs/{job_id}/report")
def journal_report(
    job_id: str,
) -> FileResponse:
    metadata = read_metadata(
        job_id
    )

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="Laporan jurnal tidak ditemukan.",
        )

    report_path = Path(
        metadata["report_path"]
    )

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="File laporan jurnal tidak tersedia.",
        )

    return FileResponse(
        report_path,
        filename=(
            f"Laporan_Jurnal_{job_id[:8]}.json"
        ),
        media_type="application/json",
    )


@router.delete("/api/journal/jobs/{job_id}")
def journal_delete(
    job_id: str,
) -> dict[str, Any]:
    job_directory = (
        JOURNAL_DIRECTORY
        / job_id
    )

    if not job_directory.exists():
        raise HTTPException(
            status_code=404,
            detail="Riwayat jurnal tidak ditemukan.",
        )

    shutil.rmtree(
        job_directory,
        ignore_errors=True,
    )

    return {
        "success": True,
        "message": "Riwayat jurnal berhasil dihapus.",
    }