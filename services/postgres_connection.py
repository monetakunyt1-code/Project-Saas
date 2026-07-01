from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row


DATABASE_ENV_NAMES = (
    "DOCURAPI_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
)

DOCURAPI_SCHEMAS = (
    "core",
    "billing",
    "saas",
    "security",
    "background",
    "notifications",
    "observability",
    "docurapi_meta",
)


def normalize_database_url(
    value: str,
) -> str:
    normalized = value.strip()

    if normalized.startswith("postgres://"):
        normalized = (
            "postgresql://"
            + normalized[len("postgres://"):]
        )

    return normalized


def resolve_database_url(
    *,
    required: bool = True,
) -> str:
    for name in DATABASE_ENV_NAMES:
        value = os.environ.get(name, "").strip()

        if value:
            normalized = normalize_database_url(
                value
            )

            if not is_postgres_url(normalized):
                raise RuntimeError(
                    f"{name} bukan URL PostgreSQL."
                )

            return normalized

    if required:
        raise RuntimeError(
            "URL PostgreSQL belum tersedia. "
            "Isi DOCURAPI_DATABASE_URL, "
            "DATABASE_URL, atau POSTGRES_URL."
        )

    return ""


def is_postgres_url(
    value: str,
) -> bool:
    lowered = value.lower()

    return lowered.startswith(
        (
            "postgresql://",
            "postgresql+psycopg://",
        )
    )


@contextmanager
def postgres_connection(
    database_url: str | None = None,
    *,
    autocommit: bool = False,
) -> Iterator[Connection[Any]]:
    url = normalize_database_url(
        database_url
        or resolve_database_url()
    )

    connection = psycopg.connect(
        url,
        autocommit=autocommit,
        row_factory=dict_row,
    )

    try:
        yield connection
    finally:
        connection.close()


def ping_postgres(
    database_url: str | None = None,
) -> dict[str, Any]:
    with postgres_connection(
        database_url,
    ) as connection:
        row = connection.execute(
            """
            SELECT
                current_database() AS database_name,
                current_user AS database_user,
                current_schema() AS current_schema
            """
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "PostgreSQL tidak memberikan hasil."
            )

        return dict(row)


def ensure_docurapi_schemas(
    database_url: str | None = None,
) -> tuple[str, ...]:
    with postgres_connection(
        database_url,
    ) as connection:
        for schema_name in DOCURAPI_SCHEMAS:
            connection.execute(
                sql.SQL(
                    "CREATE SCHEMA IF NOT EXISTS {}"
                ).format(
                    sql.Identifier(schema_name)
                )
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
                docurapi_meta.migration_ledger
            (
                id BIGSERIAL PRIMARY KEY,
                source_database TEXT NOT NULL,
                migration_name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (
                    source_database,
                    migration_name
                )
            )
            """
        )

        connection.commit()

    return DOCURAPI_SCHEMAS


def list_docurapi_schemas(
    database_url: str | None = None,
) -> tuple[str, ...]:
    with postgres_connection(
        database_url,
    ) as connection:
        rows = connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = ANY(%s)
            ORDER BY schema_name
            """,
            (list(DOCURAPI_SCHEMAS),),
        ).fetchall()

    return tuple(
        str(row["schema_name"])
        for row in rows
    )
