# Release Notes DocuRapi

## MVP Backend + Web Checkpoint

Branch:

```text
chore/codespaces-stabilization-20260706-114140
```

## Status Umum

DocuRapi sudah berada pada checkpoint MVP internal. Backend core sudah stabil, payment flow manual QRIS sudah berjalan, admin dashboard tersedia, dan UI dasar untuk user serta admin sudah dibuat.

## Fitur Selesai

### Backend Core

- FastAPI modular architecture
- Health endpoint
- Processing endpoint untuk dokumen `.docx`
- Job preview, report, dan download endpoint
- SQLite database initialization dan migration otomatis
- OpenAPI export script

### Payment Flow

- Manual QRIS payment mode
- QRIS statis
- Nominal unik pembayaran
- Invoice expiry
- Refresh invoice
- Upload bukti pembayaran
- WhatsApp admin approval link
- Signed admin action token untuk approve, reject, dan view
- Status unpaid, pending_verification, paid, rejected, expired

### Invoice dan Receipt

- Public invoice page
- Public invoice JSON
- Receipt page setelah paid
- Receipt JSON setelah paid
- Payment status page
- Download terbuka hanya setelah paid

### Admin

- Admin dashboard backend
- Admin dashboard web
- Admin secret via header `X-Admin-Secret`
- Pending payment list
- View proof pembayaran
- Approve payment
- Reject payment
- System readiness check
- Audit log
- Cleanup policy
- Cleanup dry-run

### UI Web

- Guest upload page
- Payment confirmation form
- Upload bukti pembayaran dari browser
- Payment status page
- Admin dashboard page
- Shared navigation
- Resume last guest job via localStorage
- UI polish dasar

### Testing dan Maintenance

- Backend test suite
- Final backend check script
- Smoke test manual QRIS end-to-end
- Doctor backend script
- Production preflight script
- Deployment guide
- Final runbook uji akhir

## Yang Belum Production-Ready

- Domain production belum dipasang
- QRIS asli belum dipasang ke `static/payment/qris-shopee.png`
- Admin secret production belum digenerate
- Admin WhatsApp production perlu dikonfirmasi
- Hosting atau VPS belum disiapkan
- Backup policy production belum dijalankan
- UI masih MVP, belum final komersial

## Perkiraan Progres

- Backend MVP: 90%
- Payment flow: 90%
- Admin backend: 85%
- Testing backend: 90%
- UI user: 65%
- UI admin: 60%
- Deployment prep: 70%
- Production readiness: 50%

## Uji Akhir

Gunakan dokumen berikut:

```text
docs/FINAL_RUNBOOK.md
```

Urutan utama:

```text
1. Run final_backend_check.sh
2. Run backend
3. Test upload user
4. Test invoice
5. Test payment confirmation
6. Test admin dashboard
7. Test approve payment
8. Test status paid
9. Test download
10. Test receipt
11. Run smoke_manual_qris_flow.sh
```

## Catatan Release

Checkpoint ini layak dijadikan dasar sebelum pengujian akhir. Setelah uji akhir selesai, langkah berikutnya adalah memperbaiki bug UI, memasang QRIS asli, lalu menyiapkan deployment production.
