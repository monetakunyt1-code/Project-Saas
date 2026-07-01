from __future__ import annotations

import os
import unittest
from pathlib import Path


# Secret khusus automated test, bukan secret production.
os.environ.setdefault(
    "DOCURAPI_SECRET_KEY",
    (
        "ci-docurapi-secret-"
        "8f42d9e0b6534c6f97a0d3e6c28f1b5a"
        "9a4c7e1d6f832b50"
    ),
)

os.environ.setdefault(
    "DOCURAPI_SESSION_SECRET",
    (
        "ci-docurapi-session-"
        "c7e13b9a48f620d5e3a91c7b4f8652d0"
        "a9e347b61c528f90"
    ),
)

os.environ.setdefault(
    "DOCURAPI_PAYMENT_WEBHOOK_SECRET",
    (
        "ci-docurapi-webhook-"
        "5d8e31a7b4c960f2e6a38d1c7b5290f4"
        "a6e187c35d942b80"
    ),
)

Path("storage").mkdir(
    parents=True,
    exist_ok=True,
)

Path("logs").mkdir(
    parents=True,
    exist_ok=True,
)

from app import app  # noqa: E402


class ApplicationSmokeTest(unittest.TestCase):
    def test_application_is_fastapi(self) -> None:
        self.assertEqual(
            type(app).__name__,
            "FastAPI",
        )

    def test_application_has_routes(self) -> None:
        self.assertGreaterEqual(
            len(app.routes),
            100,
        )

    def test_required_routes_exist(self) -> None:
        paths = {
            path
            for route in app.routes
            if isinstance(
                path := getattr(
                    route,
                    "path",
                    None,
                ),
                str,
            )
        }

        required = {
            "/",
            "/billing",
            "/api/plans",
            "/api/process",
        }

        self.assertEqual(
            required - paths,
            set(),
        )

    def test_openapi_can_be_generated(self) -> None:
        schema = app.openapi()

        self.assertEqual(
            schema.get("openapi"),
            "3.1.0",
        )

        self.assertIn(
            "paths",
            schema,
        )


if __name__ == "__main__":
    unittest.main()
