from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from psycopg import sql

from services.postgres_connection import (
    postgres_connection,
)
from services.sqlite_postgres_migration import (
    SOURCE_DATABASES,
    SourceDatabase,
    quote_sqlite_identifier,
)


@dataclass(frozen=True)
class DefaultExpression:
    kind: str
    value: Any


def safe_object_name(
    *parts: str,
    limit: int = 63,
) -> str:
    raw = "_".join(
        part
        for part in parts
        if part
    )

    normalized = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        raw,
    ).strip("_").lower()

    if not normalized:
        normalized = "docurapi_object"

    if len(normalized.encode("utf-8")) <= limit:
        return normalized

    digest = hashlib.sha1(
        normalized.encode("utf-8")
    ).hexdigest()[:10]

    prefix = normalized[
        : max(1, limit - len(digest) - 1)
    ]

    return f"{prefix}_{digest}"


def strip_outer_parentheses(
    value: str,
) -> str:
    result = value.strip()

    while (
        result.startswith("(")
        and result.endswith(")")
    ):
        depth = 0
        valid = True

        for index, character in enumerate(result):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1

                if depth == 0 and index != len(result) - 1:
                    valid = False
                    break

                if depth < 0:
                    valid = False
                    break

        if not valid or depth != 0:
            break

        result = result[1:-1].strip()

    return result


def translate_sqlite_default(
    value: str | None,
) -> DefaultExpression | None:
    if value is None:
        return None

    normalized = strip_outer_parentheses(
        str(value)
    )

    if not normalized:
        return None

    upper = normalized.upper()

    raw_keywords = {
        "CURRENT_TIMESTAMP",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "TRUE",
        "FALSE",
    }

    if upper in raw_keywords:
        return DefaultExpression(
            "raw",
            upper,
        )

    if upper == "NULL":
        return None

    compact = re.sub(
        r"\s+",
        "",
        normalized.lower(),
    )

    if compact in {
        "datetime('now')",
        'datetime("now")',
    }:
        return DefaultExpression(
            "raw",
            "CURRENT_TIMESTAMP",
        )

    if compact in {
        "date('now')",
        'date("now")',
    }:
        return DefaultExpression(
            "raw",
            "CURRENT_DATE",
        )

    if compact in {
        "time('now')",
        'time("now")',
    }:
        return DefaultExpression(
            "raw",
            "CURRENT_TIME",
        )

    if compact in {
        "strftime('%s','now')",
        'strftime("%s","now")',
    }:
        return DefaultExpression(
            "raw",
            "EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)::BIGINT",
        )

    if re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)",
        normalized,
    ):
        return DefaultExpression(
            "raw",
            normalized,
        )

    if (
        len(normalized) >= 2
        and normalized[0] == "'"
        and normalized[-1] == "'"
    ):
        literal = normalized[1:-1].replace(
            "''",
            "'",
        )

        return DefaultExpression(
            "literal",
            literal,
        )

    return DefaultExpression(
        "unsupported",
        normalized,
    )


def sqlite_tables(
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
        str(row["name"])
        for row in rows
    ]


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[sqlite3.Row]:
    table = quote_sqlite_identifier(
        table_name
    )

    return list(
        connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    )


def primary_key_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = [
        row
        for row in table_columns(
            connection,
            table_name,
        )
        if int(row["pk"] or 0) > 0
    ]

    rows.sort(
        key=lambda row: int(row["pk"])
    )

    return [
        str(row["name"])
        for row in rows
    ]


def constraint_exists(
    pg: Any,
    schema_name: str,
    table_name: str,
    constraint_name: str,
) -> bool:
    row = pg.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_constraint AS constraint_record
            JOIN pg_class AS table_record
              ON table_record.oid =
                 constraint_record.conrelid
            JOIN pg_namespace AS namespace_record
              ON namespace_record.oid =
                 table_record.relnamespace
            WHERE namespace_record.nspname = %s
              AND table_record.relname = %s
              AND constraint_record.conname = %s
        ) AS exists
        """,
        (
            schema_name,
            table_name,
            constraint_name,
        ),
    ).fetchone()

    return bool(row["exists"])


def index_exists(
    pg: Any,
    schema_name: str,
    index_name: str,
) -> bool:
    row = pg.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = %s
              AND indexname = %s
        ) AS exists
        """,
        (
            schema_name,
            index_name,
        ),
    ).fetchone()

    return bool(row["exists"])


