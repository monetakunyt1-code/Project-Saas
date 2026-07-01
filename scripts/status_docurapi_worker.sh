#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"

PID_FILE="$ROOT/logs/docurapi_worker.pid"
LOG_FILE="$ROOT/logs/docurapi_worker.log"

if [[ ! -f "$PID_FILE" ]]; then
    echo "Worker status: STOPPED"
    exit 1
fi

worker_pid="$(cat "$PID_FILE" 2>/dev/null || true)"

if [[ -z "$worker_pid" ]]; then
    rm -f "$PID_FILE"
    echo "Worker status: STOPPED"
    exit 1
fi

if ! kill -0 "$worker_pid" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "Worker status: STOPPED"
    exit 1
fi

command_line="$(
    tr '\0' ' ' < "/proc/$worker_pid/cmdline" 2>/dev/null || true
)"

if [[ "$command_line" != *"docurapi_worker.py"* ]]; then
    echo "Worker status: INVALID PID"
    exit 1
fi

echo "Worker status: RUNNING"
echo "PID          : $worker_pid"
echo "Log          : $LOG_FILE"
