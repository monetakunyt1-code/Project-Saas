# DocuRapi Features

## Guest User

- Upload dokumen `.docx` tanpa login
- Memilih mode layanan: analyze, format, journal
- Melihat preview hasil
- Melihat report hasil
- Melihat invoice pembayaran
- Membayar via QRIS statis
- Menggunakan nominal unik
- Upload bukti pembayaran
- Cek status pembayaran
- Download dokumen setelah pembayaran disetujui
- Melihat receipt pembayaran
- Resume dokumen terakhir dari localStorage browser

## Admin

- Login sederhana menggunakan admin secret
- Dashboard overview
- System readiness check
- Melihat pembayaran pending
- Melihat bukti pembayaran
- Approve pembayaran
- Reject pembayaran
- Melihat audit log
- Menjalankan cleanup dry-run
- Menjalankan cleanup file lama

## Payment Flow

```text
Upload dokumen
→ Preview/report dibuat
→ Invoice nominal unik dibuat
→ User bayar QRIS statis
→ User upload bukti pembayaran
→ Admin menerima link WhatsApp
→ Admin cek transaksi merchant
→ Admin approve/reject
→ Download dibuka jika paid
```

## Backend Maintenance

- SQLite migration otomatis
- Audit log
- Cleanup policy
- OpenAPI export
- Doctor script
- Final backend validation script
- End-to-end smoke test script
