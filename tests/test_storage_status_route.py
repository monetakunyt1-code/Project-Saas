from __future__ import annotations

import os
import unittest


_DATABASE_ENVIRONMENT = (
    "DOCURAPI_DATABASE_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
)

_SAVED_DATABASE_ENVIRONMENT = {
    name: os.environ.pop(name)
    for name in _DATABASE_ENVIRONMENT
    if name in os.environ
}

try:
    from app import app
finally:
    os.environ.update(
        _SAVED_DATABASE_ENVIRONMENT
    )


class StorageStatusRouteTest(
    unittest.TestCase,
):
    def test_storage_status_route_exists(
        self,
    ) -> None:
        paths = {
            getattr(
                route,
                "path",
                None,
            )
            for route in app.routes
        }

        self.assertIn(
            "/api/storage/status",
            paths,
        )

    def test_storage_status_route_unique(
        self,
    ) -> None:
        matching = [
            route
            for route in app.routes
            if getattr(
                route,
                "path",
                None,
            )
            == "/api/storage/status"
        ]

        self.assertEqual(
            len(matching),
            1,
        )


if __name__ == "__main__":
    unittest.main()
