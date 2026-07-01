from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import STORAGE_DIR


SAAS_DIR = STORAGE_DIR / "saas"
DB_PATH = SAAS_DIR / "saas.db"
SAAS_DIR.mkdir(parents=True, exist_ok=True)

PLANS = {
    "free": {
        "name": "Free",
        "monthly_quota": 5,
        "price_idr": 0,
        "features": [
            "5 operasi per bulan",
            "Format dasar",
            "Audit akademik",
        ],
    },
    "student": {
        "name": "Student",
        "monthly_quota": 30,
        "price_idr": 29000,
        "features": [
            "30 operasi per bulan",
            "Journal Studio",
            "Template khusus",
        ],
    },
    "pro": {
        "name": "Pro",
        "monthly_quota": 200,
        "price_idr": 79000,
        "features": [
            "200 operasi per bulan",
            "Batch processing",
            "Laporan visual",
        ],
    },
    "institution": {
        "name": "Institution",
        "monthly_quota": 1000,
        "price_idr": 299000,
        "features": [
            "1.000 operasi per bulan",
            "Penggunaan tim",
            "Prioritas dukungan",
        ],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS plans (
                plan_code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                monthly_quota INTEGER NOT NULL,
                price_idr INTEGER NOT NULL,
                features_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id TEXT PRIMARY KEY,
                plan_code TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (plan_code)
                    REFERENCES plans(plan_code)
            );

            CREATE TABLE IF NOT EXISTS usage_monthly (
                user_id TEXT NOT NULL,
                period TEXT NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, period),
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                plan_code TEXT NOT NULL,
                amount_idr INTEGER NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
                    ON DELETE CASCADE
            );
            """
        )

        for code, plan in PLANS.items():
            connection.execute(
                """
                INSERT INTO plans (
                    plan_code,
                    name,
                    monthly_quota,
                    price_idr,
                    features_json
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plan_code)
                DO UPDATE SET
                    name = excluded.name,
                    monthly_quota = excluded.monthly_quota,
                    price_idr = excluded.price_idr,
                    features_json = excluded.features_json
                """,
                (
                    code,
                    plan["name"],
                    plan["monthly_quota"],
                    plan["price_idr"],
                    json.dumps(
                        plan["features"],
                        ensure_ascii=False,
                    ),
                ),
            )

        connection.commit()


def one(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            query,
            parameters,
        ).fetchone()

    return dict(row) if row else None


def all_rows(
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def get_user_by_email(
    email: str,
) -> dict[str, Any] | None:
    return one(
        "SELECT * FROM users WHERE email = ?",
        (email.strip().lower(),),
    )


def get_user(
    user_id: str,
) -> dict[str, Any] | None:
    return one(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    )


def create_user(
    user_id: str,
    email: str,
    display_name: str,
    password_hash: str,
    password_salt: str,
    role: str = "user",
) -> dict[str, Any]:
    timestamp = now_iso()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO users (
                user_id,
                email,
                display_name,
                password_hash,
                password_salt,
                role,
                is_active,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                user_id,
                email.lower(),
                display_name,
                password_hash,
                password_salt,
                role,
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                plan_code,
                status,
                updated_at
            )
            VALUES (?, 'free', 'active', ?)
            """,
            (
                user_id,
                timestamp,
            ),
        )

        connection.commit()

    result = get_user(user_id)

    if not result:
        raise RuntimeError("Akun gagal dibuat.")

    return result


def upsert_admin(
    user_id: str,
    email: str,
    display_name: str,
    password_hash: str,
    password_salt: str,
) -> dict[str, Any]:
    timestamp = now_iso()
    existing = get_user_by_email(email)

    with connect() as connection:
        if existing:
            user_id = existing["user_id"]

            connection.execute(
                """
                UPDATE users
                SET
                    display_name = ?,
                    password_hash = ?,
                    password_salt = ?,
                    role = 'admin',
                    is_active = 1,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    display_name,
                    password_hash,
                    password_salt,
                    timestamp,
                    user_id,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    email,
                    display_name,
                    password_hash,
                    password_salt,
                    role,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'admin', 1, ?, ?)
                """,
                (
                    user_id,
                    email.lower(),
                    display_name,
                    password_hash,
                    password_salt,
                    timestamp,
                    timestamp,
                ),
            )

        connection.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                plan_code,
                status,
                updated_at
            )
            VALUES (?, 'institution', 'active', ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                plan_code = 'institution',
                status = 'active',
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                timestamp,
            ),
        )

        connection.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (user_id,),
        )

        connection.commit()

    result = get_user(user_id)

    if not result:
        raise RuntimeError("Administrator gagal dibuat.")

    return result


