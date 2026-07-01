from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.responses import (
    FileResponse,
)

from services.object_aware_response import (
    ObjectAwareFileResponse,
)
from services.runtime_file_mirror import (
    mirror_local_file,
)
from services.storage_bridge import (
    create_storage_bridge,
)
from services.storage_manifest import (
    delete_mirror,
    get_mirror,
)


class ObjectStorageRuntimeTest(
    unittest.TestCase,
):
    def test_download_fallback_when_local_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            source = (
                root
                / "result.docx"
            )

            source.write_bytes(
                b"runtime-object-content"
            )

            environment = {
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

            with patch.dict(
                os.environ,
                environment,
                clear=False,
            ):
                record = mirror_local_file(
                    source,
                    field_name=
                        "output_path",
                    arguments={
                        "job_id":
                            "runtime-test",
                    },
                    module_name=
                        "database",
                )

                self.assertIsNotNone(
                    record
                )

                manifest = get_mirror(
                    source
                )

                self.assertIsNotNone(
                    manifest
                )

                source.unlink()

                response = (
                    ObjectAwareFileResponse(
                        source,
                        filename=
                            "hasil.docx",
                    )
                )

                self.assertIsInstance(
                    response,
                    FileResponse,
                )

                response_path = Path(
                    response.path
                )

                self.assertEqual(
                    response_path.read_bytes(),
                    b"runtime-object-content",
                )

                response_path.unlink(
                    missing_ok=True
                )

                assert record is not None

                bridge = (
                    create_storage_bridge()
                )

                bridge.delete(
                    record.object_reference
                )

                delete_mirror(
                    source
                )


if __name__ == "__main__":
    unittest.main()
