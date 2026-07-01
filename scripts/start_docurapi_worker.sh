#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"

PID_FILE="$ROOT/logs/docurapi_worker.pid"
LOG_FILE="$ROOT/logs/docurapi_worker.log"

mkdir -p "$ROOT/logs"

existing_pid=""

if [[ -f "$PID_FILE" ]]; then
    existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
fi

if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    command_line="$(
        tr '\0' ' ' \
            < "/proc/$existing_pid/cmdline" \
            2>/dev/null \
            || true
    )"

    if [[ "$command_line" == *"docurapi_worker.py"* ]]; then
        echo "Worker sudah berjalan."
        echo "PID: $existing_pid"
        echo "Log: $LOG_FILE"
        exit 0
    fi
fi

rm -f "$PID_FILE"

if [[ -z "${DOCURAPI_DATABASE_URL:-}" ]] \
    && [[ -z "${DATABASE_URL:-}" ]] \
    && [[ -z "${POSTGRES_URL:-}" ]]; then

    eval "$(
        bash scripts/start_local_postgres.sh --print-env
    )"
fi

export DOCURAPI_OBJECT_STORAGE_BACKEND="${DOCURAPI_OBJECT_STORAGE_BACKEND:-local}"
export DOCURAPI_OBJECT_STORAGE_LOCAL_ROOT="${DOCURAPI_OBJECT_STORAGE_LOCAL_ROOT:-$ROOT/storage/object_store}"
export DOCURAPI_OBJECT_STORAGE_CACHE_ROOT="${DOCURAPI_OBJECT_STORAGE_CACHE_ROOT:-/tmp/docurapi-object-cache}"
export DOCURAPI_OBJECT_STORAGE_KEEP_LOCAL_COPY="${DOCURAPI_OBJECT_STORAGE_KEEP_LOCAL_COPY:-true}"

export DOCURAPI_WORKER_POLL_SECONDS="${DOCURAPI_WORKER_POLL_SECONDS:-1}"
export DOCURAPI_WORKER_HEARTBEAT_SECONDS="${DOCURAPI_WORKER_HEARTBEAT_SECONDS:-2}"
export DOCURAPI_WORKER_CANCEL_POLL_SECONDS="${DOCURAPI_WORKER_CANCEL_POLL_SECONDS:-0.5}"
export DOCURAPI_WORKER_STALE_SECONDS="${DOCURAPI_WORKER_STALE_SECONDS:-30}"
export DOCURAPI_WORKER_RECOVERY_INTERVAL_SECONDS="${DOCURAPI_WORKER_RECOVERY_INTERVAL_SECONDS:-10}"

PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python)"
fi

nohup "$PYTHON" scripts/docurapi_worker.py \
    >> "$LOG_FILE" \
    2>&1 &

worker_pid="$!"

echo "$worker_pid" > "$PID_FILE"

for attempt in $(seq 1 20); do
    if ! kill -0 "$worker_pid" 2>/dev/null; then
        echo "GAGAL: worker berhenti saat startup."
        tail -n 160 "$LOG_FILE" || true
        rm -f "$PID_FILE"
        exit 1
    fi

    if grep -q \
        "DOCURAPI_WORKER_STARTED" \
        "$LOG_FILE" \
        2>/dev/null; then

        echo "DOCURAPI_WORKER_STARTED"
        echo "PID: $worker_pid"
        echo "Log: $LOG_FILE"
        exit 0
    fi

    sleep 1
done

echo "GAGAL: marker startup worker tidak ditemukan."
tail -n 160 "$LOG_FILE" || true
exit 1
