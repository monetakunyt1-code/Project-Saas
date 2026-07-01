from __future__ import annotations

import base64
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Sequence

from psycopg import sql

from services.postgres_connection import (
    postgres_connection,
)


@dataclass(frozen=True)
class SourceDatabase:
    relative_path: str
    schema_name: str
    logical_name: str


@dataclass(frozen=True)
class ColumnDefinition:
    position: int
    name: str
    declared_type: str
    postgres_type: str
    nullable: bool
    observed_types: tuple[str, ...]


SOURCE_DATABASES: tuple[SourceDatabase, ...] = (
    SourceDatabase(
        "storage/docurapi.db",
        "core",
        "docurapi",
    ),
    SourceDatabase(
        "storage/billing/billing.db",
        "billing",
        "billing",
    ),
    SourceDatabase(
        "storage/saas/saas.db",
        "saas",
        "saas",
    ),
    SourceDatabase(
        "storage/saas/security.db",
        "security",
        "security",
    ),
    SourceDatabase(
        "storage/background/background_jobs.db",
        "background",
        "background",
    ),
    SourceDatabase(
        "storage/notifications/notifications.db",
        "notifications",
        "notifications",
    ),
    SourceDatabase(
        "storage/system/observability.db",
        "observability",
        "observability",
    ),
)


