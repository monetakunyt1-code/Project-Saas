from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.runtime_file_mirror import (
    install_module_file_mirroring,
    mirror_local_file,
)
from services.storage_bridge import (
    is_object_reference,
)


class RuntimeFileMirrorTest(
    unittest.TestCase,
):
    def _environment(
        self,
        root: Path,
    ) -> dict[str, str]:
        return {
            "DOCURAPI_OBJECT_STORAGE_BACKEND":
                "local",

            "DOCURAPI_OBJECT_STORAGE_LOCAL_ROOT":
                str(
                    root / "objects"
                ),

            "DOCURAPI_OBJECT_STORAGE_CACHE_ROOT":
                str(
                    root / "cache"
                ),

            "DOCURAPI_OBJECT_STORAGE_RUNTIME_ENABLED":
                "false",

            "DOCURAPI_OBJECT_STORAGE_KEEP_LOCAL_COPY":
                "true",

            "DOCURAPI_OBJECT_STORAGE_MIRROR_ENABLED":
                "true",

            "DOCURAPI_OBJECT_STORAGE_MIRROR_REQUIRED":
                "true",
        }

    def test_mirror_preserves_local_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = (
                root
                / "hasil.docx"
            )

            source.write_bytes(
                b"docurapi-result"
            )

            with patch.dict(
                os.environ,
                self._environment(
                    root
                ),
                clear=False,
            ):
                record = mirror_local_file(
                    source,
                    field_name=
                        "output_path",
                    arguments={
                        "job_id":
                            "job-001",
                        "user_id":
                            "user-001",
                        "workspace_id":
                            "workspace-001",
                    },
                    module_name=
                        "database",
                )

            self.assertIsNotNone(
                record
            )

            assert record is not None

            self.assertTrue(
                source.is_file()
            )

            self.assertTrue(
                is_object_reference(
                    record.object_reference
                )
            )

            object_path = (
                root
                / "objects"
                / Path(
                    *record.object_key.split(
                        "/"
                    )
                )
            )

            self.assertTrue(
                object_path.is_file()
            )

            self.assertEqual(
                object_path.read_bytes(),
                b"docurapi-result",
            )

    def test_nonexistent_file_is_skipped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            with patch.dict(
                os.environ,
                self._environment(
                    root
                ),
                clear=False,
            ):
                record = mirror_local_file(
                    root / "missing.docx",
                    field_name=
                        "output_path",
                    arguments={
                        "job_id":
                            "job-missing",
                    },
                    module_name=
                        "database",
                )

            self.assertIsNone(
                record
            )

    def test_object_reference_is_skipped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            with patch.dict(
                os.environ,
                self._environment(
                    root
                ),
                clear=False,
            ):
                record = mirror_local_file(
                    (
                        "object://jobs/"
                        "result.docx"
                    ),
                    field_name=
                        "output_path",
                    module_name=
                        "database",
                )

            self.assertIsNone(
                record
            )

    def test_module_function_wrapper(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = (
                root
                / "template.docx"
            )

            source.write_bytes(
                b"template-content"
            )

            def save_template(
                template_id: str,
                file_path: str,
            ) -> str:
                del template_id
                return file_path

            save_template.__module__ = (
                "fake_database"
            )

            namespace = {
                "save_template":
                    save_template,
            }

            with patch.dict(
                os.environ,
                self._environment(
                    root
                ),
                clear=False,
            ):
                wrapped = (
                    install_module_file_mirroring(
                        namespace,
                        module_name=
                            "fake_database",
                    )
                )

                result = namespace[
                    "save_template"
                ](
                    "template-001",
                    str(source),
                )

            self.assertIn(
                "save_template",
                wrapped,
            )

            self.assertEqual(
                result,
                str(source),
            )

            self.assertTrue(
                getattr(
                    namespace[
                        "save_template"
                    ],
                    (
                        "__docurapi_"
                        "storage_mirror__"
                    ),
                    False,
                )
            )

            mirrored_files = [
                path
                for path in (
                    root / "objects"
                ).rglob("*")
                if path.is_file()
            ]

            self.assertEqual(
                len(mirrored_files),
                1,
            )

            self.assertEqual(
                mirrored_files[
                    0
                ].read_bytes(),
                b"template-content",
            )


if __name__ == "__main__":
    unittest.main()
