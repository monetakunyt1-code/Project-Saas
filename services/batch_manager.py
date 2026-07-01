from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
BATCH_DIRECTORY = BASE_DIR / "storage" / "batches"
METADATA_DIRECTORY = BATCH_DIRECTORY / "metadata"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage() -> None:
    BATCH_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    METADATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


def metadata_path(
    batch_id: str,
) -> Path:
    ensure_storage()

    return METADATA_DIRECTORY / f"{batch_id}.json"


def create_batch_record(
    batch_id: str,
    mode: str,
    preset: str,
    total_files: int,
    success_count: int,
    failed_count: int,
    zip_path: str,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    record = {
        "batch_id": batch_id,
        "mode": mode,
        "preset": preset,
        "total_files": total_files,
        "success_count": success_count,
        "failed_count": failed_count,
        "zip_path": zip_path,
        "failures": failures,
        "created_at": utc_now(),
    }

    metadata_path(batch_id).write_text(
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return record


def get_batch(
    batch_id: str,
) -> dict[str, Any] | None:
    path = metadata_path(batch_id)

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


def list_batches() -> list[dict[str, Any]]:
    ensure_storage()

    records: list[dict[str, Any]] = []

    for path in METADATA_DIRECTORY.glob(
        "*.json"
    ):
        try:
            record = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            continue

        if isinstance(record, dict):
            records.append(record)

    return sorted(
        records,
        key=lambda item: item.get(
            "created_at",
            "",
        ),
        reverse=True,
    )


def delete_batch_record(
    batch_id: str,
) -> dict[str, Any] | None:
    record = get_batch(batch_id)

    if not record:
        return None

    metadata_path(batch_id).unlink(
        missing_ok=True
    )

    return record