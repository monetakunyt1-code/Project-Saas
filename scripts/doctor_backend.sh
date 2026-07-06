#!/usr/bin/env bash
set -euo pipefail

echo "=== DocuRapi Backend Doctor ==="

cd "$(dirname "$0")/.."

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

python -m compileall app.py database.py docurapi
pytest -q tests/test_backend.py

if curl -sS http://127.0.0.1:8000/api/health >/tmp/docurapi_health.json 2>/dev/null; then
  echo ""
  echo "Backend running. Health:"
  python -m json.tool /tmp/docurapi_health.json

  ADMIN_SECRET="$(python - <<'PY'
from dotenv import dotenv_values
print(dotenv_values(".env").get("DOCURAPI_ADMIN_APPROVAL_SECRET", "dev-admin-secret-change-me"))
PY
)"

  echo ""
  echo "Readiness:"
  curl -sS http://127.0.0.1:8000/api/admin/system/readiness \
    -H "X-Admin-Secret: $ADMIN_SECRET" \
    | python -m json.tool
else
  echo ""
  echo "Backend belum berjalan di http://127.0.0.1:8000."
  echo "Jalankan: bash scripts/run_backend.sh"
fi

echo ""
echo "=== Doctor selesai ==="