def apply_column_rules(
    sqlite_connection: sqlite3.Connection,
    pg: Any,
    source: SourceDatabase,
    table_name: str,
) -> dict[str, int]:
    result = {
        "not_null": 0,
        "defaults": 0,
        "unsupported_defaults": 0,
    }

    for column in table_columns(
        sqlite_connection,
        table_name,
    ):
        column_name = str(
            column["name"]
        )

        is_primary_key = int(
            column["pk"] or 0
        ) > 0

        requires_not_null = bool(
            column["notnull"]
        ) or is_primary_key

        if requires_not_null:
            null_count = pg.execute(
                sql.SQL(
                    "SELECT COUNT(*) AS count "
                    "FROM {}.{} "
                    "WHERE {} IS NULL"
                ).format(
                    sql.Identifier(
                        source.schema_name
                    ),
                    sql.Identifier(
                        table_name
                    ),
                    sql.Identifier(
                        column_name
                    ),
                )
            ).fetchone()

            if int(null_count["count"]) != 0:
                raise RuntimeError(
                    f"Kolom wajib masih memiliki NULL: "
                    f"{source.schema_name}."
                    f"{table_name}.{column_name}"
                )

            pg.execute(
                sql.SQL(
                    "ALTER TABLE {}.{} "
                    "ALTER COLUMN {} SET NOT NULL"
                ).format(
                    sql.Identifier(
                        source.schema_name
                    ),
                    sql.Identifier(
                        table_name
                    ),
                    sql.Identifier(
                        column_name
                    ),
                )
            )

            result["not_null"] += 1

        default = translate_sqlite_default(
            column["dflt_value"]
        )

        if default is None:
            continue

        if default.kind == "unsupported":
            result[
                "unsupported_defaults"
            ] += 1
            continue

        if default.kind == "literal":
            expression = sql.Literal(
                default.value
            )
        else:
            expression = sql.SQL(
                str(default.value)
            )

        pg.execute(
            sql.SQL(
                "ALTER TABLE {}.{} "
                "ALTER COLUMN {} SET DEFAULT {}"
            ).format(
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
                sql.Identifier(
                    column_name
                ),
                expression,
            )
        )

        result["defaults"] += 1

    return result


