from __future__ import annotations

import hashlib
import importlib
import os
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config import STORAGE_DIR
from notification_database import (
    consume_token_record,
    create_notification_record,
    create_token_record,
    email_is_verified,
    enqueue_email_record,
    get_active_token_by_hash,
    get_email_record,
    list_email_outbox,
    list_notifications,
    list_pending_email_records,
    mark_email_failed,
    mark_email_sent,
    record_verified_email,
    unread_notification_count,
)


BASE_DIR = Path(
    __file__
).resolve().parent.parent

OUTBOX_FILE_DIRECTORY = (
    STORAGE_DIR
    / "notifications"
    / "outbox_files"
)

OUTBOX_FILE_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def delivery_mode() -> str:
    return os.getenv(
        "DOCURAPI_EMAIL_MODE",
        "local",
    ).strip().lower()


def public_base_url() -> str:
    return os.getenv(
        "DOCURAPI_PUBLIC_BASE_URL",
        "http://127.0.0.1:8000",
    ).rstrip("/")


def email_from_address() -> str:
    return os.getenv(
        "DOCURAPI_EMAIL_FROM",
        "noreply@docurapi.local",
    )


def email_from_name() -> str:
    return os.getenv(
        "DOCURAPI_EMAIL_FROM_NAME",
        "DocuRapi",
    )


def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    action_url: str | None = None,
    workspace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return create_notification_record(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        workspace_id=workspace_id,
        metadata=metadata,
    )


