from __future__ import annotations

import hashlib
import tempfile
import uuid

from pathlib import Path

from services.object_storage import (
    create_object_storage,
)


def main() -> None:
    storage = create_object_storage(
        "vercel_blob"
    )

    probe_id = uuid.uuid4().hex

    key = (
        "system/probes/"
        f"python-adapter-{probe_id}.txt"
    )

    payload = (
        "DocuRapi Private Blob "
        f"Python Runtime Probe\n{probe_id}\n"
    ).encode(
        "utf-8"
    )

    expected = hashlib.sha256(
        payload
    ).hexdigest()

    uploaded = False

    try:
        result = storage.put_bytes(
            key,
            payload,
            content_type="text/plain",
        )

        uploaded = True

        print(
            "Blob upload:",
            "PASSED",
        )

        print(
            "Stored object:",
            type(result).__name__,
        )

        if not storage.exists(
            key
        ):
            raise RuntimeError(
                "Blob tidak ditemukan setelah upload."
            )

        print(
            "Blob exists:",
            "PASSED",
        )

        downloaded = (
            storage.get_bytes(
                key
            )
        )

        actual = hashlib.sha256(
            downloaded
        ).hexdigest()

        if actual != expected:
            raise RuntimeError(
                "Checksum download berbeda."
            )

        print(
            "Blob download:",
            "PASSED",
        )

        print(
            "Blob checksum:",
            "PASSED",
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = (
                Path(directory)
                / "probe.txt"
            )

            storage.download_file(
                key,
                destination,
            )

            if (
                destination.read_bytes()
                != payload
            ):
                raise RuntimeError(
                    "Downloaded file berbeda."
                )

        print(
            "Blob materialization:",
            "PASSED",
        )

    finally:
        if uploaded:
            deleted = storage.delete(
                key
            )

            if deleted is not True:
                raise RuntimeError(
                    "Delete tidak mengembalikan True."
                )

            print(
                "Blob cleanup:",
                "PASSED",
            )

    if storage.exists(
        key
    ):
        raise RuntimeError(
            "Probe Blob masih tersisa setelah delete."
        )

    print(
        "DOCURAPI_VERCEL_BLOB_RUNTIME_CHECK_PASSED"
    )


if __name__ == "__main__":
    main()