def apply_primary_key(
    sqlite_connection: sqlite3.Connection,
    pg: Any,
    source: SourceDatabase,
    table_name: str,
) -> dict[str, int]:
    columns = primary_key_columns(
        sqlite_connection,
        table_name,
    )

    result = {
        "primary_keys": 0,
        "sequences": 0,
    }

    if not columns:
        return result

    constraint_name = safe_object_name(
        "pk",
        table_name,
    )

    if not constraint_exists(
        pg,
        source.schema_name,
        table_name,
        constraint_name,
    ):
        pg.execute(
            sql.SQL(
                "ALTER TABLE {}.{} "
                "ADD CONSTRAINT {} PRIMARY KEY ({})"
            ).format(
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
                sql.Identifier(
                    constraint_name
                ),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in columns
                ),
            )
        )

    result["primary_keys"] = 1

    if len(columns) != 1:
        return result

    column_name = columns[0]

    source_column = next(
        row
        for row in table_columns(
            sqlite_connection,
            table_name,
        )
        if str(row["name"]) == column_name
    )

    declared_type = str(
        source_column["type"] or ""
    ).upper()

    if "INT" not in declared_type:
        return result

    sequence_name = safe_object_name(
        table_name,
        column_name,
        "seq",
    )

    pg.execute(
        sql.SQL(
            "CREATE SEQUENCE IF NOT EXISTS {}.{}"
        ).format(
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                sequence_name
            ),
        )
    )

    qualified_sequence = (
        f"{source.schema_name}."
        f"{sequence_name}"
    )

    pg.execute(
        sql.SQL(
            "ALTER SEQUENCE {}.{} "
            "OWNED BY {}.{}.{}"
        ).format(
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                sequence_name
            ),
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                table_name
            ),
            sql.Identifier(
                column_name
            ),
        )
    )

    pg.execute(
        sql.SQL(
            "ALTER TABLE {}.{} "
            "ALTER COLUMN {} "
            "SET DEFAULT nextval({}::regclass)"
        ).format(
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                table_name
            ),
            sql.Identifier(
                column_name
            ),
            sql.Literal(
                qualified_sequence
            ),
        )
    )

    maximum = pg.execute(
        sql.SQL(
            "SELECT COALESCE(MAX({}), 0) "
            "AS maximum_value "
            "FROM {}.{}"
        ).format(
            sql.Identifier(
                column_name
            ),
            sql.Identifier(
                source.schema_name
            ),
            sql.Identifier(
                table_name
            ),
        )
    ).fetchone()

    maximum_value = int(
        maximum["maximum_value"]
    )

    if maximum_value > 0:
        pg.execute(
            sql.SQL(
                "SELECT setval("
                "{}::regclass, %s, true"
                ")"
            ).format(
                sql.Literal(
                    qualified_sequence
                )
            ),
            (
                maximum_value,
            ),
        )
    else:
        pg.execute(
            sql.SQL(
                "SELECT setval("
                "{}::regclass, 1, false"
                ")"
            ).format(
                sql.Literal(
                    qualified_sequence
                )
            )
        )

    result["sequences"] = 1

    return result


def apply_indexes(
    sqlite_connection: sqlite3.Connection,
    pg: Any,
    source: SourceDatabase,
    table_name: str,
) -> dict[str, int]:
    table = quote_sqlite_identifier(
        table_name
    )

    rows = sqlite_connection.execute(
        f"PRAGMA index_list({table})"
    ).fetchall()

    result = {
        "indexes": 0,
        "unique_indexes": 0,
        "unsupported_indexes": 0,
    }

    for index in rows:
        origin = str(
            index["origin"] or ""
        ).lower()

        if origin == "pk":
            continue

        source_index_name = str(
            index["name"]
        )

        partial = bool(
            index["partial"]
        )

        if partial:
            result[
                "unsupported_indexes"
            ] += 1
            continue

        quoted_index = (
            quote_sqlite_identifier(
                source_index_name
            )
        )

        index_columns = (
            sqlite_connection.execute(
                f"PRAGMA index_info({quoted_index})"
            ).fetchall()
        )

        columns = [
            str(row["name"])
            for row in index_columns
            if row["name"] is not None
        ]

        if (
            not columns
            or len(columns)
            != len(index_columns)
        ):
            result[
                "unsupported_indexes"
            ] += 1
            continue

        unique = bool(
            index["unique"]
        )

        if source_index_name.startswith(
            "sqlite_autoindex"
        ):
            postgres_index_name = (
                safe_object_name(
                    "uq" if unique else "ix",
                    table_name,
                    *columns,
                )
            )
        else:
            postgres_index_name = (
                safe_object_name(
                    source_index_name
                )
            )

        if index_exists(
            pg,
            source.schema_name,
            postgres_index_name,
        ):
            continue

        unique_sql = (
            sql.SQL("UNIQUE ")
            if unique
            else sql.SQL("")
        )

        pg.execute(
            sql.SQL(
                "CREATE {}INDEX {} "
                "ON {}.{} ({})"
            ).format(
                unique_sql,
                sql.Identifier(
                    postgres_index_name
                ),
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in columns
                ),
            )
        )

        result["indexes"] += 1

        if unique:
            result[
                "unique_indexes"
            ] += 1

    return result


