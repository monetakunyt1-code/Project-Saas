from __future__ import annotations

import os
import unittest

_DATABASE_ENVIRONMENT = ("DOCURAPI_DATABASE_URL", "DATABASE_URL", "POSTGRES_URL")
_SAVED = {name: os.environ.pop(name) for name in _DATABASE_ENVIRONMENT if name in os.environ}
try:
    from app import app
finally:
    os.environ.update(_SAVED)


class QrisManualRoutesTest(unittest.TestCase):
    def test_required_routes_exist_once(self) -> None:
        required = {
            "/api/payments/qris/manual/config",
            "/api/payments/qris/manual/health",
            "/api/payments/qris/manual/orders/{order_id}/prepare",
            "/api/payments/qris/manual/orders/{order_id}/proof",
            "/api/payments/qris/manual/admin/submissions",
            "/api/payments/qris/manual/admin/orders/{order_id}/proof",
            "/api/payments/qris/manual/admin/orders/{order_id}/approve",
            "/api/payments/qris/manual/admin/orders/{order_id}/reject",
            "/qris-payment/{order_id}",
            "/admin/qris-payments",
        }
        for path in required:
            total = sum(1 for route in app.routes if getattr(route, "path", None) == path)
            self.assertEqual(total, 1, path)


if __name__ == "__main__":
    unittest.main()
