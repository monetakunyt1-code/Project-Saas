"""Adapter database pusat DocuRapi.

Adapter mempertahankan API sqlite3 untuk modul lama dan memilih
backend berdasarkan environment variable.

Tanpa URL PostgreSQL:
    runtime menggunakan SQLite asli.

Dengan DOCURAPI_DATABASE_URL / DATABASE_URL / POSTGRES_URL:
    runtime menggunakan PostgreSQL melalui wrapper kompatibilitas.
"""

from __future__ import annotations

import os
import re
import sqlite3 as _sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import tuple_row


# Mengekspor konstanta, exception, class, dan helper sqlite3 agar
# seluruh modul lama tetap dapat menggunakan adapter sebagai sqlite3.
for _name in dir(_sqlite3):
    if not _name.startswith("__"):
        globals().setdefault(
            _name,
            getattr(_sqlite3, _name),
        )


_POSTGRES_ENV_NAMES = (
    "DOCURAPI_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
)

_SCHEMA_SUFFIXES = (
    (
        "storage/background/background_jobs.db",
        "background",
    ),
    (
        "storage/notifications/notifications.db",
        "notifications",
    ),
    (
        "storage/system/observability.db",
        "observability",
    ),
    (
        "storage/billing/billing.db",
        "billing",
    ),
    (
        "storage/saas/security.db",
        "security",
    ),
    (
        "storage/saas/saas.db",
        "saas",
    ),
    (
        "storage/docurapi.db",
        "core",
    ),
)

_PRAGMA_TABLE_INFO = re.compile(
    r"^\s*PRAGMA\s+table_info\s*\(\s*(.+?)\s*\)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_INSERT_OR_IGNORE = re.compile(
    r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
    re.IGNORECASE,
)

_AUTOINCREMENT_PRIMARY_KEY = re.compile(
    r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
    re.IGNORECASE,
)

_AUTOINCREMENT = re.compile(
    r"\bAUTOINCREMENT\b",
    re.IGNORECASE,
)

_BLOB_TYPE = re.compile(
    r"\bBLOB\b",
    re.IGNORECASE,
)


def database_url() -> str:
    for name in _POSTGRES_ENV_NAMES:
        value = os.environ.get(
            name,
            "",
        ).strip()

        if value:
            return value

    return ""


def _normalize_postgres_url(
    value: str,
) -> str:
    normalized = value.strip()

    if normalized.startswith(
        "postgres://"
    ):
        normalized = (
            "postgresql://"
            + normalized[
                len("postgres://"):
            ]
        )

    if normalized.startswith(
        "postgresql+psycopg://"
    ):
        normalized = (
            "postgresql://"
            + normalized[
                len(
                    "postgresql+psycopg://"
                ):
            ]
        )

    return normalized


def requested_backend() -> str:
    value = database_url().lower()

    if value.startswith(
        (
            "postgres://",
            "postgresql://",
            "postgresql+psycopg://",
        )
    ):
        return "postgresql"

    return "sqlite"


def backend_name() -> str:
    return requested_backend()


def schema_for_database(
    database: Any,
) -> str:
    value = os.fspath(
        database
    )

    normalized = value.strip()

    if normalized.startswith(
        "file:"
    ):
        normalized = normalized[5:]

    normalized = normalized.split(
        "?",
        1,
    )[0]

    normalized = normalized.replace(
        "\\",
        "/",
    ).lower()

    normalized = str(
        Path(normalized)
    ).replace(
        "\\",
        "/",
    )

    for suffix, schema_name in (
        _SCHEMA_SUFFIXES
    ):
        if normalized.endswith(
            suffix
        ):
            return schema_name

    basename = Path(
        normalized
    ).name

    basename_mapping = {
        "docurapi.db": "core",
        "billing.db": "billing",
        "saas.db": "saas",
        "security.db": "security",
        "background_jobs.db":
            "background",
        "notifications.db":
            "notifications",
        "observability.db":
            "observability",
    }

    if basename in basename_mapping:
        return basename_mapping[
            basename
        ]

    raise RuntimeError(
        "Database SQLite tidak memiliki pemetaan "
        f"schema PostgreSQL: {value}"
    )


