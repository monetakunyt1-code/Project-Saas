from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from docurapi.core.settings import settings
from docurapi.db.connection import connect


VALID_PAYMENT_MODES = {
    "manual_qris_whatsapp",
    "manual_qris",
    "simulation",
    "midtrans",
    "xendit",
}


REQUIRED_TABLES = {
    "jobs",
    "payments",
    "templates",
    "audit_logs",
}


REQUIRED_JOB_COLUMNS = {
    "job_id",
    "original_name",
    "mode",
    "preset",
    "status",
    "payment_status",
    "amount",
    "base_amount",
    "unique_code",
    "invoice_expires_at",
    "access_token",
}


REQUIRED_PAYMENT_COLUMNS = {
    "payment_id",
    "job_id",
    "provider",
    "amount",
    "status",
    "proof_file_name",
    "proof_path",
    "proof_content_type",
}


def ensure_admin_secret(secret: str) -> None:
    if secret != settings.ADMIN_APPROVAL_SECRET:
        raise HTTPException(status_code=403, detail="Secret admin tidak valid.")


def table_names() -> set[str]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    return {row["name"] for row in rows}


def column_names(table_name: str) -> set[str]:
    with connect() as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()

    return {row["name"] for row in rows}


def check_database() -> dict[str, Any]:
    tables = table_names()

    missing_tables = sorted(REQUIRED_TABLES - tables)

    jobs_columns = column_names("jobs") if "jobs" in tables else set()
    payments_columns = column_names("payments") if "payments" in tables else set()

    missing_job_columns = sorted(REQUIRED_JOB_COLUMNS - jobs_columns)
    missing_payment_columns = sorted(REQUIRED_PAYMENT_COLUMNS - payments_columns)

    ok = not missing_tables and not missing_job_columns and not missing_payment_columns

    return {
        "ok": ok,
        "database_path": str(settings.DATABASE_PATH),
        "missing_tables": missing_tables,
        "missing_job_columns": missing_job_columns,
        "missing_payment_columns": missing_payment_columns,
    }


def check_directories() -> dict[str, Any]:
    directories = {
        "storage": settings.STORAGE_DIR,
        "uploads": settings.UPLOAD_DIR,
        "outputs": settings.OUTPUT_DIR,
        "reports": settings.REPORT_DIR,
        "templates": settings.TEMPLATE_DIR,
        "payment_proofs": settings.PAYMENT_PROOF_DIR,
        "logs": settings.LOG_DIR,
    }

    result = {}

    for name, path in directories.items():
        result[name] = {
            "path": str(path),
            "exists": path.exists(),
            "is_dir": path.is_dir(),
        }

    ok = all(item["exists"] and item["is_dir"] for item in result.values())

    return {
        "ok": ok,
        "directories": result,
    }


def check_payment_config() -> dict[str, Any]:
    payment_mode = settings.PAYMENT_MODE.lower().strip()
    qris_path = None
    qris_exists = None

    if settings.QRIS_STATIC_IMAGE_URL.startswith("/static/"):
        relative = settings.QRIS_STATIC_IMAGE_URL.removeprefix("/static/")
        qris_path = settings.BASE_DIR / "static" / relative
        qris_exists = qris_path.exists()

    warnings = []

    if payment_mode not in VALID_PAYMENT_MODES:
        warnings.append(f"Payment mode tidak dikenal: {settings.PAYMENT_MODE}")

    if payment_mode in {"manual_qris_whatsapp", "manual_qris"} and not settings.ADMIN_WHATSAPP:
        warnings.append("DOCURAPI_ADMIN_WHATSAPP belum diisi.")

    if payment_mode in {"manual_qris_whatsapp", "manual_qris"} and qris_exists is False:
        warnings.append("File QRIS static belum ditemukan di static/payment/qris-shopee.png.")

    return {
        "ok": payment_mode in VALID_PAYMENT_MODES and bool(settings.ADMIN_APPROVAL_SECRET),
        "payment_mode": settings.PAYMENT_MODE,
        "merchant_name": settings.MERCHANT_NAME,
        "admin_whatsapp_configured": bool(settings.ADMIN_WHATSAPP),
        "admin_secret_configured": bool(settings.ADMIN_APPROVAL_SECRET),
        "public_base_url": settings.PUBLIC_BASE_URL,
        "qris_static_image_url": settings.QRIS_STATIC_IMAGE_URL,
        "qris_static_image_path": str(qris_path) if qris_path else None,
        "qris_static_image_exists": qris_exists,
        "warnings": warnings,
    }


def check_pricing() -> dict[str, Any]:
    prices = {
        "analyze": settings.PRICE_ANALYZE,
        "format": settings.PRICE_FORMAT,
        "journal": settings.PRICE_JOURNAL,
    }

    invalid = {key: value for key, value in prices.items() if value <= 0}

    return {
        "ok": not invalid,
        "prices": prices,
        "invalid": invalid,
    }


def check_retention() -> dict[str, Any]:
    values = {
        "failed_days": settings.RETENTION_FAILED_DAYS,
        "unpaid_days": settings.RETENTION_UNPAID_DAYS,
        "rejected_days": settings.RETENTION_REJECTED_DAYS,
        "expired_days": settings.RETENTION_EXPIRED_DAYS,
        "audit_log_days": settings.RETENTION_AUDIT_LOG_DAYS,
    }

    invalid = {key: value for key, value in values.items() if value < 0}

    return {
        "ok": not invalid,
        "values": values,
        "invalid": invalid,
    }


def get_system_readiness(secret: str) -> dict[str, Any]:
    ensure_admin_secret(secret)

    database = check_database()
    directories = check_directories()
    payment_config = check_payment_config()
    pricing = check_pricing()
    retention = check_retention()

    checks = {
        "database": database,
        "directories": directories,
        "payment_config": payment_config,
        "pricing": pricing,
        "retention": retention,
    }

    ready = all(check["ok"] for check in checks.values())

    return {
        "success": True,
        "ready": ready,
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "checks": checks,
    }
