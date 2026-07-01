from __future__ import annotations

import unittest

from services.database_adapter import (
    _split_sql_script,
    _translate_ddl,
    _translate_insert_or_ignore,
    _translate_placeholders,
    schema_for_database,
)


class DatabaseAdapterPostgresTest(
    unittest.TestCase,
):
    def test_schema_mapping(
        self,
    ) -> None:
        cases = {
            "storage/docurapi.db":
                "core",
            "storage/billing/billing.db":
                "billing",
            "storage/saas/saas.db":
                "saas",
            "storage/saas/security.db":
                "security",
            (
                "storage/background/"
                "background_jobs.db"
            ):
                "background",
            (
                "storage/notifications/"
                "notifications.db"
            ):
                "notifications",
            (
                "storage/system/"
                "observability.db"
            ):
                "observability",
        }

        for path, expected in cases.items():
            with self.subTest(
                path=path
            ):
                self.assertEqual(
                    schema_for_database(
                        path
                    ),
                    expected,
                )

    def test_unknown_database_rejected(
        self,
    ) -> None:
        with self.assertRaises(
            RuntimeError
        ):
            schema_for_database(
                "storage/unknown.db"
            )

    def test_question_placeholder(
        self,
    ) -> None:
        statement = (
            "SELECT '?' AS literal, "
            "value = ? "
            'AND "question?" = ?'
        )

        self.assertEqual(
            _translate_placeholders(
                statement
            ),
            (
                "SELECT '?' AS literal, "
                "value = %s "
                'AND "question?" = %s'
            ),
        )

    def test_insert_or_ignore(
        self,
    ) -> None:
        statement = (
            "INSERT OR IGNORE INTO "
            "items(id) VALUES (?)"
        )

        translated = (
            _translate_insert_or_ignore(
                statement
            )
        )

        self.assertIn(
            "INSERT INTO",
            translated,
        )

        self.assertIn(
            "ON CONFLICT DO NOTHING",
            translated,
        )

    def test_autoincrement_ddl(
        self,
    ) -> None:
        statement = (
            "CREATE TABLE sample ("
            "id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, "
            "payload BLOB)"
        )

        translated = _translate_ddl(
            statement
        )

        self.assertIn(
            "BIGSERIAL PRIMARY KEY",
            translated,
        )

        self.assertIn(
            "BYTEA",
            translated,
        )

        self.assertNotIn(
            "AUTOINCREMENT",
            translated,
        )

    def test_script_split(
        self,
    ) -> None:
        script = (
            "CREATE TABLE a "
            "(value TEXT DEFAULT ';');"
            "CREATE INDEX idx_a "
            "ON a(value);"
        )

        statements = (
            _split_sql_script(
                script
            )
        )

        self.assertEqual(
            len(statements),
            2,
        )


if __name__ == "__main__":
    unittest.main()