def _translate_placeholders(
    statement: str,
) -> str:
    output: list[str] = []

    index = 0
    length = len(statement)

    single_quote = False
    double_quote = False
    line_comment = False
    block_comment = False

    while index < length:
        character = statement[index]
        next_character = (
            statement[index + 1]
            if index + 1 < length
            else ""
        )

        if line_comment:
            output.append(
                character
            )

            if character == "\n":
                line_comment = False

            index += 1
            continue

        if block_comment:
            output.append(
                character
            )

            if (
                character == "*"
                and next_character == "/"
            ):
                output.append(
                    next_character
                )

                block_comment = False
                index += 2
                continue

            index += 1
            continue

        if (
            not single_quote
            and not double_quote
            and character == "-"
            and next_character == "-"
        ):
            output.extend(
                (
                    character,
                    next_character,
                )
            )

            line_comment = True
            index += 2
            continue

        if (
            not single_quote
            and not double_quote
            and character == "/"
            and next_character == "*"
        ):
            output.extend(
                (
                    character,
                    next_character,
                )
            )

            block_comment = True
            index += 2
            continue

        if character == "'" and not double_quote:
            output.append(
                character
            )

            if single_quote:
                if next_character == "'":
                    output.append(
                        next_character
                    )

                    index += 2
                    continue

                single_quote = False
            else:
                single_quote = True

            index += 1
            continue

        if character == '"' and not single_quote:
            output.append(
                character
            )

            if double_quote:
                if next_character == '"':
                    output.append(
                        next_character
                    )

                    index += 2
                    continue

                double_quote = False
            else:
                double_quote = True

            index += 1
            continue

        if (
            character == "?"
            and not single_quote
            and not double_quote
        ):
            output.append(
                "%s"
            )
        else:
            output.append(
                character
            )

        index += 1

    return "".join(
        output
    )


def _translate_insert_or_ignore(
    statement: str,
) -> str:
    if not _INSERT_OR_IGNORE.search(
        statement
    ):
        return statement

    translated = _INSERT_OR_IGNORE.sub(
        "INSERT INTO",
        statement,
        count=1,
    )

    if re.search(
        r"\bON\s+CONFLICT\b",
        translated,
        re.IGNORECASE,
    ):
        return translated

    stripped = translated.rstrip()

    semicolon = (
        ";"
        if stripped.endswith(";")
        else ""
    )

    if semicolon:
        stripped = stripped[:-1].rstrip()

    return (
        stripped
        + " ON CONFLICT DO NOTHING"
        + semicolon
    )


def _translate_ddl(
    statement: str,
) -> str:
    translated = (
        _AUTOINCREMENT_PRIMARY_KEY.sub(
            "BIGSERIAL PRIMARY KEY",
            statement,
        )
    )

    translated = _AUTOINCREMENT.sub(
        "",
        translated,
    )

    translated = _BLOB_TYPE.sub(
        "BYTEA",
        translated,
    )

    return translated


def _translate_runtime_sql(
    statement: str,
) -> str:
    translated = _translate_ddl(
        statement
    )

    translated = (
        _translate_insert_or_ignore(
            translated
        )
    )

    translated = (
        _translate_placeholders(
            translated
        )
    )

    return translated


def _split_sql_script(
    script: str,
) -> list[str]:
    statements: list[str] = []
    current: list[str] = []

    index = 0
    length = len(script)

    single_quote = False
    double_quote = False
    line_comment = False
    block_comment = False

    while index < length:
        character = script[index]
        next_character = (
            script[index + 1]
            if index + 1 < length
            else ""
        )

        if line_comment:
            current.append(
                character
            )

            if character == "\n":
                line_comment = False

            index += 1
            continue

        if block_comment:
            current.append(
                character
            )

            if (
                character == "*"
                and next_character == "/"
            ):
                current.append(
                    next_character
                )

                block_comment = False
                index += 2
                continue

            index += 1
            continue

        if (
            not single_quote
            and not double_quote
            and character == "-"
            and next_character == "-"
        ):
            current.extend(
                (
                    character,
                    next_character,
                )
            )

            line_comment = True
            index += 2
            continue

        if (
            not single_quote
            and not double_quote
            and character == "/"
            and next_character == "*"
        ):
            current.extend(
                (
                    character,
                    next_character,
                )
            )

            block_comment = True
            index += 2
            continue

        if character == "'" and not double_quote:
            current.append(
                character
            )

            if single_quote:
                if next_character == "'":
                    current.append(
                        next_character
                    )

                    index += 2
                    continue

                single_quote = False
            else:
                single_quote = True

            index += 1
            continue

        if character == '"' and not single_quote:
            current.append(
                character
            )

            if double_quote:
                if next_character == '"':
                    current.append(
                        next_character
                    )

                    index += 2
                    continue

                double_quote = False
            else:
                double_quote = True

            index += 1
            continue

        if (
            character == ";"
            and not single_quote
            and not double_quote
        ):
            statement = "".join(
                current
            ).strip()

            if statement:
                statements.append(
                    statement
                )

            current = []
            index += 1
            continue

        current.append(
            character
        )

        index += 1

    remaining = "".join(
        current
    ).strip()

    if remaining:
        statements.append(
            remaining
        )

    return statements