def foreign_key_groups(
    sqlite_connection: sqlite3.Connection,
    table_name: str,
) -> Iterable[list[sqlite3.Row]]:
    table = quote_sqlite_identifier(
        table_name
    )

    rows = sqlite_connection.execute(
        f"PRAGMA foreign_key_list({table})"
    ).fetchall()

    grouped: dict[
        int,
        list[sqlite3.Row],
    ] = defaultdict(list)

    for row in rows:
        grouped[int(row["id"])].append(
            row
        )

    for group in grouped.values():
        group.sort(
            key=lambda row: int(
                row["seq"]
            )
        )

        yield group


def normalize_action(
    value: str | None,
) -> str:
    action = str(
        value or "NO ACTION"
    ).strip().upper()

    allowed = {
        "NO ACTION",
        "RESTRICT",
        "CASCADE",
        "SET NULL",
        "SET DEFAULT",
    }

    return (
        action
        if action in allowed
        else "NO ACTION"
    )


def apply_foreign_keys(
    sqlite_connection: sqlite3.Connection,
    pg: Any,
    source: SourceDatabase,
    table_name: str,
) -> int:
    count = 0

    for group in foreign_key_groups(
        sqlite_connection,
        table_name,
    ):
        referenced_table = str(
            group[0]["table"]
        )

        local_columns = [
            str(row["from"])
            for row in group
        ]

        referenced_columns = [
            (
                str(row["to"])
                if row["to"] is not None
                else ""
            )
            for row in group
        ]

        if any(
            not column
            for column in referenced_columns
        ):
            referenced_primary_key = (
                primary_key_columns(
                    sqlite_connection,
                    referenced_table,
                )
            )

            if (
                len(referenced_primary_key)
                != len(referenced_columns)
            ):
                raise RuntimeError(
                    "Foreign key tanpa kolom tujuan "
                    f"tidak dapat dipetakan: "
                    f"{table_name} → "
                    f"{referenced_table}"
                )

            referenced_columns = (
                referenced_primary_key
            )

        constraint_name = safe_object_name(
            "fk",
            table_name,
            *local_columns,
            referenced_table,
        )

        if constraint_exists(
            pg,
            source.schema_name,
            table_name,
            constraint_name,
        ):
            continue

        on_update = normalize_action(
            group[0]["on_update"]
        )

        on_delete = normalize_action(
            group[0]["on_delete"]
        )

        pg.execute(
            sql.SQL(
                "ALTER TABLE {}.{} "
                "ADD CONSTRAINT {} "
                "FOREIGN KEY ({}) "
                "REFERENCES {}.{} ({}) "
                "ON UPDATE {} "
                "ON DELETE {} "
                "NOT VALID"
            ).format(
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
                sql.Identifier(
                    constraint_name
                ),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in local_columns
                ),
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    referenced_table
                ),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column
                    in referenced_columns
                ),
                sql.SQL(on_update),
                sql.SQL(on_delete),
            )
        )

        pg.execute(
            sql.SQL(
                "ALTER TABLE {}.{} "
                "VALIDATE CONSTRAINT {}"
            ).format(
                sql.Identifier(
                    source.schema_name
                ),
                sql.Identifier(
                    table_name
                ),
                sql.Identifier(
                    constraint_name
                ),
            )
        )

        count += 1

    return count


