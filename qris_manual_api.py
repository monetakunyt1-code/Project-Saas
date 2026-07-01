"""Manual QRIS payment flow for DocuRapi."""

from __future__ import annotations

import html
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from services.postgres_worker_queue import enqueue_job, get_job
from services.qris_manual_payments import (
    QrisPaymentError,
    QrisPaymentNotFoundError,
    attach_proof,
    detect_proof_type,
    get_payment_by_order,
    list_payments,
    mark_approved,
    mark_rejected,
    prepare_payment,
    qris_health,
)
from services.storage_bridge import build_object_key, create_storage_bridge


router = APIRouter(tags=["QRIS Manual Payment"])
MERCHANT_NAME = "RUANG DEADLINE - STATIONERY"
QRIS_IMAGE_URL = "/static/payment/qris-docurapi.png"
MAX_PROOF_BYTES = int(os.environ.get("DOCURAPI_QRIS_MAX_PROOF_BYTES", str(8 * 1024 * 1024)))


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ApprovalRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"raw": response.text[:2000]}


def _forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name in ("cookie", "authorization", "x-csrf-token", "x-requested-with", "user-agent"):
        value = request.headers.get(name)
        if value:
            headers[name] = value
    return headers


async def _internal_request(
    request: Request,
    method: str,
    path: str,
    *,
    json_body: Mapping[str, Any] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://docurapi.internal",
        follow_redirects=False,
        timeout=30.0,
    ) as client:
        return await client.request(
            method,
            path,
            headers=_forward_headers(request),
            json=(dict(json_body) if json_body is not None else None),
        )


def _recursive_value(value: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] not in (None, ""):
                return value[key]
        for nested in value.values():
            result = _recursive_value(nested, keys)
            if result not in (None, ""):
                return result
    elif isinstance(value, list):
        for nested in value:
            result = _recursive_value(nested, keys)
            if result not in (None, ""):
                return result
    return None


def _identity(payload: Any) -> dict[str, str]:
    candidate = payload.get("user") if isinstance(payload, dict) and isinstance(payload.get("user"), dict) else payload
    if not isinstance(candidate, dict):
        raise HTTPException(status_code=401, detail="Sesi pengguna tidak valid.")

    user_id = _recursive_value(candidate, ("user_id", "id", "uuid", "account_id"))
    email = _recursive_value(candidate, ("email", "user_email"))
    name = _recursive_value(candidate, ("name", "full_name", "username"))
    if user_id in (None, ""):
        raise HTTPException(status_code=401, detail="Identitas pengguna tidak tersedia.")
    return {
        "user_id": str(user_id),
        "email": str(email or ""),
        "name": str(name or email or user_id),
    }


async def _require_user(request: Request) -> dict[str, str]:
    response = await _internal_request(request, "GET", "/api/auth/me")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    return _identity(_safe_json(response))


async def _require_admin(request: Request) -> dict[str, str]:
    user = await _require_user(request)
    response = await _internal_request(request, "GET", "/api/admin/users")
    if response.status_code != 200:
        raise HTTPException(status_code=403, detail="Akses admin diperlukan.")
    return user


async def _fetch_order(request: Request, order_id: str) -> dict[str, Any]:
    response = await _internal_request(request, "GET", "/api/billing/orders/" + str(order_id))
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Order billing tidak ditemukan.")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Order billing tidak dapat dibaca.")

    payload = _safe_json(response)
    order = dict(payload["order"]) if isinstance(payload, dict) and isinstance(payload.get("order"), dict) else payload
    if not isinstance(order, dict):
        raise HTTPException(status_code=502, detail="Format order billing tidak valid.")

    amount_value = _recursive_value(
        order,
        ("gross_amount", "total_amount", "final_amount", "amount", "total", "price"),
    )
    try:
        amount = Decimal(str(amount_value))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Nominal order billing tidak ditemukan.") from exc
    if amount <= 0:
        raise HTTPException(status_code=409, detail="Nominal order tidak valid.")

    product_code = _recursive_value(order, ("product_code", "plan_code", "package_code", "sku", "code"))
    return {"amount": str(amount), "product_code": str(product_code or ""), "raw": order}


def _ensure_owner(payment: Mapping[str, Any], user_id: str) -> None:
    if str(payment.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="Order dimiliki pengguna lain.")


def _public_payment(payment: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(payment)
    result.pop("activation_response", None)
    return result


async def _activate_existing_billing_order(request: Request, order_id: str, note: str | None) -> dict[str, Any]:
    path = f"/api/billing/orders/{order_id}/simulate-pay"
    response = await _internal_request(
        request,
        "POST",
        path,
        json_body={"source": "qris_manual_admin_approval", "note": note},
    )
    if response.status_code == 422:
        response = await _internal_request(request, "POST", path)
    if response.status_code not in {200, 201, 202, 204}:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Aktivasi paket pada billing gagal.",
                "billing_status": response.status_code,
                "billing_response": _safe_json(response),
            },
        )
    return {
        "status_code": response.status_code,
        "response": _safe_json(response),
        "activation_route": path,
    }


