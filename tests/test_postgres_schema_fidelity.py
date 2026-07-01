from __future__ import annotations

import unittest

from services.postgres_schema_fidelity import (
    safe_object_name,
    strip_outer_parentheses,
    translate_sqlite_default,
)


class PostgresSchemaFidelityTest(
    unittest.TestCase,
):
    def test_safe_name_limit(
        self,
    ) -> None:
        name = safe_object_name(
            "table" * 30,
            "column" * 30,
        )

        self.assertLessEqual(
            len(name.encode("utf-8")),
            63,
        )

    def test_numeric_default(
        self,
    ) -> None:
        result = translate_sqlite_default(
            "(0)"
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.kind,
            "raw",
        )
        self.assertEqual(
            result.value,
            "0",
        )

    def test_timestamp_default(
        self,
    ) -> None:
        result = translate_sqlite_default(
            "datetime('now')"
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.value,
            "CURRENT_TIMESTAMP",
        )

    def test_string_default(
        self,
    ) -> None:
        result = translate_sqlite_default(
            "'pending'"
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.kind,
            "literal",
        )
        self.assertEqual(
            result.value,
            "pending",
        )

    def test_outer_parentheses(
        self,
    ) -> None:
        self.assertEqual(
            strip_outer_parentheses(
                "(((CURRENT_TIMESTAMP)))"
            ),
            "CURRENT_TIMESTAMP",
        )


if __name__ == "__main__":
    unittest.main()
