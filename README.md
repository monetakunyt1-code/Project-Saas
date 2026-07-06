# DocuRapi

DocuRapi adalah backend dan web MVP untuk memproses dokumen akademik `.docx` dengan alur guest upload, preview, pembayaran QRIS manual, verifikasi admin via WhatsApp, dan download hasil setelah pembayaran disetujui.

## Fitur utama

- Guest upload tanpa login
- Processing dokumen `.docx`
- Preview dan report hasil proses
- Manual QRIS payment flow
- Nominal unik pembayaran
- Upload bukti pembayaran
- Admin approval via WhatsApp link
- Admin dashboard web
- Invoice dan receipt page
- Payment status page
- Audit log
- Cleanup policy
- System readiness check
- Smoke test end-to-end

## Tech stack

- Python
- FastAPI
- SQLite
- python-docx
- HTML, CSS, JavaScript
- Pytest

## Menjalankan backend development

```bash
cd /workspaces/Project-Saas
source .venv/bin/activate
bash scripts/run_backend.sh
```

Buka:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/admin
```

Jika menggunakan GitHub Codespaces, buka melalui tab PORTS pada port 8000.

## Test backend

```bash
bash scripts/final_backend_check.sh
```

## Smoke test flow QRIS manual

```bash
bash scripts/smoke_manual_qris_flow.sh
```

## OpenAPI export

```bash
python scripts/export_openapi.py
```

Output:

```text
docs/openapi.json
```

## Production

Lihat panduan:

```text
docs/DEPLOYMENT.md
```

Copy environment production:

```bash
cp .env.production.example .env
```

Wajib isi domain, nomor WhatsApp admin, admin secret, dan file QRIS asli.
