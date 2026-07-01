from __future__ import annotations

import unittest
from decimal import Decimal

from services.qris_manual_payments import QrisPaymentError, detect_proof_type, normalize_amount


class QrisManualPaymentsTest(unittest.TestCase):
    def test_normalize_amount(self) -> None:
        self.assertEqual(normalize_amount("15000"), Decimal("15000.00"))

    def test_invalid_amount(self) -> None:
        with self.assertRaises(QrisPaymentError):
            normalize_amount(0)

    def test_detect_png(self) -> None:
        content_type, extension = detect_proof_type(b"\x89PNG\r\n\x1a\n" + b"data")
        self.assertEqual(content_type, "image/png")
        self.assertEqual(extension, ".png")

    def test_reject_unknown_file(self) -> None:
        with self.assertRaises(QrisPaymentError):
            detect_proof_type(b"not-an-image")


if __name__ == "__main__":
    unittest.main()
