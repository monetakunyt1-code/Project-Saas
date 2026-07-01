#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(
    cd "$(
        dirname "${BASH_SOURCE[0]}"
    )/.." &&
    pwd
)"

cd "$ROOT"

export PAGER=cat
export PSQL_PAGER=cat
export DOCURAPI_RUNTIME_BACKEND="postgresql"

if [ -z "${DOCURAPI_DATABASE_URL:-}" ] \
    && [ -z "${DATABASE_URL:-}" ] \
    && [ -z "${POSTGRES_URL:-}" ]
then
    if [ ! -x "scripts/start_local_postgres.sh" ]; then
        echo "GAGAL: URL PostgreSQL tidak tersedia."
        exit 1
    fi

    bash scripts/start_local_postgres.sh --check \
        >/dev/null

    eval "$(
        bash scripts/start_local_postgres.sh --print-env
    )"
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
else
    PYTHON="$(
        command -v python3 \
        || command -v python
    )"
fi

if [ -z "${PYTHON:-}" ]; then
    echo "GAGAL: Python tidak ditemukan."
    exit 1
fi

"$PYTHON" - <<'PY'
from services import database_adapter
from services.postgres_connection import ping_postgres

information = ping_postgres()

print(
    "Starting DocuRapi with PostgreSQL:",
    information["database_name"],
)

if database_adapter.backend_name() != "postgresql":
    raise RuntimeError(
        "Launcher PostgreSQL tidak mengaktifkan backend PostgreSQL."
    )
PY

exec "$PYTHON" -m uvicorn \
    app:app \
    --host "${DOCURAPI_HOST:-0.0.0.0}" \
    --port "${PORT:-8000}"
