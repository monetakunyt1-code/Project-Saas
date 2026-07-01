from __future__ import annotations

import multiprocessing
import os
import queue
import signal
import socket
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services.postgres_worker_queue import (  # noqa: E402
    claim_job,
    complete_job,
    fail_job,
    heartbeat_job,
    heartbeat_worker,
    initialize_worker_schema,
    is_cancel_requested,
    mark_canceled,
    recover_stale_jobs,
    register_worker,
    stop_worker,
)

from services.worker_handlers import (  # noqa: E402
    execute_job,
)


STOP_REQUESTED = False


def environment_float(
    name: str,
    default: float,
    *,
    minimum: float,
) -> float:
    raw = os.environ.get(
        name,
        "",
    ).strip()

    if not raw:
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} harus berupa angka."
        ) from exc

    return max(
        minimum,
        value,
    )


def environment_int(
    name: str,
    default: int,
    *,
    minimum: int,
) -> int:
    raw = os.environ.get(
        name,
        "",
    ).strip()

    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} harus berupa bilangan bulat."
        ) from exc

    return max(
        minimum,
        value,
    )


def request_stop(
    signum: int,
    frame: Any,
) -> None:
    del signum
    del frame

    global STOP_REQUESTED

    STOP_REQUESTED = True


def child_execute(
    job_type: str,
    payload: dict[str, Any],
    result_queue: multiprocessing.Queue,
) -> None:
    try:
        result = execute_job(
            job_type,
            payload,
        )

        result_queue.put({
            "ok": True,
            "result": result,
        })

    except BaseException as exc:
        result_queue.put({
            "ok": False,

            "error_type":
                type(exc).__name__,

            "error_message":
                str(exc),

            "traceback":
                traceback.format_exc(),
        })


def terminate_process(
    process: multiprocessing.Process,
) -> None:
    if not process.is_alive():
        process.join(
            timeout=1,
        )

        return

    process.terminate()

    process.join(
        timeout=5,
    )

    if process.is_alive():
        process.kill()

        process.join(
            timeout=5,
        )


def run_claimed_job(
    worker_id: str,
    job: dict[str, Any],
    *,
    heartbeat_seconds: float,
    cancel_poll_seconds: float,
) -> None:
    job_id = str(
        job["job_id"]
    )

    lock_token = str(
        job["lock_token"]
    )

    job_type = str(
        job["job_type"]
    )

    payload_value = (
        job.get(
            "payload_json"
        )
        or {}
    )

    payload = (
        dict(payload_value)
        if isinstance(
            payload_value,
            dict,
        )
        else {}
    )

    payload["_job_id"] = (
        job_id
    )

    timeout_seconds = max(
        1,
        int(
            job.get(
                "timeout_seconds",
                300,
            )
        ),
    )

    context = (
        multiprocessing.get_context(
            "spawn"
        )
    )

    result_queue = context.Queue(
        maxsize=1
    )

    process = context.Process(
        target=child_execute,
        args=(
            job_type,
            payload,
            result_queue,
        ),
        name=(
            "docurapi-job-"
            + job_id[:12]
        ),
    )

    process.start()

    started_at = (
        time.monotonic()
    )

    next_heartbeat = started_at

    next_cancel_check = (
        started_at
    )

    try:
        while process.is_alive():
            now = time.monotonic()

            if STOP_REQUESTED:
                terminate_process(
                    process
                )

                fail_job(
                    job_id,
                    lock_token,
                    (
                        "Worker dihentikan saat "
                        "menjalankan job."
                    ),
                    retryable=True,
                )

                return

            elapsed = (
                now
                - started_at
            )

            if elapsed >= timeout_seconds:
                terminate_process(
                    process
                )

                fail_job(
                    job_id,
                    lock_token,
                    (
                        "Job melewati timeout "
                        f"{timeout_seconds} detik."
                    ),
                    retryable=True,
                    timed_out=True,
                )

                return

            if now >= next_cancel_check:
                if is_cancel_requested(
                    job_id,
                    lock_token,
                ):
                    terminate_process(
                        process
                    )

                    mark_canceled(
                        job_id,
                        lock_token,
                    )

                    return

                next_cancel_check = (
                    now
                    + cancel_poll_seconds
                )

            if now >= next_heartbeat:
                if not heartbeat_job(
                    job_id,
                    lock_token,
                ):
                    terminate_process(
                        process
                    )

                    return

                heartbeat_worker(
                    worker_id,
                    current_job_id=
                        job_id,
                )

                next_heartbeat = (
                    now
                    + heartbeat_seconds
                )

            time.sleep(
                0.2
            )

        process.join(
            timeout=2,
        )

        try:
            outcome = result_queue.get(
                timeout=2,
            )
        except queue.Empty:
            fail_job(
                job_id,
                lock_token,
                (
                    "Worker child berhenti tanpa "
                    "memberikan hasil."
                ),
                retryable=True,
            )

            return

        if bool(
            outcome.get(
                "ok"
            )
        ):
            result = dict(
                outcome.get(
                    "result"
                )
                or {}
            )

            complete_job(
                job_id,
                lock_token,
                result=result,
                artifact_reference=
                    result.get(
                        "artifact_reference"
                    ),
                artifact_filename=
                    result.get(
                        "artifact_filename"
                    ),
            )

            return

        error_message = (
            f"{outcome.get('error_type', 'WorkerError')}: "
            f"{outcome.get('error_message', '')}"
        ).strip()

        trace = str(
            outcome.get(
                "traceback",
                "",
            )
        )

        if trace:
            error_message = (
                error_message
                + "\n"
                + trace
            )

        fail_job(
            job_id,
            lock_token,
            error_message,
            retryable=True,
        )

    finally:
        if process.is_alive():
            terminate_process(
                process
            )

        result_queue.close()


