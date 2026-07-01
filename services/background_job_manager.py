from __future__ import annotations

import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from background_database import (
    get_background_job,
    is_job_cancellation_requested,
    mark_interrupted_jobs,
    update_background_job,
)


MAX_WORKERS = max(
    1,
    min(
        int(
            os.getenv(
                "DOCURAPI_BACKGROUND_WORKERS",
                "3",
            )
        ),
        8,
    ),
)

INTERNAL_BASE_URL = os.getenv(
    "DOCURAPI_INTERNAL_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

REQUEST_TIMEOUT_SECONDS = max(
    60,
    int(
        os.getenv(
            "DOCURAPI_BACKGROUND_TIMEOUT",
            "1800",
        )
    ),
)

_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="docurapi-job",
)

_runtime_payloads: dict[
    str,
    dict[str, Any]
] = {}

_runtime_lock = threading.Lock()

mark_interrupted_jobs()


def safe_artifact_filename(
    value: str | None,
) -> str:
    if not value:
        return "background_result.bin"

    cleaned = re.sub(
        r"[^A-Za-z0-9._ -]+",
        "_",
        Path(value).name,
    ).strip()

    return cleaned or "background_result.bin"


def content_disposition_filename(
    header: str,
) -> str | None:
    match = re.search(
        r'filename="?([^";]+)"?',
        header or "",
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1).strip()


def register_runtime_payload(
    job_id: str,
    payload: dict[str, Any],
) -> None:
    with _runtime_lock:
        _runtime_payloads[
            job_id
        ] = payload


def pop_runtime_payload(
    job_id: str,
) -> dict[str, Any] | None:
    with _runtime_lock:
        return _runtime_payloads.pop(
            job_id,
            None,
        )


def get_runtime_payload(
    job_id: str,
) -> dict[str, Any] | None:
    with _runtime_lock:
        return _runtime_payloads.get(
            job_id
        )


def _heartbeat(
    job_id: str,
    stop_event: threading.Event,
) -> None:
    progress = 40

    messages = [
        "Membaca struktur dokumen...",
        "Memproses isi dokumen...",
        "Menerapkan aturan pemrosesan...",
        "Menyusun hasil...",
        "Menyelesaikan laporan...",
    ]

    message_index = 0

    while not stop_event.wait(2.0):
        job = get_background_job(
            job_id
        )

        if (
            not job
            or job["status"]
            not in {
                "running",
                "canceling",
            }
        ):
            return

        if is_job_cancellation_requested(
            job_id
        ):
            update_background_job(
                job_id,
                status="canceling",
                message=(
                    "Menunggu proses aktif berhenti..."
                ),
            )

            continue

        progress = min(
            progress + 3,
            90,
        )

        message = messages[
            message_index
            % len(messages)
        ]

        message_index += 1

        update_background_job(
            job_id,
            progress=progress,
            message=message,
        )


def _build_response_result(
    response: httpx.Response,
    job_directory: Path,
) -> tuple[
    dict[str, Any],
    str | None,
    str | None,
]:
    content_type = response.headers.get(
        "content-type",
        "",
    )

    result: dict[str, Any] = {
        "status_code": response.status_code,
        "content_type": content_type,
        "headers": {
            "content-type": content_type,
        },
    }

    if "application/json" in content_type:
        try:
            result["body_type"] = "json"
            result["body"] = response.json()

            return (
                result,
                None,
                None,
            )

        except ValueError:
            pass

    if (
        content_type.startswith("text/")
        or "html" in content_type
        or "xml" in content_type
    ):
        result["body_type"] = "text"
        result["body"] = response.text

        return (
            result,
            None,
            None,
        )

    filename = content_disposition_filename(
        response.headers.get(
            "content-disposition",
            "",
        )
    )

    filename = safe_artifact_filename(
        filename
    )

    artifact_directory = (
        job_directory
        / "artifacts"
    )

    artifact_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact_path = (
        artifact_directory
        / filename
    )

    artifact_path.write_bytes(
        response.content
    )

    result["body_type"] = "artifact"
    result["body"] = {
        "message": (
            "Hasil tersedia sebagai file."
        ),
        "filename": filename,
    }

    return (
        result,
        str(artifact_path),
        filename,
    )


