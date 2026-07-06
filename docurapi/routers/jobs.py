from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from docurapi.db.jobs_repository import (
    clear_job_history,
    delete_job,
    get_job,
    list_jobs,
    remove_job_files,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def ensure_job_access(job: dict[str, Any] | None, token: str) -> dict[str, Any]:
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job tidak ditemukan.",
        )

    saved_token = job.get("access_token")

    if saved_token and token != saved_token:
        raise HTTPException(
            status_code=403,
            detail="Token akses tidak valid.",
        )

    return job


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
                "payment_status": job.get("payment_status", "unpaid"),
                "amount": job.get("amount", 0),
                "output_name": job["output_name"],
                "error_message": job["error_message"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "download_locked": job.get("payment_status", "unpaid") != "paid",
            }
            for job in jobs
        ]
    }


@router.get("/{job_id}/preview")
def preview_job(job_id: str, token: str = Query(...)) -> dict[str, Any]:
    job = ensure_job_access(get_job(job_id), token)

    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Dokumen belum selesai diproses.",
        )

    report_path = Path(job["report_path"])

    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Preview tidak tersedia.",
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    payment_status = job.get("payment_status", "unpaid")
    is_paid = payment_status == "paid"

    return {
        "job_id": job_id,
        "original_name": job["original_name"],
        "mode": job["mode"],
        "preset": job["preset"],
        "payment_status": payment_status,
        "amount": job.get("amount", 0),
        "download_locked": not is_paid,
        "summary": report.get("analysis_after", {}).get("summary", {}),
        "issues": report.get("analysis_after", {}).get("issues", []),
        "structure_preview": {
            "chapters": report.get("analysis_after", {}).get("structure", {}).get("chapters", [])[:10],
            "subheadings": report.get("analysis_after", {}).get("structure", {}).get("subheadings", [])[:15],
            "table_captions_total": report.get("analysis_after", {}).get("summary", {}).get("table_captions_total", 0),
            "figure_captions_total": report.get("analysis_after", {}).get("summary", {}).get("figure_captions_total", 0),
        },
        "payment_url": f"/api/payments/{job_id}/checkout?token={token}",
        "download_url": f"/api/jobs/{job_id}/download?token={token}" if is_paid else None,
    }


@router.get("/{job_id}/download")
def download_job(job_id: str, token: str = Query(...)):
    job = ensure_job_access(get_job(job_id), token)

    if job["status"] != "completed":
        raise HTTPException(
            status_code=404,
            detail="Hasil dokumen tidak ditemukan.",
        )

    if job.get("payment_status", "unpaid") != "paid":
        raise HTTPException(
            status_code=402,
            detail="Dokumen sudah diproses, tetapi download dikunci sampai pembayaran berhasil.",
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
def download_report(job_id: str, token: str = Query(...)):
    job = ensure_job_access(get_job(job_id), token)

    if job["status"] != "completed":
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
        filename=f"preview_laporan_{job_id}.json",
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
