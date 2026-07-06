from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from docurapi.db.jobs_repository import (
    clear_job_history,
    delete_job,
    get_job,
    list_jobs,
    remove_job_files,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def history(limit: int = 25) -> dict[str, Any]:
    jobs = list_jobs(limit=limit)

    return {
        "jobs": [
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
            for job in jobs
        ]
    }


@router.get("/{job_id}/download")
def download_job(job_id: str):
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
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/{job_id}/report")
def download_report(job_id: str):
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


@router.delete("/{job_id}")
def remove_job(job_id: str) -> dict[str, Any]:
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


@router.delete("")
def remove_all_jobs() -> dict[str, Any]:
    jobs = clear_job_history()

    for job in jobs:
        remove_job_files(job)

    return {
        "success": True,
        "deleted": len(jobs),
    }
