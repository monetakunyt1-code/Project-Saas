from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from services.object_storage import (  # noqa: E402
    backend_name,
    create_object_storage,
)


def main() -> None:
    print()
    print("=" * 68)
    print("DOCURAPI OBJECT STORAGE CHECK")
    print("=" * 68)

    storage = create_object_storage()

    print(
        "Backend:",
        backend_name(),
    )

    key = (
        "system/probes/"
        + uuid.uuid4().hex
        + ".bin"
    )

    payload = (
        b"DOCURAPI_OBJECT_STORAGE_PROBE"
    )

    expected_hash = hashlib.sha256(
        payload
    ).hexdigest()

    result = storage.put_bytes(
        key,
        payload,
        content_type=(
            "application/octet-stream"
        ),
        metadata={
            "purpose":
                "runtime-check",
        },
    )

    print(
        "Stored key :",
        result.key,
    )

    print(
        "Stored size:",
        result.size,
    )

    if not storage.exists(
        key
    ):
        raise RuntimeError(
            "Object tidak terdeteksi setelah disimpan."
        )

    downloaded = storage.get_bytes(
        key
    )

    actual_hash = hashlib.sha256(
        downloaded
    ).hexdigest()

    print(
        "Expected hash:",
        expected_hash,
    )

    print(
        "Actual hash  :",
        actual_hash,
    )

    if expected_hash != actual_hash:
        raise RuntimeError(
            "Checksum object tidak sama."
        )

    url = storage.presigned_get_url(
        key,
        expires_in=300,
    )

    if not url:
        raise RuntimeError(
            "URL object tidak tersedia."
        )

    print(
        "URL type:",
        url.split(
            ":",
            1,
        )[0],
    )

    if not storage.delete(
        key
    ):
        raise RuntimeError(
            "Object probe gagal dihapus."
        )

    if storage.exists(
        key
    ):
        raise RuntimeError(
            "Object masih tersedia setelah dihapus."
        )

    print()
    print(
        "OBJECT_STORAGE_ROUNDTRIP_PASSED"
    )


if __name__ == "__main__":
    main()
