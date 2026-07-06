#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${DOCURAPI_PUBLIC_BASE_URL:-http://127.0.0.1:8000}"

if [ -z "${DOCURAPI_ADMIN_APPROVAL_SECRET:-}" ]; then
  DOCURAPI_ADMIN_APPROVAL_SECRET="$(python - <<'PY'
from dotenv import dotenv_values
print(dotenv_values(".env").get("DOCURAPI_ADMIN_APPROVAL_SECRET", "dev-admin-secret-change-me"))
PY
)"
  export DOCURAPI_ADMIN_APPROVAL_SECRET
fi

WORKDIR="$(mktemp -d)"
echo "Smoke test workdir: $WORKDIR"

echo ""
echo "1. Check backend health"
curl -sS "$BASE_URL/api/health" -o "$WORKDIR/health.json"
python -m json.tool "$WORKDIR/health.json"

echo ""
echo "2. Create sample DOCX"
python - <<PY
from pathlib import Path
from docx import Document

path = Path("$WORKDIR/sample_smoke.docx")
doc = Document()
doc.add_heading("BAB I PENDAHULUAN", level=1)
doc.add_paragraph("Ini dokumen uji end-to-end DocuRapi.")
doc.add_paragraph("Dokumen ini dibuat otomatis oleh smoke test.")
doc.save(path)
print(path)
PY

echo ""
echo "3. Create fake payment proof PNG"
python - <<PY
import base64
from pathlib import Path

png_base64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
Path("$WORKDIR/bukti_smoke.png").write_bytes(base64.b64decode(png_base64))
print("$WORKDIR/bukti_smoke.png")
PY

echo ""
echo "4. Process document"
curl -sS -X POST "$BASE_URL/api/process" \
  -F "file=@$WORKDIR/sample_smoke.docx" \
  -F "mode=format" \
  -F "preset=skripsi" \
  -o "$WORKDIR/process.json"

python -m json.tool "$WORKDIR/process.json"

JOB_ID="$(python - <<PY
import json
data=json.load(open("$WORKDIR/process.json"))
print(data["job_id"])
PY
)"

TOKEN="$(python - <<PY
import json
data=json.load(open("$WORKDIR/process.json"))
payment_url=data["payment_url"]
print(payment_url.split("token=", 1)[1])
PY
)"

echo ""
echo "JOB_ID=$JOB_ID"

echo ""
echo "5. Checkout QRIS"
curl -sS "$BASE_URL/api/payments/$JOB_ID/checkout?token=$TOKEN" \
  -o "$WORKDIR/checkout.json"

python -m json.tool "$WORKDIR/checkout.json"

echo ""
echo "6. Invoice JSON"
curl -sS "$BASE_URL/api/payments/$JOB_ID/invoice?token=$TOKEN&format=json" \
  -o "$WORKDIR/invoice.json"

python -m json.tool "$WORKDIR/invoice.json"

echo ""
echo "7. Confirm manual payment with proof"
curl -sS -X POST "$BASE_URL/api/payments/$JOB_ID/confirm-manual?token=$TOKEN" \
  -F "payer_name=Smoke Test User" \
  -F "note=Smoke test pembayaran QRIS manual" \
  -F "proof_file=@$WORKDIR/bukti_smoke.png" \
  -o "$WORKDIR/confirm.json"

python -m json.tool "$WORKDIR/confirm.json"

echo ""
echo "8. Admin pending payments via header"
curl -sS "$BASE_URL/api/admin/payments/pending" \
  -H "X-Admin-Secret: $DOCURAPI_ADMIN_APPROVAL_SECRET" \
  -o "$WORKDIR/pending.json"

python -m json.tool "$WORKDIR/pending.json"

echo ""
echo "9. Admin approve payment via header"
curl -sS -X POST "$BASE_URL/api/admin/payments/$JOB_ID/approve" \
  -H "X-Admin-Secret: $DOCURAPI_ADMIN_APPROVAL_SECRET" \
  -o "$WORKDIR/approve.json"

python -m json.tool "$WORKDIR/approve.json"

DOWNLOAD_URL="$(python - <<PY
import json
data=json.load(open("$WORKDIR/approve.json"))
print(data["download_url"])
PY
)"

echo ""
echo "10. Download paid document"
curl -sS -L "$BASE_URL$DOWNLOAD_URL" \
  -o "$WORKDIR/hasil_smoke.docx"

ls -lh "$WORKDIR/hasil_smoke.docx"

echo ""
echo "11. Receipt JSON"
curl -sS "$BASE_URL/api/payments/$JOB_ID/receipt?token=$TOKEN&format=json" \
  -o "$WORKDIR/receipt.json"

python -m json.tool "$WORKDIR/receipt.json"

echo ""
echo "12. Admin dashboard overview"
curl -sS "$BASE_URL/api/admin/dashboard/overview" \
  -H "X-Admin-Secret: $DOCURAPI_ADMIN_APPROVAL_SECRET" \
  -o "$WORKDIR/dashboard.json"

python -m json.tool "$WORKDIR/dashboard.json"

echo ""
echo "=== SMOKE TEST BERHASIL ==="
echo "Workdir hasil test: $WORKDIR"
echo "File hasil download: $WORKDIR/hasil_smoke.docx"
