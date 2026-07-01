from __future__ import annotations

import secrets
from pathlib import Path
from uuid import uuid4

from saas_database import (
    DB_PATH,
    initialize,
    upsert_admin,
)
from services.auth_service import password_hash


initialize()

email = "admin@docurapi.local"
display_name = "Administrator DocuRapi"
password = secrets.token_urlsafe(18)

digest, salt = password_hash(password)

admin = upsert_admin(
    user_id=uuid4().hex,
    email=email,
    display_name=display_name,
    password_hash=digest,
    password_salt=salt,
)

content = f"""AKUN ADMINISTRATOR LOKAL DOCURAPI

Email       : {email}
Kata sandi  : {password}
Paket       : Institution
Login       : http://127.0.0.1:8000/login
Admin       : http://127.0.0.1:8000/admin
Database    : {DB_PATH}

CATATAN
- Simpan file ini secara aman.
- Jangan unggah LOCAL_ADMIN.txt ke GitHub.
- Pembayaran masih menggunakan simulasi.
"""

Path("LOCAL_ADMIN.txt").write_text(
    content,
    encoding="utf-8",
)

print("ADMIN_READY")
print(email)