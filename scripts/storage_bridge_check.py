from __future__ import annotations

import hashlib
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


from services.storage_bridge import (  # noqa: E402
    build_object_key,
    create_storage_bridge,
    is_object_reference,
)


def main() -> None:
    print()
    print("=" * 72)
    print("DOCURAPI HYBRID STORAGE BRIDGE CHECK")
    print("=" * 72)

    bridge = create_storage_bridge(
        enabled=True,
        preserve_local=True,
    )

    resource_id = uuid.uuid4().hex

    key = build_object_key(
        "runtime-probes",
        "document.docx",
        user_id="system",
        workspace_id="system",
        resource_id=resource_id,
    )

    payload = (
        b"DOCURAPI_HYBRID_STORAGE_BRIDGE"
    )

    expected_hash = hashlib.sha256(
        payload
    ).hexdigest()

    with tempfile.TemporaryDirectory() as directory:
        local_path = (
            Path(directory)
            / "document.docx"
        )

        local_path.write_bytes(
            payload
        )

        result = bridge.persist_file(
            local_path,
            key,
        )

        print(
            "Backend          :",
            result.backend,
        )

        print(
            "Object key       :",
            result.object_key,
        )

        print(
            "Active reference :",
            result.active_reference,
        )

        print(
            "Local preserved  :",
            local_path.exists(),
        )

        if not is_object_reference(
            result.active_reference
        ):
            raise RuntimeError(
                "Runtime bridge tidak menghasilkan "
                "object reference."
            )

        if not local_path.exists():
            raise RuntimeError(
                "Salinan lokal tidak dipertahankan."
            )

        object_payload = bridge.read_bytes(
            result.object_reference
        )

        actual_hash = hashlib.sha256(
            object_payload
        ).hexdigest()

        print(
            "Expected hash    :",
            expected_hash,
        )

        print(
            "Actual hash      :",
            actual_hash,
        )

        if expected_hash != actual_hash:
            raise RuntimeError(
                "Checksum object berbeda."
            )

        with bridge.materialize(
            result.object_reference
        ) as materialized:
            if not materialized.is_file():
                raise RuntimeError(
                    "Object tidak dapat dimaterialisasi."
                )

            materialized_hash = (
                hashlib.sha256(
                    materialized.read_bytes()
                ).hexdigest()
            )

            if (
                materialized_hash
                != expected_hash
            ):
                raise RuntimeError(
                    "Checksum hasil materialisasi berbeda."
                )

        if not bridge.delete(
            result.object_reference
        ):
            raise RuntimeError(
                "Object probe gagal dihapus."
            )

        if bridge.exists(
            result.object_reference
        ):
            raise RuntimeError(
                "Object probe masih tersedia."
            )

        if not local_path.exists():
            raise RuntimeError(
                "Penghapusan object ikut "
                "menghapus salinan lokal."
            )

    print()
    print(
        "HYBRID_STORAGE_BRIDGE_ROUNDTRIP_PASSED"
    )


if __name__ == "__main__":
    main()