def _strip_identifier_quotes(
    value: str,
) -> str:
    normalized = value.strip()

    pairs = (
        ('"', '"'),
        ("'", "'"),
        ("`", "`"),
        ("[", "]"),
    )

    for start, end in pairs:
        if (
            normalized.startswith(start)
            and normalized.endswith(end)
            and len(normalized) >= 2
        ):
            normalized = normalized[
                1:-1
            ]

            break

    return normalized.replace(
        '""',
        '"',
    )


def _translate_sqlite_master(
    statement: str,
) -> str:
    if not re.search(
        r"\bsqlite_master\b",
        statement,
        re.IGNORECASE,
    ):
        return statement

    return """
        SELECT
            table_name AS name
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """


def _translate_exception(
    exception: psycopg.Error,
) -> None:
    message = str(
        exception
    )

    if isinstance(
        exception,
        psycopg.IntegrityError,
    ):
        raise _sqlite3.IntegrityError(
            message
        ) from exception

    if isinstance(
        exception,
        psycopg.OperationalError,
    ):
        raise _sqlite3.OperationalError(
            message
        ) from exception

    if isinstance(
        exception,
        psycopg.ProgrammingError,
    ):
        raise _sqlite3.ProgrammingError(
            message
        ) from exception

    if isinstance(
        exception,
        psycopg.InterfaceError,
    ):
        raise _sqlite3.InterfaceError(
            message
        ) from exception

    raise _sqlite3.DatabaseError(
        message
    ) from exception


class _CompatRow:
    __slots__ = (
        "_names",
        "_values",
        "_mapping",
    )

    def __init__(
        self,
        names: Sequence[str],
        values: Sequence[Any],
    ) -> None:
        self._names = tuple(
            str(name)
            for name in names
        )

        self._values = tuple(
            values
        )

        self._mapping = {
            name: self._values[index]
            for index, name in enumerate(
                self._names
            )
        }

    def keys(
        self,
    ) -> list[str]:
        return list(
            self._names
        )

    def __getitem__(
        self,
        key: int | slice | str,
    ) -> Any:
        if isinstance(
            key,
            (
                int,
                slice,
            ),
        ):
            return self._values[
                key
            ]

        return self._mapping[
            str(key)
        ]

    def __iter__(
        self,
    ) -> Iterator[Any]:
        return iter(
            self._values
        )

    def __len__(
        self,
    ) -> int:
        return len(
            self._values
        )

    def __repr__(
        self,
    ) -> str:
        return repr(
            self._values
        )


def _description_name(
    column: Any,
) -> str:
    name = getattr(
        column,
        "name",
        None,
    )

    if name is not None:
        return str(
            name
        )

    try:
        return str(
            column[0]
        )
    except Exception:
        return ""


def _description_tuple(
    column: Any,
) -> tuple[Any, ...]:
    return (
        _description_name(column),
        getattr(
            column,
            "type_code",
            None,
        ),
        getattr(
            column,
            "display_size",
            None,
        ),
        getattr(
            column,
            "internal_size",
            None,
        ),
        getattr(
            column,
            "precision",
            None,
        ),
        getattr(
            column,
            "scale",
            None,
        ),
        getattr(
            column,
            "null_ok",
            None,
        ),
    )


