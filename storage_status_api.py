"""Status API untuk object storage DocuRapi."""

from __future__ import annotations

from fastapi import APIRouter

from services.object_storage import (
    backend_name,
)
from services.runtime_file_mirror import (
    mirror_enabled,
    mirror_required,
)
from services.storage_bridge import (
    keep_local_copy,
    runtime_enabled,
)
from services.storage_manifest import (
    storage_statistics,
)


router = APIRouter(
    tags=[
        "Object Storage",
    ]
)


@router.get(
    "/api/storage/status"
)
def object_storage_status() -> dict:
    statistics = (
        storage_statistics()
    )

    return {
        "status": "ready",
        "backend":
            backend_name(),
        "mirror_enabled":
            mirror_enabled(),
        "mirror_required":
            mirror_required(),
        "object_reference_runtime":
            runtime_enabled(),
        "keep_local_copy":
            keep_local_copy(),
        "manifest":
            statistics,
        "download_fallback":
            True,
    }