def user_notifications(
    user_id: str,
    limit: int = 100,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    return list_notifications(
        user_id=user_id,
        limit=limit,
        unread_only=unread_only,
    )


def user_unread_count(
    user_id: str,
) -> int:
    return unread_notification_count(
        user_id
    )


def enqueue_email(
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    template_key: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    return enqueue_email_record(
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template_key=template_key,
        user_id=user_id,
    )


def build_email_message(
    email_record: dict[str, Any],
) -> EmailMessage:
    message = EmailMessage()

    message["Subject"] = email_record[
        "subject"
    ]

    message["From"] = (
        f"{email_from_name()} "
        f"<{email_from_address()}>"
    )

    message["To"] = email_record[
        "recipient"
    ]

    message.set_content(
        email_record["body_text"]
    )

    body_html = email_record.get(
        "body_html"
    )

    if body_html:
        message.add_alternative(
            body_html,
            subtype="html",
        )

    return message


def deliver_email_record(
    email_record: dict[str, Any],
) -> dict[str, Any]:
    email_id = email_record["email_id"]

    message = build_email_message(
        email_record
    )

    mode = delivery_mode()

    try:
        if mode == "local":
            file_path = (
                OUTBOX_FILE_DIRECTORY
                / f"{email_id}.eml"
            )

            file_path.write_bytes(
                message.as_bytes()
            )

            mark_email_sent(
                email_id,
                str(file_path),
            )

            return {
                "email_id": email_id,
                "status": "sent",
                "mode": "local",
                "local_file_path": str(
                    file_path
                ),
            }

        if mode != "smtp":
            raise RuntimeError(
                "DOCURAPI_EMAIL_MODE harus "
                "bernilai local atau smtp."
            )

        host = os.getenv(
            "DOCURAPI_SMTP_HOST",
            "",
        ).strip()

        port = int(
            os.getenv(
                "DOCURAPI_SMTP_PORT",
                "587",
            )
        )

        username = os.getenv(
            "DOCURAPI_SMTP_USERNAME",
            "",
        )

        password = os.getenv(
            "DOCURAPI_SMTP_PASSWORD",
            "",
        )

        use_ssl = (
            os.getenv(
                "DOCURAPI_SMTP_SSL",
                "0",
            )
            == "1"
        )

        use_starttls = (
            os.getenv(
                "DOCURAPI_SMTP_STARTTLS",
                "1",
            )
            == "1"
        )

        if not host:
            raise RuntimeError(
                "DOCURAPI_SMTP_HOST belum diisi."
            )

        smtp_class = (
            smtplib.SMTP_SSL
            if use_ssl
            else smtplib.SMTP
        )

        with smtp_class(
            host,
            port,
            timeout=30,
        ) as smtp:
            if (
                use_starttls
                and not use_ssl
            ):
                smtp.starttls()

            if username:
                smtp.login(
                    username,
                    password,
                )

            smtp.send_message(
                message
            )

        mark_email_sent(
            email_id
        )

        return {
            "email_id": email_id,
            "status": "sent",
            "mode": "smtp",
        }

    except Exception as exc:
        mark_email_failed(
            email_id,
            str(exc),
        )

        return {
            "email_id": email_id,
            "status": "failed",
            "mode": mode,
            "error": str(exc),
        }


def enqueue_and_deliver_email(
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    template_key: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    email_record = enqueue_email(
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template_key=template_key,
        user_id=user_id,
    )

    return deliver_email_record(
        email_record
    )


def send_pending_emails(
    limit: int = 50,
) -> dict[str, Any]:
    records = list_pending_email_records(
        limit=limit
    )

    results = [
        deliver_email_record(record)
        for record in records
    ]

    return {
        "processed": len(results),
        "sent": sum(
            1
            for item in results
            if item["status"] == "sent"
        ),
        "failed": sum(
            1
            for item in results
            if item["status"] == "failed"
        ),
        "results": results,
    }


def issue_email_token(
    user_id: str | None,
    email: str,
    purpose: str,
    ttl_minutes: int = 60,
) -> str:
    raw_token = secrets.token_urlsafe(
        40
    )

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    expires_at = (
        utc_now()
        + timedelta(
            minutes=max(
                5,
                min(
                    int(ttl_minutes),
                    1440,
                ),
            )
        )
    ).isoformat()

    create_token_record(
        user_id=user_id,
        email=email,
        purpose=purpose,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    return raw_token


def validate_email_token(
    raw_token: str,
    purpose: str,
) -> dict[str, Any] | None:
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    token_record = get_active_token_by_hash(
        token_hash,
        purpose,
    )

    if not token_record:
        return None

    try:
        expires_at = datetime.fromisoformat(
            token_record["expires_at"]
        )
    except ValueError:
        return None

    if expires_at <= utc_now():
        return None

    return token_record


def consume_email_token(
    token_record: dict[str, Any],
) -> bool:
    return consume_token_record(
        token_record["token_id"]
    )


def send_verification_email(
    user_id: str,
    email: str,
) -> dict[str, Any]:
    token = issue_email_token(
        user_id=user_id,
        email=email,
        purpose="email_verification",
        ttl_minutes=120,
    )

    verification_url = (
        public_base_url()
        + "/notifications?verify_token="
        + token
    )

    subject = (
        "Verifikasi email akun DocuRapi"
    )

    body_text = (
        "Halo,\n\n"
        "Gunakan tautan berikut untuk "
        "memverifikasi email akun DocuRapi:\n\n"
        f"{verification_url}\n\n"
        "Tautan berlaku selama 120 menit.\n"
    )

    body_html = (
        "<h2>Verifikasi Email DocuRapi</h2>"
        "<p>Klik tombol berikut untuk "
        "memverifikasi email Anda.</p>"
        f"<p><a href='{verification_url}'>"
        "Verifikasi Email</a></p>"
        "<p>Tautan berlaku selama 120 menit.</p>"
    )

    return enqueue_and_deliver_email(
        recipient=email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        template_key="email_verification",
        user_id=user_id,
    )


def confirm_email_verification(
    raw_token: str,
) -> dict[str, Any]:
    token_record = validate_email_token(
        raw_token,
        "email_verification",
    )

    if not token_record:
        return {
            "success": False,
            "message": (
                "Token verifikasi tidak valid "
                "atau sudah kedaluwarsa."
            ),
        }

    record_verified_email(
        email=token_record["email"],
        user_id=token_record.get(
            "user_id"
        ),
    )

    update_application_email_status(
        token_record["email"]
    )

    consume_email_token(
        token_record
    )

    if token_record.get("user_id"):
        create_notification(
            user_id=token_record["user_id"],
            title="Email berhasil diverifikasi",
            message=(
                "Alamat email akun Anda "
                "telah berhasil diverifikasi."
            ),
            notification_type="success",
            action_url="/account",
        )

    return {
        "success": True,
        "message": (
            "Email berhasil diverifikasi."
        ),
        "email": token_record["email"],
    }


def user_database_path() -> Path | None:
    candidates = [
        STORAGE_DIR
        / "saas"
        / "saas.db",
        STORAGE_DIR
        / "saas.db",
    ]

    try:
        module = importlib.import_module(
            "saas_database"
        )

        for attribute in [
            "SAAS_DATABASE_PATH",
            "DATABASE_PATH",
            "DB_PATH",
        ]:
            value = getattr(
                module,
                attribute,
                None,
            )

            if value:
                candidates.insert(
                    0,
                    Path(value),
                )

    except Exception:
        pass

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def quoted_identifier(
    value: str,
) -> str:
    return (
        '"'
        + value.replace(
            '"',
            '""',
        )
        + '"'
    )


def users_table_information() -> (
    tuple[
        Path,
        str,
        set[str],
    ]
    | None
):
    database_path = user_database_path()

    if not database_path:
        return None

    connection = sqlite3.connect(
        database_path,
        timeout=15,
    )

    try:
        tables = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        ]

        table_name = next(
            (
                name
                for name in tables
                if name.lower() == "users"
            ),
            None,
        )

        if not table_name:
            return None

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info("
                + quoted_identifier(
                    table_name
                )
                + ")"
            ).fetchall()
        }

        return (
            database_path,
            table_name,
            columns,
        )

    finally:
        connection.close()


def find_user_by_email(
    email: str,
) -> dict[str, Any] | None:
    information = users_table_information()

    if not information:
        return None

    database_path, table_name, columns = (
        information
    )

    email_column = next(
        (
            candidate
            for candidate in [
                "email",
                "email_address",
            ]
            if candidate in columns
        ),
        None,
    )

    if not email_column:
        return None

    connection = sqlite3.connect(
        database_path,
        timeout=15,
    )

    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            (
                "SELECT * FROM "
                + quoted_identifier(
                    table_name
                )
                + " WHERE LOWER("
                + quoted_identifier(
                    email_column
                )
                + ") = LOWER(?) LIMIT 1"
            ),
            (email.strip(),),
        ).fetchone()

        if not row:
            return None

        result = dict(row)

        user_id = next(
            (
                result.get(candidate)
                for candidate in [
                    "user_id",
                    "id",
                    "uuid",
                ]
                if result.get(candidate)
                is not None
            ),
            None,
        )

        result["resolved_user_id"] = (
            str(user_id)
            if user_id is not None
            else None
        )

        result["resolved_email"] = (
            result.get(email_column)
        )

        return result

    finally:
        connection.close()


def send_password_reset_email(
    email: str,
) -> dict[str, Any]:
    user = find_user_by_email(
        email
    )

    generic_result = {
        "success": True,
        "message": (
            "Apabila email terdaftar, "
            "instruksi reset password telah dikirim."
        ),
    }

    if not user:
        return generic_result

    user_id = user.get(
        "resolved_user_id"
    )

    resolved_email = user.get(
        "resolved_email"
    )

    token = issue_email_token(
        user_id=user_id,
        email=resolved_email,
        purpose="password_reset",
        ttl_minutes=60,
    )

    reset_url = (
        public_base_url()
        + "/reset-password?token="
        + token
    )

    body_text = (
        "Halo,\n\n"
        "Gunakan tautan berikut untuk "
        "mengatur ulang password DocuRapi:\n\n"
        f"{reset_url}\n\n"
        "Tautan berlaku selama 60 menit.\n"
    )

    body_html = (
        "<h2>Reset Password DocuRapi</h2>"
        "<p>Klik tombol berikut untuk "
        "mengatur ulang password.</p>"
        f"<p><a href='{reset_url}'>"
        "Reset Password</a></p>"
        "<p>Tautan berlaku selama 60 menit.</p>"
    )

    enqueue_and_deliver_email(
        recipient=resolved_email,
        subject="Reset password DocuRapi",
        body_text=body_text,
        body_html=body_html,
        template_key="password_reset",
        user_id=user_id,
    )

    return generic_result


def resolve_password_hasher():
    try:
        module = importlib.import_module(
            "services.auth_service"
        )
    except Exception:
        return None

    for function_name in [
        "hash_password",
        "create_password_hash",
        "password_hash",
        "encode_password",
    ]:
        function = getattr(
            module,
            function_name,
            None,
        )

        if callable(function):
            return function

    return None


def reset_application_password(
    email: str,
    new_password: str,
) -> bool:
    information = users_table_information()

    hasher = resolve_password_hasher()

    if not information or not hasher:
        return False

    database_path, table_name, columns = (
        information
    )

    email_column = next(
        (
            candidate
            for candidate in [
                "email",
                "email_address",
            ]
            if candidate in columns
        ),
        None,
    )

    password_column = next(
        (
            candidate
            for candidate in [
                "password_hash",
                "hashed_password",
                "password",
            ]
            if candidate in columns
        ),
        None,
    )

    if (
        not email_column
        or not password_column
    ):
        return False

    hashed_password = hasher(
        new_password
    )

    connection = sqlite3.connect(
        database_path,
        timeout=15,
    )

    try:
        cursor = connection.execute(
            (
                "UPDATE "
                + quoted_identifier(
                    table_name
                )
                + " SET "
                + quoted_identifier(
                    password_column
                )
                + " = ? WHERE LOWER("
                + quoted_identifier(
                    email_column
                )
                + ") = LOWER(?)"
            ),
            (
                hashed_password,
                email,
            ),
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def confirm_password_reset(
    raw_token: str,
    new_password: str,
) -> dict[str, Any]:
    token_record = validate_email_token(
        raw_token,
        "password_reset",
    )

    if not token_record:
        return {
            "success": False,
            "message": (
                "Token reset password tidak valid "
                "atau sudah kedaluwarsa."
            ),
        }

    updated = reset_application_password(
        token_record["email"],
        new_password,
    )

    if not updated:
        return {
            "success": False,
            "unsupported": True,
            "message": (
                "Struktur autentikasi saat ini "
                "belum mendukung pembaruan password "
                "otomatis dari Notification Center."
            ),
        }

    consume_email_token(
        token_record
    )

    if token_record.get("user_id"):
        create_notification(
            user_id=token_record["user_id"],
            title="Password berhasil diubah",
            message=(
                "Password akun Anda baru saja "
                "berhasil diperbarui."
            ),
            notification_type="security",
            action_url="/security-center",
        )

    return {
        "success": True,
        "message": (
            "Password berhasil diperbarui."
        ),
    }


def update_application_email_status(
    email: str,
) -> bool:
    information = users_table_information()

    if not information:
        return False

    database_path, table_name, columns = (
        information
    )

    email_column = next(
        (
            candidate
            for candidate in [
                "email",
                "email_address",
            ]
            if candidate in columns
        ),
        None,
    )

    if not email_column:
        return False

    connection = sqlite3.connect(
        database_path,
        timeout=15,
    )

    try:
        if "email_verified" in columns:
            cursor = connection.execute(
                (
                    "UPDATE "
                    + quoted_identifier(
                        table_name
                    )
                    + " SET "
                    + quoted_identifier(
                        "email_verified"
                    )
                    + " = 1 WHERE LOWER("
                    + quoted_identifier(
                        email_column
                    )
                    + ") = LOWER(?)"
                ),
                (email,),
            )

        elif "is_email_verified" in columns:
            cursor = connection.execute(
                (
                    "UPDATE "
                    + quoted_identifier(
                        table_name
                    )
                    + " SET "
                    + quoted_identifier(
                        "is_email_verified"
                    )
                    + " = 1 WHERE LOWER("
                    + quoted_identifier(
                        email_column
                    )
                    + ") = LOWER(?)"
                ),
                (email,),
            )

        elif "email_verified_at" in columns:
            cursor = connection.execute(
                (
                    "UPDATE "
                    + quoted_identifier(
                        table_name
                    )
                    + " SET "
                    + quoted_identifier(
                        "email_verified_at"
                    )
                    + " = ? WHERE LOWER("
                    + quoted_identifier(
                        email_column
                    )
                    + ") = LOWER(?)"
                ),
                (
                    utc_now().isoformat(),
                    email,
                ),
            )

        else:
            return False

        connection.commit()

        return cursor.rowcount > 0

    finally:
        connection.close()


def email_status(
    email: str,
) -> dict[str, Any]:
    return {
        "email": email,
        "verified": email_is_verified(
            email
        ),
    }


def outbox_items(
    limit: int = 100,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return list_email_outbox(
        limit=limit,
        status=status,
    )


def notification_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "delivery_mode": delivery_mode(),
        "local_outbox": str(
            OUTBOX_FILE_DIRECTORY
        ),
        "smtp_configured": bool(
            os.getenv(
                "DOCURAPI_SMTP_HOST"
            )
        ),
    }
