from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


import background_database  # noqa: E402
import database  # noqa: E402
import notification_database  # noqa: E402

from services.runtime_file_mirror import (  # noqa: E402
    mirror_enabled,
    mirror_local_file,
)
from services.storage_bridge import (  # noqa: E402
    runtime_enabled,
)


def wrapped_functions(
    module: object,
) -> tuple[str, ...]:
    return tuple(
        getattr(
            module,
            (
                "_DOCURAPI_STORAGE_"
                "MIRRORED_FUNCTIONS"
            ),
            (),
        )
    )


def main() -> None:
    print()
    print("=" * 72)
    print("DOCURAPI RUNTIME FILE MIRROR CHECK")
    print("=" * 72)

    modules = (
        (
            "database",
            database,
        ),
        (
            "background_database",
            background_database,
        ),
        (
            "notification_database",
            notification_database,
        ),
    )

    total_wrapped = 0

    for name, module in modules:
        functions = wrapped_functions(
            module
        )

        total_wrapped += len(
            functions
        )

        print(
            f"{name:26}:",
            len(functions),
        )

        print(
            "  "
            + (
                ", ".join(
                    functions
                )
                if functions
                else "-"
            )
        )

    if total_wrapped < 3:
        raise RuntimeError(
            "Fungsi database yang terintegrasi "
            f"hanya {total_wrapped}."
        )

    print(
        "Mirror enabled :",
        mirror_enabled(),
    )

    print(
        "Object runtime :",
        runtime_enabled(),
    )

    if not mirror_enabled():
        raise RuntimeError(
            "Runtime mirror tidak aktif."
        )

    if runtime_enabled():
        raise RuntimeError(
            "object:// belum boleh menjadi "
            "referensi aktif pada Phase 3D."
        )

    payload = (
        b"DOCURAPI_RUNTIME_MIRROR_CHECK"
    )

    expected_hash = hashlib.sha256(
        payload
    ).hexdigest()

    with tempfile.TemporaryDirectory() as directory:
        source = (
            Path(directory)
            / "result.docx"
        )

        source.write_bytes(
            payload
        )

        record = mirror_local_file(
            source,
            field_name=
                "output_path",
            arguments={
                "job_id":
                    "phase3d-check",
                "user_id":
                    "system",
                "workspace_id":
                    "system",
            },
            module_name=
                "database",
        )

        if record is None:
            raise RuntimeError(
                "File probe tidak dimirror."
            )

        object_root = Path(
            os.environ[
                (
                    "DOCURAPI_OBJECT_"
                    "STORAGE_LOCAL_ROOT"
                )
            ]
        )

        object_path = (
            object_root
            / Path(
                *record.object_key.split(
                    "/"
                )
            )
        )

        if not object_path.is_file():
            raise RuntimeError(
                "Object hasil mirror tidak ditemukan."
            )

        actual_hash = hashlib.sha256(
            object_path.read_bytes()
        ).hexdigest()

        print(
            "Object key    :",
            record.object_key,
        )

        print(
            "Local retained:",
            source.is_file(),
        )

        print(
            "Expected hash :",
            expected_hash,
        )

        print(
            "Actual hash   :",
            actual_hash,
        )

        if expected_hash != actual_hash:
            raise RuntimeError(
                "Checksum mirror berbeda."
            )

        if not source.is_file():
            raise RuntimeError(
                "File lokal terhapus."
            )

    print()
    print(
        "RUNTIME_FILE_MIRROR_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