def ensure_result_table(
    pg: Any,
) -> None:
    pg.execute(
        """
        CREATE TABLE IF NOT EXISTS
            docurapi_meta.schema_fidelity_results
        (
            source_database TEXT PRIMARY KEY,
            schema_name TEXT NOT NULL,
            tables_count BIGINT NOT NULL,
            primary_keys_count BIGINT NOT NULL,
            sequences_count BIGINT NOT NULL,
            not_null_count BIGINT NOT NULL,
            defaults_count BIGINT NOT NULL,
            indexes_count BIGINT NOT NULL,
            unique_indexes_count BIGINT NOT NULL,
            foreign_keys_count BIGINT NOT NULL,
            unsupported_defaults_count BIGINT NOT NULL,
            unsupported_indexes_count BIGINT NOT NULL,
            applied_at TIMESTAMPTZ
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def apply_database_schema(
    root: Path,
    source: SourceDatabase,
) -> dict[str, Any]:
    database_path = (
        root / source.relative_path
    ).resolve()

    if "system_backups" in database_path.parts:
        raise RuntimeError(
            "Database system backup tidak boleh diproses."
        )

    sqlite_connection = sqlite3.connect(
        f"file:{database_path}?mode=ro",
        uri=True,
    )

    sqlite_connection.row_factory = (
        sqlite3.Row
    )

    summary: dict[str, Any] = {
        "source_database":
            source.relative_path,
        "schema_name":
            source.schema_name,
        "tables": 0,
        "primary_keys": 0,
        "sequences": 0,
        "not_null": 0,
        "defaults": 0,
        "indexes": 0,
        "unique_indexes": 0,
        "foreign_keys": 0,
        "unsupported_defaults": 0,
        "unsupported_indexes": 0,
    }

    try:
        tables = sqlite_tables(
            sqlite_connection
        )

        with postgres_connection() as pg:
            ensure_result_table(pg)

            for table_name in tables:
                summary["tables"] += 1

                column_result = (
                    apply_column_rules(
                        sqlite_connection,
                        pg,
                        source,
                        table_name,
                    )
                )

                for key, value in (
                    column_result.items()
                ):
                    summary[key] += value

                primary_result = (
                    apply_primary_key(
                        sqlite_connection,
                        pg,
                        source,
                        table_name,
                    )
                )

                for key, value in (
                    primary_result.items()
                ):
                    summary[key] += value

                index_result = (
                    apply_indexes(
                        sqlite_connection,
                        pg,
                        source,
                        table_name,
                    )
                )

                for key, value in (
                    index_result.items()
                ):
                    summary[key] += value

            for table_name in tables:
                summary["foreign_keys"] += (
                    apply_foreign_keys(
                        sqlite_connection,
                        pg,
                        source,
                        table_name,
                    )
                )

            pg.execute(
                """
                INSERT INTO
                    docurapi_meta.schema_fidelity_results
                (
                    source_database,
                    schema_name,
                    tables_count,
                    primary_keys_count,
                    sequences_count,
                    not_null_count,
                    defaults_count,
                    indexes_count,
                    unique_indexes_count,
                    foreign_keys_count,
                    unsupported_defaults_count,
                    unsupported_indexes_count,
                    applied_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (source_database)
                DO UPDATE SET
                    schema_name =
                        EXCLUDED.schema_name,
                    tables_count =
                        EXCLUDED.tables_count,
                    primary_keys_count =
                        EXCLUDED.primary_keys_count,
                    sequences_count =
                        EXCLUDED.sequences_count,
                    not_null_count =
                        EXCLUDED.not_null_count,
                    defaults_count =
                        EXCLUDED.defaults_count,
                    indexes_count =
                        EXCLUDED.indexes_count,
                    unique_indexes_count =
                        EXCLUDED.unique_indexes_count,
                    foreign_keys_count =
                        EXCLUDED.foreign_keys_count,
                    unsupported_defaults_count =
                        EXCLUDED.unsupported_defaults_count,
                    unsupported_indexes_count =
                        EXCLUDED.unsupported_indexes_count,
                    applied_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    summary[
                        "source_database"
                    ],
                    summary[
                        "schema_name"
                    ],
                    summary["tables"],
                    summary[
                        "primary_keys"
                    ],
                    summary["sequences"],
                    summary["not_null"],
                    summary["defaults"],
                    summary["indexes"],
                    summary[
                        "unique_indexes"
                    ],
                    summary[
                        "foreign_keys"
                    ],
                    summary[
                        "unsupported_defaults"
                    ],
                    summary[
                        "unsupported_indexes"
                    ],
                ),
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
                    applied_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    source.relative_path,
                    "phase2b_schema_fidelity",
                    hashlib.sha256(
                        repr(summary).encode(
                            "utf-8"
                        )
                    ).hexdigest(),
                ),
            )

            pg.commit()

    finally:
        sqlite_connection.close()

    return summary


def apply_all_schema_fidelity(
    root: Path,
) -> list[dict[str, Any]]:
    return [
        apply_database_schema(
            root,
            source,
        )
        for source in SOURCE_DATABASES
    ]