class Cursor:
    def __init__(
        self,
        connection: "Connection",
        native_cursor: Any,
    ) -> None:
        self._connection_wrapper = (
            connection
        )

        self._cursor = native_cursor

        self._fake_rows: list[
            tuple[Any, ...]
        ] | None = None

        self._fake_columns: tuple[
            str,
            ...,
        ] = ()

        self._fake_position = 0

    @property
    def connection(
        self,
    ) -> "Connection":
        return self._connection_wrapper

    @property
    def description(
        self,
    ) -> Any:
        if self._fake_rows is not None:
            return [
                (
                    name,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                for name in self._fake_columns
            ]

        description = (
            self._cursor.description
        )

        if description is None:
            return None

        return [
            _description_tuple(
                column
            )
            for column in description
        ]

    @property
    def rowcount(
        self,
    ) -> int:
        if self._fake_rows is not None:
            return len(
                self._fake_rows
            )

        return int(
            self._cursor.rowcount
        )

    @property
    def lastrowid(
        self,
    ) -> None:
        return None

    def _clear_fake(
        self,
    ) -> None:
        self._fake_rows = None
        self._fake_columns = ()
        self._fake_position = 0

    def _set_fake(
        self,
        columns: Sequence[str],
        rows: Iterable[
            Sequence[Any]
        ],
    ) -> "Cursor":
        self._fake_columns = tuple(
            str(column)
            for column in columns
        )

        self._fake_rows = [
            tuple(row)
            for row in rows
        ]

        self._fake_position = 0

        return self

    def _wrap_row(
        self,
        row: Sequence[Any] | None,
    ) -> Any:
        if row is None:
            return None

        values = tuple(
            row
        )

        if (
            self._connection_wrapper
            .row_factory
            is None
        ):
            return values

        description = (
            self._cursor.description
        )

        names = [
            _description_name(
                column
            )
            for column in (
                description or ()
            )
        ]

        return _CompatRow(
            names,
            values,
        )

    def _wrap_fake_row(
        self,
        row: Sequence[Any],
    ) -> Any:
        values = tuple(
            row
        )

        if (
            self._connection_wrapper
            .row_factory
            is None
        ):
            return values

        return _CompatRow(
            self._fake_columns,
            values,
        )

    def execute(
        self,
        statement: Any,
        parameters: Any = None,
    ) -> "Cursor":
        self._clear_fake()

        if not isinstance(
            statement,
            str,
        ):
            try:
                if parameters is None:
                    self._cursor.execute(
                        statement
                    )
                else:
                    self._cursor.execute(
                        statement,
                        parameters,
                    )

                return self

            except psycopg.Error as exception:
                _translate_exception(
                    exception
                )

        stripped = statement.strip()
        upper = stripped.upper()

        if re.fullmatch(
            r"PRAGMA\s+QUICK_CHECK\s*;?",
            stripped,
            re.IGNORECASE,
        ):
            return self._set_fake(
                ("quick_check",),
                (("ok",),),
            )

        if re.match(
            r"^PRAGMA\s+JOURNAL_MODE",
            stripped,
            re.IGNORECASE,
        ):
            return self._set_fake(
                ("journal_mode",),
                (("wal",),),
            )

        if re.match(
            r"^PRAGMA\s+FOREIGN_KEYS",
            stripped,
            re.IGNORECASE,
        ):
            return self._set_fake(
                ("foreign_keys",),
                ((1,),),
            )

        table_info_match = (
            _PRAGMA_TABLE_INFO.match(
                stripped
            )
        )

        if table_info_match:
            table_name = (
                _strip_identifier_quotes(
                    table_info_match.group(
                        1
                    )
                )
            )

            query = """
                SELECT
                    columns.ordinal_position - 1
                        AS cid,
                    columns.column_name
                        AS name,
                    columns.data_type
                        AS type,
                    CASE
                        WHEN columns.is_nullable = 'NO'
                        THEN 1
                        ELSE 0
                    END AS notnull,
                    columns.column_default
                        AS dflt_value,
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM
                                information_schema
                                .table_constraints
                                AS constraints
                            JOIN
                                information_schema
                                .key_column_usage
                                AS keys
                              ON
                                keys.constraint_name =
                                constraints.constraint_name
                             AND
                                keys.table_schema =
                                constraints.table_schema
                             AND
                                keys.table_name =
                                constraints.table_name
                            WHERE
                                constraints.constraint_type =
                                'PRIMARY KEY'
                              AND
                                constraints.table_schema =
                                columns.table_schema
                              AND
                                constraints.table_name =
                                columns.table_name
                              AND
                                keys.column_name =
                                columns.column_name
                        )
                        THEN 1
                        ELSE 0
                    END AS pk
                FROM information_schema.columns
                    AS columns
                WHERE
                    columns.table_schema =
                    current_schema()
                  AND
                    columns.table_name = %s
                ORDER BY
                    columns.ordinal_position
            """

            try:
                self._cursor.execute(
                    query,
                    (table_name,),
                )

                return self

            except psycopg.Error as exception:
                _translate_exception(
                    exception
                )

        if re.fullmatch(
            r"BEGIN\s+IMMEDIATE\s*;?",
            stripped,
            re.IGNORECASE,
        ):
            try:
                self._cursor.execute(
                    """
                    SELECT
                        pg_advisory_xact_lock(
                            hashtext(%s)
                        )
                    """,
                    (
                        "docurapi:"
                        + self
                        ._connection_wrapper
                        .schema_name
                        + ":immediate",
                    ),
                )

                return self

            except psycopg.Error as exception:
                _translate_exception(
                    exception
                )

        if upper.startswith(
            "PRAGMA "
        ):
            raise _sqlite3.OperationalError(
                "PRAGMA SQLite tidak didukung "
                f"pada PostgreSQL: {stripped}"
            )

        translated = (
            _translate_sqlite_master(
                statement
            )
        )

        translated = (
            _translate_runtime_sql(
                translated
            )
        )

        try:
            if parameters is None:
                self._cursor.execute(
                    translated
                )
            else:
                self._cursor.execute(
                    translated,
                    parameters,
                )

            if self._cursor.rowcount > 0:
                self._connection_wrapper\
                    ._total_changes += int(
                        self._cursor.rowcount
                    )

            return self

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def executemany(
        self,
        statement: str,
        parameters: Iterable[
            Sequence[Any] | Mapping[str, Any]
        ],
    ) -> "Cursor":
        self._clear_fake()

        translated = (
            _translate_runtime_sql(
                statement
            )
        )

        try:
            self._cursor.executemany(
                translated,
                parameters,
                returning=False,
            )

            if self._cursor.rowcount > 0:
                self._connection_wrapper\
                    ._total_changes += int(
                        self._cursor.rowcount
                    )

            return self

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def executescript(
        self,
        script: str,
    ) -> "Cursor":
        statements = _split_sql_script(
            script
        )

        for statement in statements:
            if re.match(
                r"^\s*PRAGMA\b",
                statement,
                re.IGNORECASE,
            ):
                self.execute(
                    statement
                )

                continue

            translated = (
                _translate_runtime_sql(
                    statement
                )
            )

            try:
                self._cursor.execute(
                    translated
                )

            except psycopg.Error as exception:
                _translate_exception(
                    exception
                )

        return self

    def fetchone(
        self,
    ) -> Any:
        if self._fake_rows is not None:
            if (
                self._fake_position
                >= len(self._fake_rows)
            ):
                return None

            row = self._fake_rows[
                self._fake_position
            ]

            self._fake_position += 1

            return self._wrap_fake_row(
                row
            )

        try:
            return self._wrap_row(
                self._cursor.fetchone()
            )

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def fetchmany(
        self,
        size: int | None = None,
    ) -> list[Any]:
        if self._fake_rows is not None:
            amount = (
                size
                if size is not None
                else 1
            )

            start = self._fake_position
            end = min(
                start + amount,
                len(self._fake_rows),
            )

            self._fake_position = end

            return [
                self._wrap_fake_row(
                    row
                )
                for row in self._fake_rows[
                    start:end
                ]
            ]

        try:
            rows = (
                self._cursor.fetchmany(
                    size
                )
                if size is not None
                else self._cursor.fetchmany()
            )

            return [
                self._wrap_row(
                    row
                )
                for row in rows
            ]

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def fetchall(
        self,
    ) -> list[Any]:
        if self._fake_rows is not None:
            rows = self._fake_rows[
                self._fake_position:
            ]

            self._fake_position = len(
                self._fake_rows
            )

            return [
                self._wrap_fake_row(
                    row
                )
                for row in rows
            ]

        try:
            return [
                self._wrap_row(
                    row
                )
                for row in (
                    self._cursor.fetchall()
                )
            ]

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def close(
        self,
    ) -> None:
        self._cursor.close()

    def __iter__(
        self,
    ) -> Iterator[Any]:
        while True:
            row = self.fetchone()

            if row is None:
                break

            yield row

    def __enter__(
        self,
    ) -> "Cursor":
        return self

    def __exit__(
        self,
        exception_type: Any,
        exception: Any,
        traceback: Any,
    ) -> bool:
        self.close()
        return False

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        return getattr(
            self._cursor,
            name,
        )


class Connection:
    def __init__(
        self,
        native_connection: Any,
        *,
        schema_name: str,
        source_database: str,
    ) -> None:
        self._connection = (
            native_connection
        )

        self.schema_name = (
            schema_name
        )

        self.source_database = (
            source_database
        )

        self.row_factory: Any = None
        self.text_factory: Any = str

        self._total_changes = 0

    @property
    def total_changes(
        self,
    ) -> int:
        return self._total_changes

    @property
    def in_transaction(
        self,
    ) -> bool:
        return (
            self._connection
            .info
            .transaction_status
            != TransactionStatus.IDLE
        )

    @property
    def isolation_level(
        self,
    ) -> str:
        return "DEFERRED"

    @isolation_level.setter
    def isolation_level(
        self,
        value: Any,
    ) -> None:
        del value

    def cursor(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Cursor:
        del args, kwargs

        return Cursor(
            self,
            self._connection.cursor(),
        )

    def execute(
        self,
        statement: Any,
        parameters: Any = None,
    ) -> Cursor:
        cursor = self.cursor()

        return cursor.execute(
            statement,
            parameters,
        )

    def executemany(
        self,
        statement: str,
        parameters: Iterable[
            Sequence[Any] | Mapping[str, Any]
        ],
    ) -> Cursor:
        cursor = self.cursor()

        return cursor.executemany(
            statement,
            parameters,
        )

    def executescript(
        self,
        script: str,
    ) -> Cursor:
        cursor = self.cursor()

        return cursor.executescript(
            script
        )

    def commit(
        self,
    ) -> None:
        try:
            self._connection.commit()

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def rollback(
        self,
    ) -> None:
        try:
            self._connection.rollback()

        except psycopg.Error as exception:
            _translate_exception(
                exception
            )

    def close(
        self,
    ) -> None:
        self._connection.close()

    def __enter__(
        self,
    ) -> "Connection":
        return self

    def __exit__(
        self,
        exception_type: Any,
        exception: Any,
        traceback: Any,
    ) -> bool:
        if exception_type is None:
            self.commit()
        else:
            self.rollback()

        return False

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        return getattr(
            self._connection,
            name,
        )


def connect(
    *args: Any,
    **kwargs: Any,
) -> Any:
    backend = requested_backend()

    if backend == "sqlite":
        return _sqlite3.connect(
            *args,
            **kwargs,
        )

    database = (
        args[0]
        if args
        else kwargs.get(
            "database"
        )
    )

    if database is None:
        raise TypeError(
            "connect() membutuhkan path database "
            "untuk menentukan schema PostgreSQL."
        )

    schema_name = schema_for_database(
        database
    )

    url = _normalize_postgres_url(
        database_url()
    )

    timeout = kwargs.get(
        "timeout",
        30,
    )

    try:
        connect_timeout = max(
            1,
            int(float(timeout)),
        )
    except (
        TypeError,
        ValueError,
    ):
        connect_timeout = 30

    try:
        native_connection = (
            psycopg.connect(
                url,
                row_factory=tuple_row,
                connect_timeout=
                    connect_timeout,
                application_name=
                    "docurapi",
                options=(
                    "-csearch_path="
                    + schema_name
                    + ",public"
                ),
            )
        )

    except psycopg.Error as exception:
        _translate_exception(
            exception
        )

    return Connection(
        native_connection,
        schema_name=schema_name,
        source_database=os.fspath(
            database
        ),
    )


def __getattr__(
    name: str,
) -> Any:
    return getattr(
        _sqlite3,
        name,
    )
