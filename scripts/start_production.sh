#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

if [ ! -f ".env" ]; then
  echo "ERROR: .env belum ada. Copy .env.production.example menjadi .env."
  exit 1
fi

python -c "from docurapi.db.connection import initialize_database; initialize_database(); print(\"Database initialized.\")"

PORT="${DOCURAPI_PORT:-8000}"

exec uvicorn app:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips="*"
