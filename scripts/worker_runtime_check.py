from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from services.postgres_worker_queue import (  # noqa: E402
    connect,
    delete_job,
    enqueue_job,
    get_job,
    queue_health,
    recover_stale_jobs,
    request_cancel,
)

from services.storage_bridge import (  # noqa: E402
    create_storage_bridge,
)


TERMINAL = {
    "succeeded",
    "failed",
    "canceled",
    "timed_out",
}


def wait_job(
    job_id: str,
    expected: set[str],
    timeout: float,
) -> dict:
    deadline = time.monotonic() + timeout
    previous = None

    while time.monotonic() < deadline:
        job = get_job(job_id)

        if job is None:
            raise RuntimeError(
                f"Job hilang: {job_id}"
            )

        status = str(job["status"])

        if status != previous:
            print(
                job_id,
                "->",
                status,
                "attempts=",
                job["attempts"],
            )

            previous = status

        if status in expected:
            return job

        time.sleep(0.5)

    raise TimeoutError(
        f"Timeout menunggu job: {job_id}"
    )


def cleanup(job_id: str) -> None:
    job = get_job(job_id)

    if job is None:
        return

    if job["status"] not in TERMINAL:
        request_cancel(job_id)
        time.sleep(0.5)

    delete_job(job_id)


def main() -> None:
    health = queue_health()

    print(
        "Active workers:",
        health["active_workers"],
    )

    if health["active_workers"] < 1:
        raise RuntimeError(
            "Worker aktif belum terdeteksi."
        )

    noop_id = "noop-" + uuid.uuid4().hex
    artifact_id = "artifact-" + uuid.uuid4().hex
    retry_id = "retry-" + uuid.uuid4().hex
    timeout_id = "timeout-" + uuid.uuid4().hex
    cancel_id = "cancel-" + uuid.uuid4().hex
    stale_id = "stale-" + uuid.uuid4().hex

    artifact_reference = None

    try:
        enqueue_job(
            "system.noop",
            {"message": "worker-ready"},
            priority=-1000000,
            max_attempts=1,
            timeout_seconds=20,
            job_id=noop_id,
        )

        wait_job(
            noop_id,
            {"succeeded"},
            30,
        )

        enqueue_job(
            "storage.write_text",
            {
                "filename": "worker-result.txt",
                "text": "DOCURAPI_WORKER_ARTIFACT",
                "category": "worker-runtime",
            },
            priority=-1000000,
            max_attempts=1,
            timeout_seconds=20,
            job_id=artifact_id,
        )

        artifact = wait_job(
            artifact_id,
            {"succeeded"},
            30,
        )

        artifact_reference = str(
            artifact.get(
                "artifact_reference"
            )
            or ""
        )

        if not artifact_reference.startswith(
            "object://"
        ):
            raise RuntimeError(
                "Artifact belum menggunakan "
                "object storage."
            )

        bridge = create_storage_bridge()

        content = bridge.read_bytes(
            artifact_reference
        )

        if content != b"DOCURAPI_WORKER_ARTIFACT":
            raise RuntimeError(
                "Isi artifact tidak sesuai."
            )

        print("OBJECT_STORAGE_ARTIFACT_PASSED")

        enqueue_job(
            "unsupported.retry.check",
            {},
            priority=-1000000,
            max_attempts=2,
            timeout_seconds=20,
            job_id=retry_id,
        )

        retry_job = wait_job(
            retry_id,
            {"failed"},
            45,
        )

        if int(retry_job["attempts"]) != 2:
            raise RuntimeError(
                "Retry tidak mencapai dua attempts."
            )

        print("RETRY_AND_BACKOFF_PASSED")

        enqueue_job(
            "system.sleep",
            {"seconds": 5},
            priority=-1000000,
            max_attempts=1,
            timeout_seconds=1,
            job_id=timeout_id,
        )

        wait_job(
            timeout_id,
            {"timed_out"},
            20,
        )

        print("JOB_TIMEOUT_PASSED")

        enqueue_job(
            "system.sleep",
            {"seconds": 20},
            priority=-1000000,
            max_attempts=1,
            timeout_seconds=60,
            job_id=cancel_id,
        )

        wait_job(
            cancel_id,
            {"running"},
            15,
        )

        request_cancel(cancel_id)

        wait_job(
            cancel_id,
            {"canceled"},
            15,
        )

        print("JOB_CANCELLATION_PASSED")

        enqueue_job(
            "system.noop",
            {},
            max_attempts=2,
            timeout_seconds=30,
            delay_seconds=3600,
            job_id=stale_id,
        )

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE background.worker_runtime_jobs
                    SET
                        status = 'running',
                        attempts = 1,
                        lock_token = %s,
                        worker_id = 'stale-worker',
                        locked_at =
                            NOW() - INTERVAL '10 minutes',
                        heartbeat_at =
                            NOW() - INTERVAL '10 minutes',
                        updated_at =
                            NOW() - INTERVAL '10 minutes'
                    WHERE job_id = %s
                    """,
                    (
                        uuid.uuid4().hex,
                        stale_id,
                    ),
                )

        recovery = recover_stale_jobs(10)
        stale_job = get_job(stale_id)

        print("Recovery:", recovery)

        if (
            stale_job is None
            or stale_job["status"]
            != "retrying"
        ):
            raise RuntimeError(
                "Stale job recovery gagal."
            )

        request_cancel(stale_id)

        print("STALE_JOB_RECOVERY_PASSED")
        print("WORKER_RUNTIME_FEATURES_PASSED")

    finally:
        if artifact_reference:
            try:
                create_storage_bridge().delete(
                    artifact_reference
                )
            except Exception:
                pass

        for job_id in (
            noop_id,
            artifact_id,
            retry_id,
            timeout_id,
            cancel_id,
            stale_id,
        ):
            try:
                cleanup(job_id)
            except Exception:
                pass


if __name__ == "__main__":
    main()