def _proof_filename(order_id: str, extension: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(order_id)).strip("-")
    return (safe or "order") + "-proof" + extension


@router.get("/api/payments/qris/manual/config")
def qris_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "mode": "static_qris_manual_verification",
        "merchant_name": MERCHANT_NAME,
        "image_url": QRIS_IMAGE_URL,
        "proof_required": True,
        "automatic_provider_confirmation": False,
        "instructions": [
            "Scan QRIS menggunakan aplikasi pembayaran.",
            "Masukkan nominal sesuai tagihan.",
            "Simpan dan unggah bukti pembayaran.",
            "Tunggu verifikasi admin.",
        ],
    }


@router.get("/api/payments/qris/manual/health")
def qris_runtime_health() -> dict[str, Any]:
    result = qris_health()
    result.update({
        "merchant_name": MERCHANT_NAME,
        "image_available": Path("static/payment/qris-docurapi.png").is_file(),
        "object_storage_proofs": True,
        "background_worker": True,
    })
    return result


@router.post("/api/payments/qris/manual/orders/{order_id}/prepare")
async def prepare_qris_order(order_id: str, request: Request) -> dict[str, Any]:
    user = await _require_user(request)
    order = await _fetch_order(request, order_id)
    try:
        payment = prepare_payment(
            order_id=order_id,
            user_id=user["user_id"],
            buyer_email=user["email"],
            amount=order["amount"],
            product_code=order["product_code"],
        )
    except QrisPaymentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"payment": _public_payment(payment), "qris": qris_config()}


