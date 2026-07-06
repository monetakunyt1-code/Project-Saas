# Final Checklist DocuRapi

## Backend

- [x] FastAPI app modular
- [x] Health endpoint
- [x] Processing endpoint
- [x] Jobs endpoint
- [x] Payment endpoint
- [x] Admin payment endpoint
- [x] Admin dashboard endpoint
- [x] Cleanup endpoint
- [x] System readiness endpoint
- [x] Pricing endpoint
- [x] Invoice endpoint
- [x] Receipt endpoint

## Payment

- [x] QRIS manual
- [x] WhatsApp admin approval link
- [x] Signed admin action token
- [x] Upload bukti pembayaran
- [x] Nominal unik
- [x] Invoice expiry
- [x] Refresh invoice
- [x] Paid/rejected/pending/expired status

## UI

- [x] Guest upload page
- [x] Payment status page
- [x] Invoice page
- [x] Receipt page
- [x] Admin dashboard page
- [x] Shared navigation
- [x] Resume last job localStorage
- [ ] UI polish final
- [ ] Mobile polish final

## Testing

- [x] Backend unit tests
- [x] Final backend check script
- [x] Smoke test manual QRIS flow
- [ ] Final browser test
- [ ] Final production preflight

## Production Preparation

- [x] .env.production.example
- [x] start_production.sh
- [x] preflight_production.sh
- [x] deployment guide
- [ ] Domain production
- [ ] QRIS static image asli
- [ ] Admin WhatsApp production
- [ ] Admin secret production
- [ ] Hosting/VPS
- [ ] Backup policy production

## Final Test Flow

```text
1. Run final_backend_check.sh
2. Run backend
3. Open guest UI
4. Upload sample DOCX
5. Check invoice
6. Confirm payment with proof
7. Open admin dashboard
8. Approve payment
9. Check status page
10. Download result
11. Check receipt
12. Run smoke_manual_qris_flow.sh
```
