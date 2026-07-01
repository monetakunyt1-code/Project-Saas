from __future__ import annotations

import unittest

from services.sqlite_postgres_migration import (
    SOURCE_DATABASES,
    infer_postgres_type,
)


class SQLitePostgresMigrationTest(
    unittest.TestCase,
):
    def test_seven_active_databases(
        self,
    ) -> None:
        self.assertEqual(
            len(SOURCE_DATABASES),
            7,
        )

        for source in SOURCE_DATABASES:
            self.assertNotIn(
                "system_backups",
                source.relative_path,
            )

    def test_integer_mapping(
        self,
    ) -> None:
        self.assertEqual(
            infer_postgres_type(
                "INTEGER",
                ("integer",),
            ),
            "BIGINT",
        )

    def test_real_mapping(
        self,
    ) -> None:
        self.assertEqual(
            infer_postgres_type(
                "REAL",
                (
                    "integer",
                    "real",
                ),
            ),
            "DOUBLE PRECISION",
        )

    def test_text_mapping(
        self,
    ) -> None:
        self.assertEqual(
            infer_postgres_type(
                "VARCHAR(255)",
                ("text",),
            ),
            "TEXT",
        )

    def test_blob_mapping(
        self,
    ) -> None:
        self.assertEqual(
            infer_postgres_type(
                "BLOB",
                ("blob",),
            ),
            "BYTEA",
        )

    def test_mixed_storage_uses_text(
        self,
    ) -> None:
        self.assertEqual(
            infer_postgres_type(
                "",
                (
                    "integer",
                    "text",
                ),
            ),
            "TEXT",
        )


if __name__ == "__main__":
    unittest.main()