def main() -> int:
    global STOP_REQUESTED

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    poll_seconds = environment_float(
        "DOCURAPI_WORKER_POLL_SECONDS",
        1.0,
        minimum=0.2,
    )

    heartbeat_seconds = (
        environment_float(
            (
                "DOCURAPI_WORKER_"
                "HEARTBEAT_SECONDS"
            ),
            5.0,
            minimum=1.0,
        )
    )

    cancel_poll_seconds = (
        environment_float(
            (
                "DOCURAPI_WORKER_"
                "CANCEL_POLL_SECONDS"
            ),
            1.0,
            minimum=0.2,
        )
    )

    stale_seconds = environment_int(
        "DOCURAPI_WORKER_STALE_SECONDS",
        90,
        minimum=10,
    )

    recovery_interval = (
        environment_float(
            (
                "DOCURAPI_WORKER_"
                "RECOVERY_INTERVAL_SECONDS"
            ),
            30.0,
            minimum=5.0,
        )
    )

    worker_id = (
        os.environ.get(
            "DOCURAPI_WORKER_ID",
            "",
        ).strip()
        or (
            socket.gethostname()
            + ":"
            + str(
                os.getpid()
            )
            + ":"
            + uuid.uuid4().hex[:8]
        )
    )

    initialize_worker_schema()

    register_worker(
        worker_id,
        os.getpid(),
    )

    recovery = recover_stale_jobs(
        stale_seconds
    )

    print(
        "DOCURAPI_WORKER_STARTED",
        flush=True,
    )

    print(
        "worker_id:",
        worker_id,
        flush=True,
    )

    print(
        "stale_recovery:",
        recovery,
        flush=True,
    )

    next_recovery = (
        time.monotonic()
        + recovery_interval
    )

    try:
        while not STOP_REQUESTED:
            now = time.monotonic()

            if now >= next_recovery:
                recovery = (
                    recover_stale_jobs(
                        stale_seconds
                    )
                )

                if (
                    recovery["retried"]
                    or recovery["failed"]
                ):
                    print(
                        "stale_recovery:",
                        recovery,
                        flush=True,
                    )

                next_recovery = (
                    now
                    + recovery_interval
                )

            heartbeat_worker(
                worker_id,
                current_job_id=None,
            )

            job = claim_job(
                worker_id
            )

            if job is None:
                time.sleep(
                    poll_seconds
                )

                continue

            print(
                "JOB_CLAIMED",
                job["job_id"],
                job["job_type"],
                flush=True,
            )

            try:
                run_claimed_job(
                    worker_id,
                    job,
                    heartbeat_seconds=
                        heartbeat_seconds,
                    cancel_poll_seconds=
                        cancel_poll_seconds,
                )

            except BaseException:
                traceback.print_exc()

                try:
                    fail_job(
                        str(
                            job["job_id"]
                        ),
                        str(
                            job["lock_token"]
                        ),
                        traceback.format_exc(),
                        retryable=True,
                    )
                except BaseException:
                    traceback.print_exc()

            finally:
                heartbeat_worker(
                    worker_id,
                    current_job_id=None,
                )

    finally:
        try:
            stop_worker(
                worker_id
            )
        except BaseException:
            traceback.print_exc()

        print(
            "DOCURAPI_WORKER_STOPPED",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()

    raise SystemExit(
        main()
    )
