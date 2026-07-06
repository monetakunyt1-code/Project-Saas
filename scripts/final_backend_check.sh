#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== DocuRapi Final Backend Check ==="

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

echo ""
echo "1. Compile Python files"
python -m compileall app.py database.py docurapi

echo ""
echo "2. Run backend tests"
pytest -q tests/test_backend.py

echo ""
echo "3. Export OpenAPI schema"
python scripts/export_openapi.py

echo ""
echo "4. Check important files"
test -f app.py
test -f requirements.txt
test -f scripts/run_backend.sh
test -f scripts/doctor_backend.sh
test -f scripts/smoke_manual_qris_flow.sh
test -f scripts/export_openapi.py
test -f docs/openapi.json
test -d docurapi
test -d docurapi/routers
test -d docurapi/services
test -d docurapi/db
test -d static/payment

echo ""
echo "5. Git status"
git status --short

echo ""
echo "6. Recent commits"
git log --oneline -5

echo ""
echo "=== FINAL BACKEND CHECK PASSED ==="
