from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.postgres_worker_queue import (
    calculate_retry_delay,
    normalize_postgres_url,
)

from services.storage_bridge import (
    create_storage_bridge,
)

from services.worker_handlers import (
    UnknownWorkerJobTypeError,
    execute_job,
    supported_job_types,
)


class PostgresWorkerQueueTest(
    unittest.TestCase,
):
    def test_normalize_postgres_url(
        self,
    ) -> None:
        self.assertEqual(
            normalize_postgres_url(
                (
                    "postgresql+psycopg://"
                    "user:pass@localhost/db"
                )
            ),
            (
                "postgresql://"
                "user:pass@localhost/db"
            ),
        )

    def test_retry_backoff(
        self,
    ) -> None:
        self.assertEqual(
            calculate_retry_delay(1),
            5,
        )

        self.assertEqual(
            calculate_retry_delay(2),
            10,
        )

        self.assertEqual(
            calculate_retry_delay(3),
            20,
        )

        self.assertEqual(
            calculate_retry_delay(20),
            300,
        )

    def test_noop_handler(
        self,
    ) -> None:
        result = execute_job(
            "system.noop",
            {
                "message":
                    "hello",
            },
        )

        self.assertTrue(
            result["ok"]
        )

        self.assertEqual(
            result["echo"][
                "message"
            ],
            "hello",
        )

    def test_unknown_handler(
        self,
    ) -> None:
        with self.assertRaises(
            UnknownWorkerJobTypeError
        ):
            execute_job(
                "unknown.handler",
                {},
            )

    def test_storage_artifact_handler(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
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

                "DOCURAPI_OBJECT_STORAGE_KEEP_LOCAL_COPY":
                    "false",
            }

            with patch.dict(
                os.environ,
                environment,
                clear=False,
            ):
                result = execute_job(
                    "storage.write_text",
                    {
                        "_job_id":
                            "test-job",

                        "filename":
                            "result.txt",

                        "text":
                            "DocuRapi Worker",
                    },
                )

                self.assertTrue(
                    result[
                        "artifact_reference"
                    ].startswith(
                        "object://"
                    )
                )

                bridge = (
                    create_storage_bridge()
                )

                content = bridge.read_bytes(
                    result[
                        "artifact_reference"
                    ]
                )

                self.assertEqual(
                    content,
                    b"DocuRapi Worker",
                )

    def test_supported_job_types(
        self,
    ) -> None:
        types = (
            supported_job_types()
        )

        self.assertIn(
            "system.noop",
            types,
        )

        self.assertIn(
            "storage.write_text",
            types,
        )


if __name__ == "__main__":
    unittest.main()
