#!/usr/bin/env bash

set -euo pipefail

cd /workspaces/Project-Saas

if [ ! -d ".venv" ]; then
    echo "GAGAL: .venv belum tersedia."
    echo "Jalankan: bash scripts/codespaces_setup.sh"
    exit 1
fi

source .venv/bin/activate

echo ""
echo "=============================================="
echo "MENJALANKAN DOCURAPI"
echo "=============================================="
echo ""
echo "Port: 8000"
echo "Hentikan server dengan Ctrl+C."
echo ""

exec python -m uvicorn app:app \
    --host 0.0.0.0 \
    --port 8000
