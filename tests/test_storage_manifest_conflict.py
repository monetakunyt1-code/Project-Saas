from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

from services.storage_manifest import (
    delete_mirror,
    get_mirror,
    record_mirror,
)


class StorageManifestConflictTest(
    unittest.TestCase,
):
    def test_object_reference_can_move_to_new_local_path(
        self,
    ) -> None:
        identifier = uuid.uuid4().hex

        reference = (
            "object://tests/manifest/"
            + identifier
            + "/result.docx"
        )

        key = (
            "tests/manifest/"
            + identifier
            + "/result.docx"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            first_path = (
                root
                / "first"
                / "result.docx"
            )

            second_path = (
                root
                / "second"
                / "result.docx"
            )

            first = record_mirror(
                local_path=first_path,
                object_reference=reference,
                object_key=key,
                field_name="output_path",
                module_name="test",
                backend="local",
                size=10,
            )

            self.assertEqual(
                first.local_path,
                str(first_path.resolve()),
            )

            second = record_mirror(
                local_path=second_path,
                object_reference=reference,
                object_key=key,
                field_name="output_path",
                module_name="test",
                backend="local",
                size=20,
            )

            self.assertEqual(
                second.local_path,
                str(second_path.resolve()),
            )

            self.assertEqual(
                second.object_reference,
                reference,
            )

            self.assertIsNone(
                get_mirror(
                    first_path
                )
            )

            current = get_mirror(
                second_path
            )

            self.assertIsNotNone(
                current
            )

            assert current is not None

            self.assertEqual(
                current.size,
                20,
            )

            self.assertTrue(
                delete_mirror(
                    second_path
                )
            )


if __name__ == "__main__":
    unittest.main()