@router.get("/api/payments/qris/manual/orders/{order_id}")
async def qris_order_detail(order_id: str, request: Request) -> dict[str, Any]:
    user = await _require_user(request)
    payment = get_payment_by_order(order_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Pembayaran QRIS belum disiapkan.")
    _ensure_owner(payment, user["user_id"])
    return {"payment": _public_payment(payment), "qris": qris_config()}


@router.post("/api/payments/qris/manual/orders/{order_id}/proof")
async def upload_qris_proof(
    order_id: str,
    request: Request,
    proof: UploadFile = File(...),
    payer_name: str = Form(default=""),
    payment_note: str = Form(default=""),
) -> dict[str, Any]:
    user = await _require_user(request)
    payment = get_payment_by_order(order_id)
    if payment is None:
        order = await _fetch_order(request, order_id)
        payment = prepare_payment(
            order_id=order_id,
            user_id=user["user_id"],
            buyer_email=user["email"],
            amount=order["amount"],
            product_code=order["product_code"],
        )
    _ensure_owner(payment, user["user_id"])

    data = await proof.read(MAX_PROOF_BYTES + 1)
    await proof.close()
    if not data:
        raise HTTPException(status_code=400, detail="File bukti kosong.")
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran bukti maksimal 8 MB.")

    try:
        content_type, extension = detect_proof_type(data)
    except QrisPaymentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    filename = _proof_filename(order_id, extension)
    key = build_object_key(
        "payment-proofs",
        filename,
        user_id=user["user_id"],
        resource_id=str(payment["payment_id"]),
    )
    bridge = create_storage_bridge(enabled=True, preserve_local=False)
    stored = bridge.persist_bytes(
        data,
        key,
        content_type=content_type,
        activate=True,
    )
    old_reference = str(payment.get("proof_reference") or "")
    try:
        updated = attach_proof(
            order_id=order_id,
            user_id=user["user_id"],
            proof_reference=stored.object_reference,
            proof_filename=filename,
            proof_content_type=content_type,
            proof_size=len(data),
            payer_name=payer_name.strip() or user["name"],
            payment_note=payment_note.strip() or None,
        )
    except Exception:
        bridge.delete(stored.object_reference)
        raise

    if old_reference and old_reference != stored.object_reference:
        try:
            bridge.delete(old_reference)
        except Exception:
            pass

    return {
        "status": "submitted",
        "payment": _public_payment(updated),
        "message": "Bukti berhasil dikirim dan menunggu verifikasi admin.",
    }


@router.get("/api/payments/qris/manual/admin/submissions")
async def admin_qris_submissions(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    await _require_admin(request)
    items = list_payments(status=status, limit=limit)
    return {"total": len(items), "items": items}


@router.get("/api/payments/qris/manual/admin/orders/{order_id}/proof")
async def admin_qris_proof(order_id: str, request: Request) -> Response:
    await _require_admin(request)
    payment = get_payment_by_order(order_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Pembayaran QRIS tidak ditemukan.")
    reference = str(payment.get("proof_reference") or "")
    if not reference:
        raise HTTPException(status_code=404, detail="Bukti pembayaran belum tersedia.")
    try:
        data = create_storage_bridge().read_bytes(reference)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="File bukti tidak dapat dibaca.") from exc
    filename = str(payment.get("proof_filename") or "payment-proof.bin")
    content_type = str(payment.get("proof_content_type") or "application/octet-stream")
    safe_filename = filename.replace('"', '')
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
    )


@router.post("/api/payments/qris/manual/admin/orders/{order_id}/approve")
async def approve_qris_payment(
    order_id: str,
    request: Request,
    body: ApprovalRequest | None = None,
) -> dict[str, Any]:
    admin = await _require_admin(request)
    payment = get_payment_by_order(order_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Pembayaran QRIS tidak ditemukan.")
    if payment["status"] == "approved":
        return {"status": "approved", "duplicate": True, "payment": payment}
    if payment["status"] != "submitted":
        raise HTTPException(status_code=409, detail="Bukti belum berstatus submitted.")

    activation = await _activate_existing_billing_order(request, order_id, body.note if body else None)
    job_id = "qris-approved-" + str(payment["payment_id"])
    worker_error = None
    if get_job(job_id) is None:
        try:
            enqueue_job(
                "billing.qris_manual_post_approval",
                {
                    "payment_id": payment["payment_id"],
                    "order_id": order_id,
                    "user_id": payment["user_id"],
                    "buyer_email": payment.get("buyer_email"),
                    "product_code": payment.get("product_code"),
                    "amount": payment["amount"],
                    "proof_reference": payment.get("proof_reference"),
                    "reviewed_by": admin["user_id"],
                    "merchant_name": MERCHANT_NAME,
                },
                priority=20,
                max_attempts=5,
                timeout_seconds=120,
                job_id=job_id,
            )
        except Exception as exc:
            worker_error = type(exc).__name__ + ": " + str(exc)
            job_id = None

    try:
        updated = mark_approved(
            order_id=order_id,
            reviewer_id=admin["user_id"],
            activation_response={**activation, "worker_error": worker_error},
            worker_job_id=job_id,
        )
    except QrisPaymentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "approved",
        "payment": updated,
        "billing_activation": activation,
        "worker_job_id": job_id,
        "worker_error": worker_error,
    }


@router.post("/api/payments/qris/manual/admin/orders/{order_id}/reject")
async def reject_qris_payment(order_id: str, request: Request, body: RejectRequest) -> dict[str, Any]:
    admin = await _require_admin(request)
    try:
        updated = mark_rejected(
            order_id=order_id,
            reviewer_id=admin["user_id"],
            reason=body.reason,
        )
    except QrisPaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pembayaran tidak ditemukan.") from exc
    except QrisPaymentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "rejected", "payment": updated}


@router.get("/qris-payment/{order_id}", response_class=HTMLResponse)
async def qris_payment_page(order_id: str) -> HTMLResponse:
    safe_order = html.escape(str(order_id), quote=True)
    script_order = json.dumps(str(order_id))
    page = f"""<!doctype html><html lang='id'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Pembayaran QRIS DocuRapi</title>
<style>body{{font-family:Arial;background:#f4f6f8;margin:0;color:#172033}}main{{max-width:920px;margin:32px auto;padding:18px}}.card{{background:white;border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(0,0,0,.08)}}.grid{{display:grid;grid-template-columns:minmax(280px,420px) 1fr;gap:28px}}.qris{{width:100%;border:1px solid #ddd;border-radius:14px}}.amount{{font-size:30px;font-weight:700;margin:8px 0 18px}}.status{{padding:12px;border-radius:10px;background:#eef4ff;margin:14px 0;white-space:pre-wrap}}label{{display:block;font-weight:600;margin:14px 0 6px}}input,textarea,button{{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid #ccd2da}}button{{background:#1f5eff;color:white;border:0;font-weight:700;cursor:pointer;margin-top:16px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}</style></head>
<body><main><div class='card'><h1>Pembayaran QRIS</h1><p>Order: <strong>{safe_order}</strong></p><div class='grid'><div><img class='qris' src='{QRIS_IMAGE_URL}' alt='QRIS {MERCHANT_NAME}'></div><div><p>Nama merchant:</p><strong>{MERCHANT_NAME}</strong><div id='amount' class='amount'>Memuat tagihan...</div><ol><li>Scan QRIS.</li><li>Masukkan nominal persis sesuai tagihan.</li><li>Pastikan nama merchant sesuai.</li><li>Unggah bukti pembayaran.</li></ol><form id='proofForm'><label>Nama pembayar</label><input name='payer_name'><label>Catatan</label><textarea name='payment_note' rows='3'></textarea><label>Bukti pembayaran</label><input name='proof' type='file' accept='image/png,image/jpeg,image/webp,application/pdf' required><button type='submit'>Kirim Bukti</button></form><div id='status' class='status'>Menyiapkan pembayaran...</div></div></div></div></main>
<script>const orderId={script_order};const s=document.getElementById('status'),a=document.getElementById('amount');async function prep(){{const r=await fetch(`/api/payments/qris/manual/orders/${{encodeURIComponent(orderId)}}/prepare`,{{method:'POST',credentials:'same-origin'}});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail||d));a.textContent=new Intl.NumberFormat('id-ID',{{style:'currency',currency:'IDR',maximumFractionDigits:0}}).format(Number(d.payment.amount));s.textContent='Status: '+d.payment.status;}}document.getElementById('proofForm').addEventListener('submit',async e=>{{e.preventDefault();s.textContent='Mengunggah bukti...';const r=await fetch(`/api/payments/qris/manual/orders/${{encodeURIComponent(orderId)}}/proof`,{{method:'POST',body:new FormData(e.target),credentials:'same-origin'}});const d=await r.json();s.textContent=r.ok?d.message:('Gagal: '+(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail||d)));}});prep().catch(e=>{{s.textContent='Gagal: '+e.message;a.textContent='Tagihan tidak tersedia';}});</script></body></html>"""
    return HTMLResponse(page)