def quote_sqlite_identifier(
    value: str,
) -> str:
    return '"' + value.replace('"', '""') + '"'


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(
            lambda: source.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def list_sqlite_tables(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def sqlite_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[sqlite3.Row]:
    quoted = quote_sqlite_identifier(
        table_name
    )

    return list(
        connection.execute(
            f"PRAGMA table_info({quoted})"
        ).fetchall()
    )


def observed_sqlite_types(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> tuple[str, ...]:
    table = quote_sqlite_identifier(
        table_name
    )
    column = quote_sqlite_identifier(
        column_name
    )

    rows = connection.execute(
        f"""
        SELECT typeof({column}) AS storage_type
        FROM {table}
        WHERE {column} IS NOT NULL
        GROUP BY typeof({column})
        ORDER BY typeof({column})
        """
    ).fetchall()

    return tuple(
        str(row[0]).lower()
        for row in rows
    )


def infer_postgres_type(
    declared_type: str,
    observed_types: Sequence[str],
) -> str:
    declared = declared_type.strip().upper()
    observed = {
        value.lower()
        for value in observed_types
        if value
    }

    if observed:
        if observed <= {"integer"}:
            return "BIGINT"

        if observed <= {
            "integer",
            "real",
        }:
            return "DOUBLE PRECISION"

        if observed <= {"blob"}:
            return "BYTEA"

        # SQLite memungkinkan tipe campuran dalam satu kolom.
        # TEXT adalah target paling aman untuk kombinasi tersebut.
        return "TEXT"

    if "INT" in declared:
        return "BIGINT"

    if any(
        token in declared
        for token in (
            "REAL",
            "FLOA",
            "DOUB",
        )
    ):
        return "DOUBLE PRECISION"

    if any(
        token in declared
        for token in (
            "NUMERIC",
            "DECIMAL",
        )
    ):
        return "NUMERIC"

    if "BLOB" in declared:
        return "BYTEA"

    return "TEXT"


def build_column_definitions(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[ColumnDefinition]:
    definitions: list[
        ColumnDefinition
    ] = []

    for row in sqlite_table_columns(
        connection,
        table_name,
    ):
        position = int(row["cid"])
        name = str(row["name"])
        declared_type = str(
            row["type"] or ""
        )

        observed = observed_sqlite_types(
            connection,
            table_name,
            name,
        )

        definitions.append(
            ColumnDefinition(
                position=position,
                name=name,
                declared_type=declared_type,
                postgres_type=infer_postgres_type(
                    declared_type,
                    observed,
                ),
                nullable=not bool(
                    row["notnull"]
                ),
                observed_types=observed,
            )
        )

    return definitions


def convert_value(
    value: Any,
    postgres_type: str,
) -> Any:
    if value is None:
        return None

    if postgres_type == "TEXT":
        if isinstance(
            value,
            (
                bytes,
                bytearray,
                memoryview,
            ),
        ):
            encoded = base64.b64encode(
                bytes(value)
            ).decode("ascii")

            return "base64:" + encoded

        return str(value)

    if postgres_type == "BYTEA":
        if isinstance(
            value,
            memoryview,
        ):
            return value.tobytes()

        if isinstance(
            value,
            (
                bytes,
                bytearray,
            ),
        ):
            return bytes(value)

        return str(value).encode(
            "utf-8"
        )

    if postgres_type == "BIGINT":
        return int(value)

    if postgres_type == "DOUBLE PRECISION":
        return float(value)

    if postgres_type == "NUMERIC":
        return Decimal(str(value))

    return value


def ensure_metadata_tables(
    connection: Any,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            docurapi_meta.sqlite_migration_tables
        (
            source_database TEXT NOT NULL,
            source_checksum TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            source_rows BIGINT NOT NULL,
            target_rows BIGINT NOT NULL,
            migrated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (
                source_database,
                schema_name,
                table_name
            )
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS
            docurapi_meta.sqlite_column_map
        (
            source_database TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            column_position INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            sqlite_declared_type TEXT NOT NULL,
            sqlite_observed_types TEXT NOT NULL,
            postgres_type TEXT NOT NULL,
            migrated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (
                source_database,
                schema_name,
                table_name,
                column_position
            )
        )
        """
    )


def iter_sqlite_rows(
    connection: sqlite3.Connection,
    table_name: str,
    column_names: Sequence[str],
    *,
    batch_size: int = 500,
) -> Iterator[list[sqlite3.Row]]:
    columns = ", ".join(
        quote_sqlite_identifier(name)
        for name in column_names
    )

    table = quote_sqlite_identifier(
        table_name
    )

    cursor = connection.execute(
        f"SELECT {columns} FROM {table}"
    )

    while True:
        rows = cursor.fetchmany(
            batch_size
        )

        if not rows:
            break

        yield rows


def migrate_table(
    *,
    sqlite_connection: sqlite3.Connection,
    postgres_connection_object: Any,
    source: SourceDatabase,
    source_checksum: str,
    table_name: str,
) -> dict[str, Any]:
    columns = build_column_definitions(
        sqlite_connection,
        table_name,
    )

    if not columns:
        return {
            "table": table_name,
            "source_rows": 0,
            "target_rows": 0,
            "columns": 0,
            "skipped": True,
        }

    postgres_connection_object.execute(
        sql.SQL(
            "DROP TABLE IF EXISTS {}.{} CASCADE"
        ).format(
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                table_name
            ),
        )
    )

    column_sql = []

    for column in columns:
        column_sql.append(
            sql.SQL("{} {}").format(
                sql.Identifier(
                    column.name
                ),
                sql.SQL(
                    column.postgres_type
                ),
            )
        )

    postgres_connection_object.execute(
        sql.SQL(
            "CREATE TABLE {}.{} ({})"
        ).format(
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                table_name
            ),
            sql.SQL(", ").join(
                column_sql
            ),
        )
    )

    source_count = int(
        sqlite_connection.execute(
            "SELECT COUNT(*) FROM "
            + quote_sqlite_identifier(
                table_name
            )
        ).fetchone()[0]
    )

    column_names = [
        column.name
        for column in columns
    ]

    insert_statement = sql.SQL(
        "INSERT INTO {}.{} ({}) VALUES ({})"
    ).format(
        sql.Identifier(
            source.schema_name
        ),
        sql.Identifier(
            table_name
        ),
        sql.SQL(", ").join(
            sql.Identifier(name)
            for name in column_names
        ),
        sql.SQL(", ").join(
            sql.Placeholder()
            for _ in column_names
        ),
    )

    for batch in iter_sqlite_rows(
        sqlite_connection,
        table_name,
        column_names,
    ):
        converted_batch = []

        for row in batch:
            converted_batch.append(
                tuple(
                    convert_value(
                        row[column.name],
                        column.postgres_type,
                    )
                    for column in columns
                )
            )

        with postgres_connection_object.cursor() as cursor:
            cursor.executemany(
                insert_statement,
                converted_batch,
                returning=False,
            )

    target_count_row = (
        postgres_connection_object.execute(
            sql.SQL(
                "SELECT COUNT(*) AS count "
                "FROM {}.{}"
            ).format(
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
            )
        ).fetchone()
    )

    target_count = int(
        target_count_row["count"]
    )

    if source_count != target_count:
        raise RuntimeError(
            f"Jumlah baris tidak sama untuk "
            f"{source.relative_path}:{table_name}. "
            f"SQLite={source_count}, "
            f"PostgreSQL={target_count}"
        )

    migrated_at = datetime.now(
        timezone.utc
    )

    postgres_connection_object.execute(
        """
        DELETE FROM
            docurapi_meta.sqlite_migration_tables
        WHERE source_database = %s
          AND schema_name = %s
          AND table_name = %s
        """,
        (
            source.relative_path,
            source.schema_name,
            table_name,
        ),
    )

    postgres_connection_object.execute(
        """
        INSERT INTO
            docurapi_meta.sqlite_migration_tables
        (
            source_database,
            source_checksum,
            schema_name,
            table_name,
            source_rows,
            target_rows,
            migrated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            source.relative_path,
            source_checksum,
            source.schema_name,
            table_name,
            source_count,
            target_count,
            migrated_at,
        ),
    )

    postgres_connection_object.execute(
        """
        DELETE FROM
            docurapi_meta.sqlite_column_map
        WHERE source_database = %s
          AND schema_name = %s
          AND table_name = %s
        """,
        (
            source.relative_path,
            source.schema_name,
            table_name,
        ),
    )

    for column in columns:
        postgres_connection_object.execute(
            """
            INSERT INTO
                docurapi_meta.sqlite_column_map
            (
                source_database,
                schema_name,
                table_name,
                column_position,
                column_name,
                sqlite_declared_type,
                sqlite_observed_types,
                postgres_type,
                migrated_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """,
            (
                source.relative_path,
                source.schema_name,
                table_name,
                column.position,
                column.name,
                column.declared_type,
                ",".join(
                    column.observed_types
                ),
                column.postgres_type,
                migrated_at,
            ),
        )

    return {
        "table": table_name,
        "source_rows": source_count,
        "target_rows": target_count,
        "columns": len(columns),
        "skipped": False,
    }


def migrate_database(
    root: Path,
    source: SourceDatabase,
) -> dict[str, Any]:
    source_path = (
        root / source.relative_path
    ).resolve()

    if not source_path.exists():
        raise FileNotFoundError(
            source_path
        )

    if "system_backups" in source_path.parts:
        raise RuntimeError(
            "Database system_backups tidak boleh dimigrasikan."
        )

    checksum = sha256_file(
        source_path
    )

    sqlite_connection = sqlite3.connect(
        f"file:{source_path}?mode=ro",
        uri=True,
    )

    sqlite_connection.row_factory = (
        sqlite3.Row
    )

    tables = list_sqlite_tables(
        sqlite_connection
    )

    results = []

    try:
        with postgres_connection() as pg:
            ensure_metadata_tables(pg)

            pg.execute(
                sql.SQL(
                    "CREATE SCHEMA IF NOT EXISTS {}"
                ).format(
                    sql.Identifier(
                        source.schema_name
                    )
                )
            )

            for table_name in tables:
                result = migrate_table(
                    sqlite_connection=sqlite_connection,
                    postgres_connection_object=pg,
                    source=source,
                    source_checksum=checksum,
                    table_name=table_name,
                )

                results.append(
                    result
                )

            migration_name = (
                "phase2a_sqlite_snapshot"
            )

            pg.execute(
                """
                INSERT INTO
                    docurapi_meta.migration_ledger
                (
                    source_database,
                    migration_name,
                    checksum
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (
                    source_database,
                    migration_name
                )
                DO UPDATE SET
                    checksum = EXCLUDED.checksum,
                    applied_at = CURRENT_TIMESTAMP
                """,
                (
                    source.relative_path,
                    migration_name,
                    checksum,
                ),
            )

            pg.commit()

    finally:
        sqlite_connection.close()

    return {
        "source": source.relative_path,
        "schema": source.schema_name,
        "checksum": checksum,
        "tables": results,
    }


def migrate_all(
    root: Path,
) -> list[dict[str, Any]]:
    return [
        migrate_database(
            root,
            source,
        )
        for source in SOURCE_DATABASES
    ]
