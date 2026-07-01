from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services.object_aware_response import (  # noqa: E402
    ObjectAwareFileResponse,
)
from services.runtime_file_mirror import (  # noqa: E402
    mirror_local_file,
)
from services.storage_bridge import (  # noqa: E402
    create_storage_bridge,
)
from services.storage_manifest import (  # noqa: E402
    delete_mirror,
    get_mirror,
    storage_statistics,
)


def main() -> None:
    print()
    print("=" * 72)
    print("DOCURAPI OBJECT STORAGE RUNTIME CHECK")
    print("=" * 72)

    identifier = uuid.uuid4().hex

    with tempfile.TemporaryDirectory() as directory:
        source = (
            Path(directory)
            / "runtime-result.docx"
        )

        payload = (
            b"DOCURAPI_OBJECT_STORAGE_RUNTIME"
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
                    identifier,
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
                "Runtime file tidak dimirror."
            )

        manifest = get_mirror(
            source
        )

        if manifest is None:
            raise RuntimeError(
                "Manifest tidak tercatat."
            )

        print(
            "Local path      :",
            manifest.local_path,
        )

        print(
            "Object reference:",
            manifest.object_reference,
        )

        source.unlink()

        response = (
            ObjectAwareFileResponse(
                source,
                filename=
                    "hasil.docx",
            )
        )

        response_path = Path(
            response.path
        )

        if not response_path.is_file():
            raise RuntimeError(
                "Fallback download tidak menghasilkan file."
            )

        if response_path.read_bytes() != payload:
            raise RuntimeError(
                "Isi fallback download berbeda."
            )

        print(
            "Fallback download:",
            "PASSED",
        )

        response_path.unlink(
            missing_ok=True
        )

        bridge = create_storage_bridge()

        bridge.delete(
            record.object_reference
        )

        delete_mirror(
            source
        )

    statistics = storage_statistics()

    print(
        "Manifest objects:",
        statistics["object_count"],
    )

    print(
        "Manifest bytes  :",
        statistics["total_bytes"],
    )

    print()
    print(
        "OBJECT_STORAGE_RUNTIME_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
