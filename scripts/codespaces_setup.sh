#!/usr/bin/env bash

set -euo pipefail

cd /workspaces/Project-Saas

echo "=============================================="
echo "DOCURAPI CODESPACES AUTOMATIC SETUP"
echo "=============================================="

python --version

if [ ! -d ".venv" ]; then
    python -m venv .venv
    echo "Virtual environment dibuat."
else
    echo "Virtual environment sudah tersedia."
fi

source .venv/bin/activate

python -m pip install \
    --upgrade \
    pip \
    setuptools \
    wheel

if [ ! -f "requirements.txt" ]; then
    echo "GAGAL: requirements.txt tidak ditemukan."
    exit 1
fi

python -m pip install \
    -r requirements.txt

mkdir -p storage
mkdir -p logs

python -m pip check

python -m compileall \
    -q \
    -x '(\.venv|storage|logs|__pycache__)' \
    .

echo ""
echo "DOCURAPI_CODESPACES_AUTOMATIC_SETUP_PASSED"
