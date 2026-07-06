# Final Runbook Uji Akhir DocuRapi

Runbook ini dipakai untuk uji akhir setelah seluruh fitur selesai.

## A. Persiapan

```bash
cd /workspaces/Project-Saas
source .venv/bin/activate
```

Pastikan `.env` sudah berisi:

```env
DOCURAPI_PAYMENT_MODE=manual_qris_whatsapp
DOCURAPI_ADMIN_WHATSAPP=628xxxxxxxxxx
DOCURAPI_ADMIN_APPROVAL_SECRET=secret-admin
DOCURAPI_PUBLIC_BASE_URL=https://url-codespaces-atau-domain
```

## B. Final backend check

```bash
bash scripts/final_backend_check.sh
```

Target:

```text
27 passed
FINAL BACKEND CHECK PASSED
```

## C. Jalankan backend

```bash
fuser -k 8000/tcp || true
bash scripts/run_backend.sh
```

Buka melalui Codespaces PORTS port 8000.

## D. Uji halaman user

Buka:

```text
/ 
```

Langkah:

1. Upload file `.docx` kecil.
2. Pilih mode `format`.
3. Pilih preset `skripsi`.
4. Klik Proses Dokumen.
5. Pastikan muncul Job ID, total bayar, kode unik, invoice, preview, report, dan status.
6. Pastikan panel Dokumen Terakhir muncul.

## E. Uji invoice

Klik tombol Lihat Invoice.

Validasi:

- Job ID tampil.
- Harga dasar tampil.
- Kode unik tampil.
- Total bayar tampil.
- Status invoice tampil.
- Expired tampil.

## F. Uji konfirmasi pembayaran

Di halaman user:

1. Isi nama pembayar.
2. Isi catatan.
3. Upload bukti pembayaran JPG/PNG/PDF.
4. Klik Kirim Konfirmasi.
5. Pastikan muncul link WhatsApp admin atau pesan menunggu verifikasi.

## G. Uji admin dashboard

Buka:

```text
/admin
```

Langkah:

1. Masukkan admin secret dari `.env`.
2. Klik Simpan Secret.
3. Klik Load Dashboard.
4. Pastikan readiness, overview, dan pending payment tampil.

## H. Uji approve pembayaran

Di admin dashboard:

1. Cari pending payment.
2. Klik Lihat Bukti.
3. Klik Approve.
4. Pastikan pending payment hilang atau status berubah.

## I. Uji status dan download user

Buka halaman status dari tombol Cek Status.

Validasi setelah approve:

- Status menjadi paid.
- Tombol Download Dokumen muncul.
- Tombol Lihat Receipt muncul.
- File hasil bisa di-download.

## J. Uji receipt

Klik Lihat Receipt.

Validasi:

- Status PAID.
- Job ID tampil.
- Payment reference tampil.
- Total dibayar tampil.
- Paid at tampil.

## K. Uji smoke test otomatis

Di terminal baru:

```bash
export DOCURAPI_ADMIN_APPROVAL_SECRET=$(python - <<'PY'
from dotenv import dotenv_values
print(dotenv_values(".env").get("DOCURAPI_ADMIN_APPROVAL_SECRET", "dev-admin-secret-change-me"))
PY
)

bash scripts/smoke_manual_qris_flow.sh
```

Target:

```text
SMOKE TEST BERHASIL
```

## L. Uji cleanup dry-run

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/admin/cleanup/run?dry_run=true" \
  -H "X-Admin-Secret: $DOCURAPI_ADMIN_APPROVAL_SECRET" \
  | python -m json.tool
```

Validasi:

- success true.
- dry_run true.
- summary tampil.

## M. Kriteria selesai MVP

- [ ] Backend final check lolos.
- [ ] UI user bisa upload dokumen.
- [ ] Invoice tampil.
- [ ] Konfirmasi pembayaran berhasil.
- [ ] Admin dashboard bisa load.
- [ ] Admin bisa approve.
- [ ] User bisa download setelah paid.
- [ ] Receipt tampil.
- [ ] Smoke test berhasil.
- [ ] Cleanup dry-run berhasil.
