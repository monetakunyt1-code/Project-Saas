#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

echo "=== DocuRapi Production Preflight ==="

if [ ! -f ".env" ]; then
  echo "ERROR: .env belum ada."
  exit 1
fi

python -m compileall app.py database.py docurapi
pytest -q tests/test_backend.py
python scripts/export_openapi.py

echo "Preflight selesai."
