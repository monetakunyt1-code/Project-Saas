"""API operasional PostgreSQL background worker DocuRapi."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from services.postgres_worker_queue import (
    get_job,
    list_jobs,
    queue_health,
)

from services.worker_handlers import (
    supported_job_types,
)


router = APIRouter(
    tags=["Background Worker"],
)


def serialize(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): serialize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            serialize(item)
            for item in value
        ]

    return value


@router.get("/api/worker/health")
def worker_health() -> dict[str, Any]:
    try:
        result = queue_health()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Worker queue unavailable: "
                + type(exc).__name__
            ),
        ) from exc

    result.update({
        "queue_backend": "postgresql",
        "atomic_claiming": True,
        "retry_supported": True,
        "timeout_supported": True,
        "cancellation_supported": True,
        "stale_recovery_supported": True,
        "object_storage_artifacts": True,
        "supported_job_types": list(
            supported_job_types()
        ),
    })

    return serialize(result)


@router.get("/api/worker/jobs")
def worker_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
) -> dict[str, Any]:
    jobs = list_jobs(
        status=status,
        limit=limit,
    )

    return {
        "total": len(jobs),
        "jobs": serialize(jobs),
    }


@router.get("/api/worker/jobs/{job_id}")
def worker_job_detail(
    job_id: str,
) -> dict[str, Any]:
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Worker job tidak ditemukan.",
        )

    return serialize(job)
