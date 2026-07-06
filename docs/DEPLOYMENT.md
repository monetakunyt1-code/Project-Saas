# Deployment DocuRapi

## 1. Setup server

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Environment production

```bash
cp .env.production.example .env
```

Wajib ubah:

```env
DOCURAPI_PUBLIC_BASE_URL=https://domain-kamu.com
DOCURAPI_ADMIN_WHATSAPP=628xxxxxxxxxx
DOCURAPI_ADMIN_APPROVAL_SECRET=secret-panjang-random
```

Generate secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. QRIS

Upload QRIS asli ke:

```text
static/payment/qris-shopee.png
```

## 4. Preflight

```bash
bash scripts/preflight_production.sh
```

## 5. Start backend

```bash
bash scripts/start_production.sh
```

## 6. Health check

```bash
curl https://domain-kamu.com/api/health
```

## 7. Readiness admin

```bash
curl https://domain-kamu.com/api/admin/system/readiness -H "X-Admin-Secret: SECRET_ADMIN"
```
