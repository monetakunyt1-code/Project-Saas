from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.object_storage import (
    InvalidObjectKeyError,
    LocalObjectStorage,
    ObjectNotFoundError,
    backend_name,
    normalize_key,
)


class ObjectStorageTest(
    unittest.TestCase,
):
    def test_normalize_key(
        self,
    ) -> None:
        self.assertEqual(
            normalize_key(
                r"users\alpha\document.docx"
            ),
            "users/alpha/document.docx",
        )

    def test_rejects_path_traversal(
        self,
    ) -> None:
        invalid = (
            "../secret.txt",
            "users/../../secret.txt",
            "/absolute/file.txt",
            "",
        )

        for key in invalid:
            with self.subTest(
                key=key
            ):
                with self.assertRaises(
                    InvalidObjectKeyError
                ):
                    normalize_key(
                        key
                    )

    def test_default_backend_is_local(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            self.assertEqual(
                backend_name(),
                "local",
            )

    def test_local_roundtrip(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalObjectStorage(
                directory
            )

            result = storage.put_bytes(
                "users/test/input.docx",
                b"docurapi-test",
                content_type=(
                    "application/"
                    "vnd.openxmlformats-"
                    "officedocument."
                    "wordprocessingml.document"
                ),
            )

            self.assertEqual(
                result.key,
                "users/test/input.docx",
            )

            self.assertEqual(
                result.size,
                13,
            )

            self.assertTrue(
                storage.exists(
                    result.key
                )
            )

            self.assertEqual(
                storage.get_bytes(
                    result.key
                ),
                b"docurapi-test",
            )

            destination = (
                Path(directory)
                / "downloaded"
                / "input.docx"
            )

            downloaded = (
                storage.download_file(
                    result.key,
                    destination,
                )
            )

            self.assertEqual(
                downloaded.read_bytes(),
                b"docurapi-test",
            )

            self.assertTrue(
                storage.delete(
                    result.key
                )
            )

            self.assertFalse(
                storage.exists(
                    result.key
                )
            )

            self.assertFalse(
                storage.delete(
                    result.key
                )
            )

    def test_put_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = root / "source.txt"

            source.write_text(
                "DocuRapi",
                encoding="utf-8",
            )

            storage = LocalObjectStorage(
                root / "objects"
            )

            result = storage.put_file(
                source,
                "exports/result.txt",
            )

            self.assertEqual(
                result.size,
                len(
                    "DocuRapi".encode(
                        "utf-8"
                    )
                ),
            )

            self.assertEqual(
                storage.get_bytes(
                    result.key
                ),
                b"DocuRapi",
            )

    def test_missing_object(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = LocalObjectStorage(
                directory
            )

            with self.assertRaises(
                ObjectNotFoundError
            ):
                storage.get_bytes(
                    "missing.docx"
                )


if __name__ == "__main__":
    unittest.main()