@router.get("/admin/qris-payments", response_class=HTMLResponse)
async def qris_admin_page(request: Request) -> HTMLResponse:
    await _require_admin(request)
    page = f"""<!doctype html><html lang='id'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Admin QRIS DocuRapi</title><style>body{{font-family:Arial;background:#f6f7f9;margin:0;color:#172033}}main{{max-width:1200px;margin:30px auto;padding:18px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}button{{padding:8px 12px;border:0;border-radius:8px;cursor:pointer}}.approve{{background:#137333;color:white}}.reject{{background:#b3261e;color:white}}</style></head><body><main><h1>Verifikasi Pembayaran QRIS</h1><p>Merchant: <strong>{MERCHANT_NAME}</strong></p><button onclick='loadData()'>Muat Ulang</button><div id='message'></div><table><thead><tr><th>Order</th><th>Pengguna</th><th>Nominal</th><th>Bukti</th><th>Status</th><th>Aksi</th></tr></thead><tbody id='rows'></tbody></table></main><script>const rows=document.getElementById('rows'),msg=document.getElementById('message');const rupiah=v=>new Intl.NumberFormat('id-ID',{{style:'currency',currency:'IDR',maximumFractionDigits:0}}).format(Number(v));async function loadData(){{const r=await fetch('/api/payments/qris/manual/admin/submissions?limit=200',{{credentials:'same-origin'}});const d=await r.json();if(!r.ok){{msg.textContent='Gagal: '+JSON.stringify(d);return;}}rows.innerHTML='';for(const p of d.items){{const tr=document.createElement('tr');tr.innerHTML=`<td>${{p.order_id}}</td><td>${{p.buyer_email||p.user_id}}</td><td>${{rupiah(p.amount)}}</td><td>${{p.proof_reference?`<a target='_blank' href='/api/payments/qris/manual/admin/orders/${{encodeURIComponent(p.order_id)}}/proof'>${{p.proof_filename||'Lihat bukti'}}</a>`:'Belum ada'}}</td><td>${{p.status}}</td><td><button class='approve' onclick="approvePay('${{p.order_id}}')">Setujui</button> <button class='reject' onclick="rejectPay('${{p.order_id}}')">Tolak</button></td>`;rows.appendChild(tr);}}}}async function approvePay(id){{if(!confirm('Pastikan transaksi benar-benar masuk. Lanjutkan?'))return;const r=await fetch(`/api/payments/qris/manual/admin/orders/${{encodeURIComponent(id)}}/approve`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}',credentials:'same-origin'}});const d=await r.json();msg.textContent=r.ok?'Pembayaran disetujui.':'Gagal: '+JSON.stringify(d);loadData();}}async function rejectPay(id){{const reason=prompt('Alasan penolakan:');if(!reason)return;const r=await fetch(`/api/payments/qris/manual/admin/orders/${{encodeURIComponent(id)}}/reject`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{reason}}),credentials:'same-origin'}});const d=await r.json();msg.textContent=r.ok?'Pembayaran ditolak.':'Gagal: '+JSON.stringify(d);loadData();}}loadData();</script></body></html>"""
    return HTMLResponse(page)
