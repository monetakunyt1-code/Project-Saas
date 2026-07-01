#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"

PID_FILE="$ROOT/logs/docurapi_worker.pid"

if [[ ! -f "$PID_FILE" ]]; then
    echo "Worker tidak sedang berjalan."
    exit 0
fi

worker_pid="$(cat "$PID_FILE" 2>/dev/null || true)"

if [[ -z "$worker_pid" ]]; then
    rm -f "$PID_FILE"
    echo "PID worker kosong."
    exit 0
fi

if ! kill -0 "$worker_pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "Worker sudah berhenti."
    exit 0
fi

command_line="$(
    tr '\0' ' ' < "/proc/$worker_pid/cmdline" 2>/dev/null || true
)"

if [[ "$command_line" != *"docurapi_worker.py"* ]]; then
    echo "GAGAL: PID bukan proses DocuRapi worker."
    exit 1
fi

kill -TERM "$worker_pid"

for attempt in $(seq 1 20); do
    if ! kill -0 "$worker_pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "DOCURAPI_WORKER_STOPPED"
        exit 0
    fi

    sleep 1
done

kill -KILL "$worker_pid" 2>/dev/null || true
rm -f "$PID_FILE"

echo "DOCURAPI_WORKER_FORCE_STOPPED"
