from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.responses import FileResponse

from services.object_storage import (
    LocalObjectStorage,
)
from services.storage_bridge import (
    HybridStorageBridge,
    StorageBridgeError,
    build_object_key,
    is_object_reference,
    object_key_from_reference,
    object_reference,
)


class StorageBridgeTest(
    unittest.TestCase,
):
    def test_object_reference_roundtrip(
        self,
    ) -> None:
        reference = object_reference(
            "jobs/test/result.docx"
        )

        self.assertTrue(
            is_object_reference(
                reference
            )
        )

        self.assertEqual(
            object_key_from_reference(
                reference
            ),
            "jobs/test/result.docx",
        )

    def test_local_value_is_not_object(
        self,
    ) -> None:
        self.assertFalse(
            is_object_reference(
                "storage/jobs/result.docx"
            )
        )

        with self.assertRaises(
            StorageBridgeError
        ):
            object_key_from_reference(
                "storage/jobs/result.docx"
            )

    def test_build_object_key(
        self,
    ) -> None:
        key = build_object_key(
            "job outputs",
            "../../Hasil Akhir.DOCX",
            user_id="user 01",
            workspace_id="workspace/utama",
            resource_id="job:123",
        )

        self.assertEqual(
            key,
            (
                "job-outputs/"
                "workspaces/workspace-utama/"
                "users/user-01/"
                "resources/job-123/"
                "Hasil-Akhir.docx"
            ),
        )

        self.assertNotIn(
            "..",
            key,
        )

    def test_dual_write_local_active(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = root / "result.docx"

            source.write_bytes(
                b"docurapi-result"
            )

            object_storage = (
                LocalObjectStorage(
                    root / "objects"
                )
            )

            bridge = HybridStorageBridge(
                object_storage,
                enabled=False,
                preserve_local=True,
                cache_root=root / "cache",
            )

            result = bridge.persist_file(
                source,
                "jobs/job-1/result.docx",
            )

            self.assertEqual(
                result.active_reference,
                str(source.resolve()),
            )

            self.assertTrue(
                source.exists()
            )

            self.assertTrue(
                object_storage.exists(
                    "jobs/job-1/result.docx"
                )
            )

            self.assertEqual(
                bridge.read_bytes(
                    result.active_reference
                ),
                b"docurapi-result",
            )

            self.assertEqual(
                bridge.read_bytes(
                    result.object_reference
                ),
                b"docurapi-result",
            )

    def test_object_reference_active(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = root / "output.pdf"

            source.write_bytes(
                b"pdf-content"
            )

            storage = LocalObjectStorage(
                root / "objects"
            )

            bridge = HybridStorageBridge(
                storage,
                enabled=True,
                preserve_local=True,
                cache_root=root / "cache",
            )

            result = bridge.persist_file(
                source,
                "reports/report-1/output.pdf",
            )

            self.assertTrue(
                is_object_reference(
                    result.active_reference
                )
            )

            self.assertTrue(
                source.exists()
            )

            with bridge.materialize(
                result.active_reference
            ) as materialized:
                self.assertTrue(
                    materialized.is_file()
                )

                self.assertEqual(
                    materialized.read_bytes(),
                    b"pdf-content",
                )

            self.assertFalse(
                materialized.exists()
            )

    def test_persist_bytes_with_local_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            storage = LocalObjectStorage(
                root / "objects"
            )

            bridge = HybridStorageBridge(
                storage,
                enabled=True,
                preserve_local=True,
                cache_root=root / "cache",
            )

            local_path = (
                root
                / "uploads"
                / "input.docx"
            )

            result = bridge.persist_bytes(
                b"uploaded-document",
                "uploads/input.docx",
                local_path=local_path,
            )

            self.assertTrue(
                is_object_reference(
                    result.active_reference
                )
            )

            self.assertEqual(
                local_path.read_bytes(),
                b"uploaded-document",
            )

            self.assertEqual(
                bridge.read_bytes(
                    result.object_reference
                ),
                b"uploaded-document",
            )

    def test_local_object_download_response(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            storage = LocalObjectStorage(
                root / "objects"
            )

            bridge = HybridStorageBridge(
                storage,
                enabled=True,
                preserve_local=True,
                cache_root=root / "cache",
            )

            result = bridge.persist_bytes(
                b"download-result",
                "downloads/result.docx",
            )

            response = (
                bridge.build_download_response(
                    result.object_reference,
                    filename="hasil.docx",
                )
            )

            self.assertIsInstance(
                response,
                FileResponse,
            )

            response_path = Path(
                response.path
            )

            self.assertTrue(
                response_path.is_file()
            )

            self.assertEqual(
                response_path.read_bytes(),
                b"download-result",
            )

            response_path.unlink(
                missing_ok=True
            )


if __name__ == "__main__":
    unittest.main()
