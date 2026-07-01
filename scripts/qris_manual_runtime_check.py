from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.postgres_worker_queue import delete_job, enqueue_job, get_job, queue_health
from services.qris_manual_payments import (
    attach_proof,
    delete_payment,
    initialize_qris_schema,
    mark_rejected,
    prepare_payment,
    qris_health,
)
from services.storage_bridge import create_storage_bridge

TERMINAL = {"succeeded", "failed", "canceled", "timed_out"}


def wait_job(job_id: str, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        job = get_job(job_id)
        if job is None:
            raise RuntimeError("QRIS worker smoke job hilang.")
        status = str(job["status"])
        if status != previous:
            print("QRIS worker job:", status)
            previous = status
        if status in TERMINAL:
            return job
        time.sleep(1)
    raise TimeoutError("QRIS worker smoke job tidak selesai.")


def main() -> None:
    initialize_qris_schema()
    image = ROOT / "static/payment/qris-docurapi.png"
    if not image.is_file() or image.stat().st_size < 100_000:
        raise RuntimeError("Gambar QRIS belum terpasang dengan benar.")

    identifier = uuid.uuid4().hex
    order_id = "QRIS-SMOKE-" + identifier[:12]
    proof_reference = "object://smoke/proof-" + identifier + ".png"
    job_id = "qris-smoke-" + identifier[:24]
    artifact = ""

    try:
        payment = prepare_payment(
            order_id=order_id,
            user_id="smoke-user",
            buyer_email="smoke@example.com",
            amount="10000",
            product_code="SMOKE",
        )
        if payment["status"] != "prepared":
            raise RuntimeError("Prepare payment gagal.")

        submitted = attach_proof(
            order_id=order_id,
            user_id="smoke-user",
            proof_reference=proof_reference,
            proof_filename="proof.png",
            proof_content_type="image/png",
            proof_size=1234,
            payer_name="Smoke User",
            payment_note="Runtime check",
        )
        if submitted["status"] != "submitted":
            raise RuntimeError("Submit proof gagal.")

        rejected = mark_rejected(
            order_id=order_id,
            reviewer_id="smoke-admin",
            reason="Runtime rejection test",
        )
        if rejected["status"] != "rejected":
            raise RuntimeError("Reject payment gagal.")

        print("QRIS database health:", qris_health())

        worker_health = queue_health()
        if worker_health["active_workers"] < 1:
            raise RuntimeError("Background worker tidak aktif.")

        enqueue_job(
            "billing.qris_manual_post_approval",
            {
                "payment_id": payment["payment_id"],
                "order_id": order_id,
                "user_id": "smoke-user",
                "buyer_email": "smoke@example.com",
                "product_code": "SMOKE",
                "amount": "10000.00",
                "proof_reference": proof_reference,
                "reviewed_by": "smoke-admin",
                "merchant_name": "RUANG DEADLINE - STATIONERY",
            },
            priority=10,
            max_attempts=2,
            timeout_seconds=30,
            job_id=job_id,
        )

        job = wait_job(job_id)
        if job["status"] != "succeeded":
            raise RuntimeError("QRIS worker gagal: " + str(job.get("error_message")))

        artifact = str(job.get("artifact_reference") or "")
        if not artifact.startswith("object://"):
            raise RuntimeError("QRIS worker artifact bukan object reference.")

        bridge = create_storage_bridge()
        content = bridge.read_bytes(artifact)
        if b"qris_manual_payment_approved" not in content:
            raise RuntimeError("Isi QRIS worker artifact tidak sesuai.")

        print("QRIS_MANUAL_RUNTIME_CHECK_PASSED")

    finally:
        if artifact:
            try:
                create_storage_bridge().delete(artifact)
            except Exception:
                pass
        existing = get_job(job_id)
        if existing is not None and existing["status"] in TERMINAL:
            try:
                delete_job(job_id)
            except Exception:
                pass
        delete_payment(order_id)


if __name__ == "__main__":
    main()
