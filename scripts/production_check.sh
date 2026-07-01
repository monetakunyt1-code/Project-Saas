#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(
    cd "$(
        dirname "${BASH_SOURCE[0]}"
    )" &&
    pwd
)"

ROOT="$(
    cd "$SCRIPT_DIR/.." &&
    pwd
)"

cd "$ROOT"

echo ""
echo "============================================================"
echo "DOCURAPI PRODUCTION CHECK"
echo "============================================================"
echo ""

if [ ! -x ".venv/bin/python" ]; then
    echo "GAGAL: .venv tidak tersedia."
    exit 1
fi

source .venv/bin/activate

echo "[1/5] Dependency"
python -m pip check

echo ""
echo "[2/5] Syntax"
python -m compileall \
    -q \
    app.py \
    services \
    tests

echo ""
echo "[3/5] Unit dan smoke test"
python -m unittest discover \
    -s tests \
    -p "test_*.py" \
    -v

echo ""
echo "[4/5] Git whitespace"
git diff --check

echo ""
echo "[5/5] Application import"

python - <<'PY'
from app import app

paths = {
    path
    for route in app.routes
    if isinstance(
        path := getattr(route, "path", None),
        str,
    )
}

required = {
    "/",
    "/billing",
    "/api/plans",
    "/api/process",
}

missing = sorted(
    required - paths
)

print("Application :", type(app).__name__)
print("Routes      :", len(app.routes))
print("Missing     :", missing)

if missing:
    raise RuntimeError(
        "Route wajib tidak tersedia: "
        + ", ".join(missing)
    )

print("APPLICATION_IMPORT_PASSED")
PY

echo ""
echo "============================================================"
echo "PRODUCTION CHECK BERHASIL"
echo "============================================================"
echo ""
echo "DOCURAPI_PRODUCTION_CHECK_PASSED"
