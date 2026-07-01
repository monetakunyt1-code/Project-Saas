from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.postgres_connection import (
    DOCURAPI_SCHEMAS,
    is_postgres_url,
    normalize_database_url,
    resolve_database_url,
)


class PostgresConnectionTest(
    unittest.TestCase,
):
    def test_normalizes_legacy_postgres_url(
        self,
    ) -> None:
        self.assertEqual(
            normalize_database_url(
                "postgres://user:pass@host/db"
            ),
            "postgresql://user:pass@host/db",
        )

    def test_recognizes_postgres_url(
        self,
    ) -> None:
        self.assertTrue(
            is_postgres_url(
                "postgresql://user:pass@host/db"
            )
        )

        self.assertFalse(
            is_postgres_url(
                "sqlite:///storage/app.db"
            )
        )

    def test_resolves_primary_environment(
        self,
    ) -> None:
        environment = {
            "DOCURAPI_DATABASE_URL":
                "postgresql://user:pass@host/db",
        }

        with patch.dict(
            os.environ,
            environment,
            clear=True,
        ):
            self.assertEqual(
                resolve_database_url(),
                environment[
                    "DOCURAPI_DATABASE_URL"
                ],
            )

    def test_rejects_non_postgres_url(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "DOCURAPI_DATABASE_URL":
                    "sqlite:///storage/app.db",
            },
            clear=True,
        ):
            with self.assertRaises(
                RuntimeError
            ):
                resolve_database_url()

    def test_expected_schemas_exist(
        self,
    ) -> None:
        self.assertEqual(
            set(DOCURAPI_SCHEMAS),
            {
                "core",
                "billing",
                "saas",
                "security",
                "background",
                "notifications",
                "observability",
                "docurapi_meta",
            },
        )


if __name__ == "__main__":
    unittest.main()
