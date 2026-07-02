from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[1]


PROBE = r'''
from pathlib import Path
import config


project_storage = (
    Path(config.__file__)
    .resolve()
    .parent
    / "storage"
).resolve()


def collect_paths(value):
    if isinstance(value, Path):
        return [value]

    if type(value) in {
        list,
        tuple,
        set,
    }:
        result = []

        for item in value:
            result.extend(
                collect_paths(item)
            )

        return result

    if type(value) is dict:
        result = []

        for key, item in value.items():
            result.extend(
                collect_paths(key)
            )

            result.extend(
                collect_paths(item)
            )

        return result

    return []


invalid = []

for name, value in vars(config).items():
    if name.startswith(
        "_docurapi_"
    ):
        continue

    for path in collect_paths(value):
        if not path.is_absolute():
            continue

        try:
            path.resolve().relative_to(
                project_storage
            )

        except ValueError:
            continue

        invalid.append(
            f"{name}={path}"
        )


if invalid:
    raise RuntimeError(
        "Path storage masih mengarah ke source "
        "read-only: "
        + ", ".join(invalid)
    )


remapped = getattr(
    config,
    "_docurapi_remapped_path_names",
    [],
)

if not remapped:
    raise RuntimeError(
        "Tidak ada path config yang dipindahkan "
        "ke runtime storage."
    )


runtime_storage = getattr(
    config,
    "_docurapi_runtime_storage_root",
)

if not runtime_storage.is_dir():
    raise RuntimeError(
        "Runtime storage belum dibuat."
    )


print(
    "Remapped config names:",
    sorted(remapped),
)

print(
    "Runtime storage:",
    runtime_storage,
)

print(
    "VERCEL_RUNTIME_PATH_PROBE_PASSED"
)
'''


class VercelRuntimePathTest(
    unittest.TestCase
):
    def test_vercel_storage_uses_tmp(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime_root = (
                Path(directory)
                / "docurapi-runtime"
            )

            environment = os.environ.copy()

            environment.update(
                {
                    "VERCEL":
                        "1",

                    "VERCEL_ENV":
                        "production",

                    "DOCURAPI_RUNTIME_ROOT":
                        str(runtime_root),
                }
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    PROBE,
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                0,
                result.stdout,
            )

            self.assertIn(
                "VERCEL_RUNTIME_PATH_PROBE_PASSED",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
