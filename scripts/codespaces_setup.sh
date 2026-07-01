#!/usr/bin/env bash

set -Eeuo pipefail

WORKSPACE_ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.."
    pwd
)"

cd "$WORKSPACE_ROOT"

echo "=============================================="
echo "DOCURAPI CODESPACES AUTOMATIC SETUP"
echo "=============================================="
echo "Workspace: $WORKSPACE_ROOT"

if command -v python3 >/dev/null 2>&1; then
    SYSTEM_PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    SYSTEM_PYTHON="$(command -v python)"
else
    echo "GAGAL: Python tidak ditemukan."
    exit 1
fi

"$SYSTEM_PYTHON" --version

if [ ! -x ".venv/bin/python" ]; then
    echo "Membuat virtual environment..."

    rm -rf .venv

    "$SYSTEM_PYTHON" -m venv .venv
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

mkdir -p storage logs

python -m pip check

python -m compileall \
    -q \
    -x '(\.venv|storage|logs|__pycache__)' \
    .

echo ""
echo "DOCURAPI_CODESPACES_AUTOMATIC_SETUP_PASSED"
