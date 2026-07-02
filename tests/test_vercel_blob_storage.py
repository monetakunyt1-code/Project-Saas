from __future__ import annotations

import json
import os
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch
from urllib import error as urllib_error


class FakeResponse:
    def __init__(
        self,
        data: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._data = data
        self.status = status
        self.headers = (
            headers
            or {}
        )

    def read(
        self,
    ) -> bytes:
        return self._data

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        *_args,
    ) -> None:
        return None


class VercelBlobStorageTest(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "BLOB_STORE_ID":
                    "store_test123",

                "BLOB_READ_WRITE_TOKEN":
                    "vercel_blob_rw_test123_secret",

                "VERCEL_OIDC_TOKEN":
                    "",
            },
            clear=False,
        )

        self.environment.start()

        self.payload = (
            b"DocuRapi Vercel Blob Test"
        )

        self.object_exists = True

    def tearDown(
        self,
    ) -> None:
        self.environment.stop()

    def fake_urlopen(
        self,
        request,
        timeout=None,
    ):
        del timeout

        method = request.get_method()
        url = request.full_url

        if (
            method == "PUT"
            and "/api/blob/" in url
        ):
            response = {
                "url": (
                    "https://test123.private."
                    "blob.vercel-storage.com/"
                    "tests/blob.txt"
                ),

                "downloadUrl": (
                    "https://test123.private."
                    "blob.vercel-storage.com/"
                    "tests/blob.txt?download=1"
                ),

                "pathname":
                    "tests/blob.txt",

                "contentType":
                    "text/plain",

                "contentDisposition":
                    "attachment",

                "etag":
                    "test-etag",
            }

            self.object_exists = True

            return FakeResponse(
                json.dumps(
                    response
                ).encode(
                    "utf-8"
                )
            )

        if (
            method == "GET"
            and "/api/blob?url=" in url
        ):
            if not self.object_exists:
                raise urllib_error.HTTPError(
                    url,
                    404,
                    "Not Found",
                    {},
                    None,
                )

            metadata = {
                "url": (
                    "https://test123.private."
                    "blob.vercel-storage.com/"
                    "tests/blob.txt"
                ),

                "downloadUrl":
                    "",

                "pathname":
                    "tests/blob.txt",

                "size":
                    len(
                        self.payload
                    ),

                "contentType":
                    "text/plain",

                "contentDisposition":
                    "attachment",

                "cacheControl":
                    "public, max-age=60",

                "uploadedAt":
                    "2026-07-02T00:00:00Z",

                "etag":
                    "test-etag",
            }

            return FakeResponse(
                json.dumps(
                    metadata
                ).encode(
                    "utf-8"
                )
            )

        if (
            method == "GET"
            and ".private.blob."
            in url
        ):
            if not self.object_exists:
                raise urllib_error.HTTPError(
                    url,
                    404,
                    "Not Found",
                    {},
                    None,
                )

            return FakeResponse(
                self.payload,
                headers={
                    "content-type":
                        "text/plain",
                },
            )

        if (
            method == "POST"
            and url.endswith(
                "/api/blob/delete"
            )
        ):
            self.object_exists = False

            return FakeResponse(
                b"{}"
            )

        raise AssertionError(
            f"Unexpected request: {method} {url}"
        )

    @patch(
        "services.vercel_blob_storage."
        "urllib_request.urlopen"
    )
    def test_private_blob_roundtrip(
        self,
        mocked_urlopen,
    ) -> None:
        mocked_urlopen.side_effect = (
            self.fake_urlopen
        )

        from services.object_storage import (
            create_object_storage,
        )

        storage = create_object_storage(
            "vercel_blob"
        )

        stored = storage.put_bytes(
            "tests/blob.txt",
            self.payload,
            content_type="text/plain",
        )

        self.assertIsNotNone(
            stored
        )

        self.assertTrue(
            storage.exists(
                "tests/blob.txt"
            )
        )

        self.assertEqual(
            storage.get_bytes(
                "tests/blob.txt"
            ),
            self.payload,
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = (
                Path(directory)
                / "downloaded.txt"
            )

            result = storage.download_file(
                "tests/blob.txt",
                destination,
            )

            self.assertEqual(
                Path(result).read_bytes(),
                self.payload,
            )

        private_url = (
            storage.presigned_get_url(
                "tests/blob.txt"
            )
        )

        self.assertIn(
            ".private.blob."
            "vercel-storage.com",
            private_url,
        )

        deleted = storage.delete(
            "tests/blob.txt"
        )

        self.assertTrue(
            deleted
        )

        self.assertFalse(
            storage.exists(
                "tests/blob.txt"
            )
        )

    def test_factory_aliases(
        self,
    ) -> None:
        from services.object_storage import (
            create_object_storage,
        )

        for backend in (
            "vercel",
            "vercel_blob",
            "vercel-blob",
            "blob",
        ):
            storage = (
                create_object_storage(
                    backend
                )
            )

            self.assertEqual(
                storage.backend,
                "vercel_blob",
            )


if __name__ == "__main__":
    unittest.main()
