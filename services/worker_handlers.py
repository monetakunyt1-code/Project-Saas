"""Handler job yang dapat dijalankan DocuRapi worker."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from services.storage_bridge import (
    build_object_key,
    create_storage_bridge,
)


class UnknownWorkerJobTypeError(
    RuntimeError
):
    """Tipe job tidak terdaftar."""


class InvalidWorkerPayloadError(
    RuntimeError
):
    """Payload job tidak valid."""


WorkerHandler = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


def _payload_dict(
    payload: Mapping[
        str,
        Any,
    ] | None,
) -> dict[str, Any]:
    if payload is None:
        return {}

    if not isinstance(
        payload,
        Mapping,
    ):
        raise InvalidWorkerPayloadError(
            "Payload worker harus berupa object."
        )

    return dict(payload)


def handle_system_noop(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "echo": payload,
    }


def handle_system_sleep(
    payload: dict[str, Any],
) -> dict[str, Any]:
    seconds = float(
        payload.get(
            "seconds",
            1,
        )
    )

    if seconds < 0:
        raise InvalidWorkerPayloadError(
            "seconds tidak boleh negatif."
        )

    seconds = min(
        seconds,
        3600,
    )

    time.sleep(
        seconds
    )

    return {
        "ok": True,
        "slept_seconds":
            seconds,
    }


def handle_storage_write_text(
    payload: dict[str, Any],
) -> dict[str, Any]:
    text = str(
        payload.get(
            "text",
            "",
        )
    )

    filename = Path(
        str(
            payload.get(
                "filename",
                "worker-result.txt",
            )
        ).replace(
            "\\",
            "/",
        )
    ).name

    if not filename:
        filename = (
            "worker-result.txt"
        )

    category = str(
        payload.get(
            "category",
            "worker-artifacts",
        )
    )

    job_id = str(
        payload.get(
            "_job_id",
            payload.get(
                "job_id",
                "worker-job",
            ),
        )
    )

    workspace_id = (
        str(
            payload["workspace_id"]
        )
        if payload.get(
            "workspace_id"
        )
        else None
    )

    user_id = (
        str(
            payload["user_id"]
        )
        if payload.get(
            "user_id"
        )
        else None
    )

    data = text.encode(
        "utf-8"
    )

    key = build_object_key(
        category,
        filename,
        user_id=user_id,
        workspace_id=
            workspace_id,
        resource_id=job_id,
    )

    bridge = create_storage_bridge(
        enabled=True,
        preserve_local=False,
    )

    stored = bridge.persist_bytes(
        data,
        key,
        content_type=(
            "text/plain; charset=utf-8"
        ),
        activate=True,
    )

    return {
        "ok": True,

        "artifact_reference":
            stored.object_reference,

        "artifact_filename":
            filename,

        "object_key":
            stored.object_key,

        "size":
            stored.size,

        "sha256":
            hashlib.sha256(
                data
            ).hexdigest(),
    }


def handle_storage_copy(
    payload: dict[str, Any],
) -> dict[str, Any]:
    source_reference = str(
        payload.get(
            "source_reference",
            "",
        )
    ).strip()

    if not source_reference:
        raise InvalidWorkerPayloadError(
            "source_reference diperlukan."
        )

    filename = Path(
        str(
            payload.get(
                "filename",
                Path(
                    source_reference
                ).name
                or "artifact.bin",
            )
        ).replace(
            "\\",
            "/",
        )
    ).name

    job_id = str(
        payload.get(
            "_job_id",
            "worker-copy",
        )
    )

    bridge = create_storage_bridge(
        enabled=True,
        preserve_local=False,
    )

    data = bridge.read_bytes(
        source_reference
    )

    key = build_object_key(
        "worker-copies",
        filename,
        resource_id=job_id,
    )

    stored = bridge.persist_bytes(
        data,
        key,
        activate=True,
    )

    return {
        "ok": True,

        "artifact_reference":
            stored.object_reference,

        "artifact_filename":
            filename,

        "object_key":
            stored.object_key,

        "size":
            stored.size,

        "sha256":
            hashlib.sha256(
                data
            ).hexdigest(),
    }


HANDLERS: dict[
    str,
    WorkerHandler,
] = {
    "system.noop":
        handle_system_noop,

    "system.sleep":
        handle_system_sleep,

    "storage.write_text":
        handle_storage_write_text,

    "storage.copy":
        handle_storage_copy,
}


def supported_job_types() -> tuple[str, ...]:
    return tuple(
        sorted(
            HANDLERS
        )
    )


def execute_job(
    job_type: str,
    payload: Mapping[
        str,
        Any,
    ] | None,
) -> dict[str, Any]:
    normalized_type = str(
        job_type
    ).strip()

    handler = HANDLERS.get(
        normalized_type
    )

    if handler is None:
        raise UnknownWorkerJobTypeError(
            "Tipe job tidak didukung: "
            f"{normalized_type}"
        )

    return handler(
        _payload_dict(
            payload
        )
    )


# DOCURAPI_QRIS_MANUAL_POST_APPROVAL_HANDLER
def handle_qris_manual_post_approval(
    payload: dict[str, Any],
) -> dict[str, Any]:
    import hashlib
    import json
    import re

    from services.storage_bridge import build_object_key, create_storage_bridge

    order_id = str(payload.get("order_id", "unknown-order"))
    safe_order = re.sub(r"[^A-Za-z0-9._-]+", "-", order_id).strip("-") or "unknown-order"
    document = {
        "event": "qris_manual_payment_approved",
        "payment_id": payload.get("payment_id"),
        "order_id": order_id,
        "user_id": payload.get("user_id"),
        "buyer_email": payload.get("buyer_email"),
        "product_code": payload.get("product_code"),
        "amount": payload.get("amount"),
        "proof_reference": payload.get("proof_reference"),
        "reviewed_by": payload.get("reviewed_by"),
        "merchant_name": payload.get("merchant_name"),
    }
    content = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    filename = safe_order + "-qris-approved.json"
    key = build_object_key(
        "payment-events",
        filename,
        resource_id=str(payload.get("payment_id") or safe_order),
    )
    bridge = create_storage_bridge(enabled=True, preserve_local=False)
    stored = bridge.persist_bytes(
        content,
        key,
        content_type="application/json; charset=utf-8",
        activate=True,
    )
    return {
        "ok": True,
        "event": "qris_manual_payment_approved",
        "order_id": order_id,
        "artifact_reference": stored.object_reference,
        "artifact_filename": filename,
        "object_key": stored.object_key,
        "size": stored.size,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


HANDLERS["billing.qris_manual_post_approval"] = handle_qris_manual_post_approval