def create_session(
    token_hash: str,
    user_id: str,
    expires_at: str,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (
                token_hash,
                user_id,
                expires_at,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                token_hash,
                user_id,
                expires_at,
                now_iso(),
            ),
        )

        connection.commit()


def get_session(
    token_hash: str,
) -> dict[str, Any] | None:
    return one(
        """
        SELECT
            s.token_hash,
            s.expires_at,
            u.*
        FROM sessions s
        JOIN users u
            ON u.user_id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    )


def delete_session(
    token_hash: str,
) -> None:
    with connect() as connection:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (token_hash,),
        )

        connection.commit()


def list_plans() -> list[dict[str, Any]]:
    plans = all_rows(
        "SELECT * FROM plans ORDER BY price_idr"
    )

    for plan in plans:
        plan["features"] = json.loads(
            plan.pop("features_json")
        )

    return plans


def get_plan(
    plan_code: str,
) -> dict[str, Any] | None:
    plan = one(
        "SELECT * FROM plans WHERE plan_code = ?",
        (plan_code,),
    )

    if plan:
        plan["features"] = json.loads(
            plan.pop("features_json")
        )

    return plan


def usage_snapshot(
    user_id: str,
) -> dict[str, Any]:
    subscription = one(
        """
        SELECT
            s.plan_code,
            s.status,
            p.name AS plan_name,
            p.monthly_quota,
            p.price_idr
        FROM subscriptions s
        JOIN plans p
            ON p.plan_code = s.plan_code
        WHERE s.user_id = ?
        """,
        (user_id,),
    )

    if not subscription:
        raise RuntimeError(
            "Langganan pengguna tidak ditemukan."
        )

    usage = one(
        """
        SELECT used_count
        FROM usage_monthly
        WHERE user_id = ?
          AND period = ?
        """,
        (
            user_id,
            period_now(),
        ),
    )

    used = (
        int(usage["used_count"])
        if usage
        else 0
    )

    quota = int(
        subscription["monthly_quota"]
    )

    return {
        **subscription,
        "period": period_now(),
        "used_count": used,
        "remaining": max(
            quota - used,
            0,
        ),
    }


def consume_usage(
    user_id: str,
    amount: int = 1,
) -> dict[str, Any]:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO usage_monthly (
                user_id,
                period,
                used_count,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, period)
            DO UPDATE SET
                used_count =
                    used_count + excluded.used_count,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                period_now(),
                max(1, int(amount)),
                now_iso(),
            ),
        )

        connection.commit()

    return usage_snapshot(user_id)


def set_plan(
    user_id: str,
    plan_code: str,
    payment_id: str | None = None,
) -> dict[str, Any]:
    plan = get_plan(plan_code)

    if not plan:
        raise ValueError("Paket tidak ditemukan.")

    timestamp = now_iso()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                plan_code,
                status,
                updated_at
            )
            VALUES (?, ?, 'active', ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                plan_code = excluded.plan_code,
                status = 'active',
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                plan_code,
                timestamp,
            ),
        )

        if payment_id:
            connection.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    user_id,
                    plan_code,
                    amount_idr,
                    provider,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'simulation', 'paid', ?)
                """,
                (
                    payment_id,
                    user_id,
                    plan_code,
                    int(plan["price_idr"]),
                    timestamp,
                ),
            )

        connection.commit()

    return usage_snapshot(user_id)


def set_active(
    user_id: str,
    active: bool,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET
                is_active = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                1 if active else 0,
                now_iso(),
                user_id,
            ),
        )

        if not active:
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ?",
                (user_id,),
            )

        connection.commit()


def admin_users() -> list[dict[str, Any]]:
    return all_rows(
        """
        SELECT
            u.user_id,
            u.email,
            u.display_name,
            u.role,
            u.is_active,
            u.created_at,
            s.plan_code,
            p.name AS plan_name,
            p.monthly_quota,
            COALESCE(m.used_count, 0) AS used_count
        FROM users u
        LEFT JOIN subscriptions s
            ON s.user_id = u.user_id
        LEFT JOIN plans p
            ON p.plan_code = s.plan_code
        LEFT JOIN usage_monthly m
            ON m.user_id = u.user_id
           AND m.period = ?
        ORDER BY u.created_at DESC
        """,
        (period_now(),),
    )


def admin_payments() -> list[dict[str, Any]]:
    return all_rows(
        """
        SELECT
            p.*,
            u.email,
            u.display_name,
            pl.name AS plan_name
        FROM payments p
        JOIN users u
            ON u.user_id = p.user_id
        JOIN plans pl
            ON pl.plan_code = p.plan_code
        ORDER BY p.created_at DESC
        """
    )


initialize()