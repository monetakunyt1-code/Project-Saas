from __future__ import annotations

import os
from pathlib import Path


class Settings:
    APP_NAME = "DocuRapi"
    APP_VERSION = "0.3.0-backend-refactor"
    APP_DESCRIPTION = "Backend modular untuk analisis dan perapihan dokumen akademik."

    BASE_DIR = Path(__file__).resolve().parents[2]

    STORAGE_DIR = BASE_DIR / "storage"
    UPLOAD_DIR = STORAGE_DIR / "uploads"
    OUTPUT_DIR = STORAGE_DIR / "outputs"
    REPORT_DIR = STORAGE_DIR / "reports"
    TEMPLATE_DIR = STORAGE_DIR / "templates"
    LOG_DIR = BASE_DIR / "logs"

    DATABASE_PATH = Path(
        os.getenv("DOCURAPI_DATABASE_PATH", str(STORAGE_DIR / "docurapi.db"))
    )

    LOG_FILE = LOG_DIR / "docurapi.log"

    MAX_FILE_SIZE = int(os.getenv("DOCURAPI_MAX_FILE_SIZE", str(20 * 1024 * 1024)))
    ALLOWED_EXTENSION = ".docx"

    DEFAULT_HISTORY_LIMIT = 25
    MAX_HISTORY_LIMIT = 100

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
            cls.LOG_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