def _execute_relay_job(
    job_id: str,
) -> None:
    payload = get_runtime_payload(
        job_id
    )

    if not payload:
        update_background_job(
            job_id,
            status="failed",
            progress=100,
            message=(
                "Payload pekerjaan tidak tersedia."
            ),
            error_message=(
                "Runtime payload tidak ditemukan."
            ),
            finished_at=(
                __import__(
                    "datetime"
                )
                .datetime.now(
                    __import__(
                        "datetime"
                    ).timezone.utc
                )
                .isoformat()
            ),
        )

        return

    if is_job_cancellation_requested(
        job_id
    ):
        update_background_job(
            job_id,
            status="canceled",
            progress=100,
            message=(
                "Pekerjaan dibatalkan sebelum dimulai."
            ),
            finished_at=(
                __import__(
                    "datetime"
                )
                .datetime.now(
                    __import__(
                        "datetime"
                    ).timezone.utc
                )
                .isoformat()
            ),
        )

        pop_runtime_payload(
            job_id
        )

        return

    from datetime import (
        datetime,
        timezone,
    )

    update_background_job(
        job_id,
        status="running",
        progress=10,
        message=(
            "Menyiapkan berkas pemrosesan..."
        ),
        started_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )

    stop_event = threading.Event()

    heartbeat_thread = threading.Thread(
        target=_heartbeat,
        args=(
            job_id,
            stop_event,
        ),
        daemon=True,
    )

    opened_files: list[Any] = []

    try:
        update_background_job(
            job_id,
            progress=25,
            message=(
                "Mengirim pekerjaan ke mesin DocuRapi..."
            ),
        )

        files_payload: list[
            tuple[
                str,
                tuple[
                    str,
                    Any,
                    str,
                ],
            ]
        ] = []

        for item in payload.get(
            "files",
            [],
        ):
            file_handle = open(
                item["path"],
                "rb",
            )

            opened_files.append(
                file_handle
            )

            files_payload.append(
                (
                    item["field_name"],
                    (
                        item["filename"],
                        file_handle,
                        item.get(
                            "content_type"
                        )
                        or (
                            "application/"
                            "octet-stream"
                        ),
                    ),
                )
            )

        headers = {
            "X-Background-Relay": "1",
        }

        cookie_header = payload.get(
            "cookie_header"
        )

        csrf_header = payload.get(
            "csrf_header"
        )

        if cookie_header:
            headers["Cookie"] = (
                cookie_header
            )

        if csrf_header:
            headers["X-CSRF-Token"] = (
                csrf_header
            )

        heartbeat_thread.start()

        target_url = (
            INTERNAL_BASE_URL
            + payload["target_path"]
        )

        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = client.post(
                target_url,
                data=payload.get(
                    "fields",
                    [],
                ),
                files=(
                    files_payload
                    if files_payload
                    else None
                ),
                headers=headers,
            )

        stop_event.set()

        heartbeat_thread.join(
            timeout=3
        )

        if is_job_cancellation_requested(
            job_id
        ):
            update_background_job(
                job_id,
                status="canceled",
                progress=100,
                message=(
                    "Pekerjaan dibatalkan."
                ),
                finished_at=datetime.now(
                    timezone.utc
                ).isoformat(),
            )

            return

        update_background_job(
            job_id,
            progress=94,
            message=(
                "Menyimpan hasil pekerjaan..."
            ),
        )

        job_directory = Path(
            payload["job_directory"]
        )

        (
            result,
            artifact_path,
            artifact_filename,
        ) = _build_response_result(
            response,
            job_directory,
        )

        if (
            artifact_path
            and isinstance(
                result.get("body"),
                dict,
            )
        ):
            result["body"][
                "download_url"
            ] = (
                f"/api/background/jobs/"
                f"{job_id}/artifact"
            )

        final_status = (
            "completed"
            if response.status_code < 400
            else "failed"
        )

        final_message = (
            "Pekerjaan berhasil diselesaikan."
            if final_status == "completed"
            else (
                "Mesin DocuRapi mengembalikan "
                "kesalahan pemrosesan."
            )
        )

        update_background_job(
            job_id,
            status=final_status,
            progress=100,
            message=final_message,
            result_json=result,
            error_message=(
                None
                if final_status == "completed"
                else (
                    f"HTTP {response.status_code}"
                )
            ),
            artifact_path=artifact_path,
            artifact_filename=(
                artifact_filename
            ),
            finished_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

    except Exception as exc:
        stop_event.set()

        update_background_job(
            job_id,
            status="failed",
            progress=100,
            message=(
                "Pekerjaan gagal dijalankan."
            ),
            error_message=str(exc),
            finished_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

    finally:
        for file_handle in opened_files:
            try:
                file_handle.close()
            except Exception:
                pass

        pop_runtime_payload(
            job_id
        )


def submit_relay_job(
    job_id: str,
    payload: dict[str, Any],
) -> None:
    register_runtime_payload(
        job_id,
        payload,
    )

    _executor.submit(
        _execute_relay_job,
        job_id,
    )