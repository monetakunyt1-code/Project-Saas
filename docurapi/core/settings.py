from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_NAME = "DocuRapi"
    APP_VERSION = "0.4.2-payment-proof"
    APP_DESCRIPTION = "Backend modular untuk preview dokumen, QRIS manual, bukti pembayaran, dan approval WhatsApp."

    BASE_DIR = BASE_DIR

    STORAGE_DIR = BASE_DIR / "storage"
    UPLOAD_DIR = STORAGE_DIR / "uploads"
    OUTPUT_DIR = STORAGE_DIR / "outputs"
    REPORT_DIR = STORAGE_DIR / "reports"
    TEMPLATE_DIR = STORAGE_DIR / "templates"
    PAYMENT_PROOF_DIR = STORAGE_DIR / "payment_proofs"
    LOG_DIR = BASE_DIR / "logs"

    DATABASE_PATH = Path(
        os.getenv("DOCURAPI_DATABASE_PATH", str(STORAGE_DIR / "docurapi.db"))
    )

    LOG_FILE = LOG_DIR / "docurapi.log"

    MAX_FILE_SIZE = int(os.getenv("DOCURAPI_MAX_FILE_SIZE", str(20 * 1024 * 1024)))
    MAX_PAYMENT_PROOF_SIZE = int(os.getenv("DOCURAPI_MAX_PAYMENT_PROOF_SIZE", str(5 * 1024 * 1024)))

    ALLOWED_EXTENSION = ".docx"
    ALLOWED_PAYMENT_PROOF_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

    DEFAULT_HISTORY_LIMIT = 25
    MAX_HISTORY_LIMIT = 100

    PAYMENT_MODE = os.getenv("DOCURAPI_PAYMENT_MODE", "manual_qris_whatsapp")
    PAYMENT_EXPIRY_HOURS = int(os.getenv("DOCURAPI_PAYMENT_EXPIRY_HOURS", "24"))
    UNIQUE_CODE_MIN = int(os.getenv("DOCURAPI_UNIQUE_CODE_MIN", "101"))
    UNIQUE_CODE_MAX = int(os.getenv("DOCURAPI_UNIQUE_CODE_MAX", "999"))

    PRICE_ANALYZE = int(os.getenv("DOCURAPI_PRICE_ANALYZE", "7000"))
    PRICE_FORMAT = int(os.getenv("DOCURAPI_PRICE_FORMAT", "12000"))
    PRICE_JOURNAL = int(os.getenv("DOCURAPI_PRICE_JOURNAL", "20000"))

    PUBLIC_BASE_URL = os.getenv("DOCURAPI_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    MERCHANT_NAME = os.getenv("DOCURAPI_MERCHANT_NAME", "DocuRapi Merchant")
    ADMIN_WHATSAPP = os.getenv("DOCURAPI_ADMIN_WHATSAPP", "")
    ADMIN_APPROVAL_SECRET = os.getenv(
        "DOCURAPI_ADMIN_APPROVAL_SECRET",
        "dev-admin-secret-change-me",
    )

    QRIS_STATIC_IMAGE_URL = os.getenv(
        "DOCURAPI_QRIS_STATIC_IMAGE_URL",
        "/static/payment/qris-shopee.png",
    )

    CORS_ALLOW_ORIGINS = [
        origin.strip()
        for origin in os.getenv("DOCURAPI_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    @classmethod
    def ensure_directories(cls) -> None:
        for directory in (
            cls.STORAGE_DIR,
            cls.UPLOAD_DIR,
            cls.OUTPUT_DIR,
            cls.REPORT_DIR,
            cls.TEMPLATE_DIR,
            cls.PAYMENT_PROOF_DIR,
            cls.LOG_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
