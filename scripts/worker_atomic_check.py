from __future__ import annotations

import concurrent.futures
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from services.postgres_worker_queue import (  # noqa: E402
    complete_job,
    connect,
    delete_job,
    enqueue_job,
    initialize_worker_schema,
)


def claim_specific(
    job_id: str,
    worker_id: str,
) -> dict | None:
    lock_token = uuid.uuid4().hex

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS
                (
                    SELECT job_id
                    FROM background.worker_runtime_jobs
                    WHERE job_id = %s
                      AND status IN ('queued', 'retrying')
                      AND available_at <= NOW()
                      AND cancel_requested = FALSE
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE background.worker_runtime_jobs AS job
                SET
                    status = 'running',
                    attempts = job.attempts + 1,
                    locked_at = NOW(),
                    lock_token = %s,
                    worker_id = %s,
                    heartbeat_at = NOW(),
                    started_at = COALESCE(
                        job.started_at,
                        NOW()
                    ),
                    updated_at = NOW()
                FROM candidate
                WHERE job.job_id = candidate.job_id
                RETURNING job.*
                """,
                (
                    job_id,
                    lock_token,
                    worker_id,
                ),
            )

            row = cursor.fetchone()

    return (
        dict(row)
        if row is not None
        else None
    )


def main() -> None:
    initialize_worker_schema()

    job_id = (
        "atomic-"
        + uuid.uuid4().hex
    )

    enqueue_job(
        "system.noop",
        {"check": "atomic"},
        priority=-2000000000,
        max_attempts=1,
        timeout_seconds=30,
        job_id=job_id,
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                claim_specific,
                job_id,
                worker_id,
            )
            for worker_id in (
                "atomic-a",
                "atomic-b",
            )
        ]

        results = [
            future.result()
            for future in futures
        ]

    claimed = [
        item
        for item in results
        if item is not None
    ]

    print("Atomic claims:", len(claimed))

    if len(claimed) != 1:
        raise RuntimeError(
            "Job harus diklaim tepat satu worker."
        )

    complete_job(
        job_id,
        str(claimed[0]["lock_token"]),
        result={"atomic": True},
    )

    delete_job(job_id)

    print("POSTGRESQL_ATOMIC_CLAIMING_PASSED")


if __name__ == "__main__":
    main()
