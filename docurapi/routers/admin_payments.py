from __future__ import annotations

from html import escape

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse

from docurapi.services.admin_payment_service import (
    approve_payment,
    get_admin_payment_detail,
    list_pending_payments,
    reject_payment,
)

router = APIRouter(prefix="/api/admin/payments", tags=["admin-payments"])


def render_admin_result_page(
    title: str,
    status: str,
    message: str,
    job_id: str,
    payment_status: str,
    extra: str = "",
) -> HTMLResponse:
    safe_title = escape(title)
    safe_status = escape(status)
    safe_message = escape(message)
    safe_job_id = escape(job_id)
    safe_payment_status = escape(payment_status)

    html = f"""
    <!doctype html>
    <html lang="id">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{safe_title}</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background: #f4f6f8;
          margin: 0;
          padding: 24px;
          color: #0f172a;
        }}
        .card {{
          max-width: 680px;
          margin: 48px auto;
          background: white;
          border-radius: 16px;
          padding: 28px;
          box-shadow: 0 8px 24px rgba(15, 23, 42, 0.10);
        }}
        .status {{
          display: inline-block;
          padding: 8px 12px;
          border-radius: 999px;
          background: #e0f2fe;
          color: #0369a1;
          font-weight: bold;
          margin-bottom: 16px;
        }}
        h1 {{
          margin-top: 0;
        }}
        .meta {{
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 16px;
          margin-top: 18px;
          line-height: 1.7;
          overflow-wrap: anywhere;
        }}
        .note {{
          margin-top: 18px;
          color: #475569;
          line-height: 1.6;
        }}
      </style>
    </head>
    <body>
      <main class="card">
        <div class="status">{safe_status}</div>
        <h1>{safe_title}</h1>
        <p>{safe_message}</p>
        <div class="meta">
          <strong>Job ID:</strong> {safe_job_id}<br>
          <strong>Status pembayaran:</strong> {safe_payment_status}
        </div>
        {extra}
        <p class="note">
          Kamu bisa menutup halaman ini. Status dokumen sudah diperbarui di backend DocuRapi.
        </p>
      </main>
    </body>
    </html>
    """

    return HTMLResponse(html)


@router.get("/pending")
def pending_payments(
    secret: str = Query(...),
    limit: int = Query(25, ge=1, le=100),
):
    return list_pending_payments(secret=secret, limit=limit)


@router.get("/{job_id}")
def payment_detail(job_id: str, secret: str = Query(...)):
    return get_admin_payment_detail(job_id=job_id, secret=secret)


@router.get("/{job_id}/approve")
def approve_payment_by_link(
    job_id: str,
    secret: str | None = Query(None),
    admin_token: str | None = Query(None),
):
    result = approve_payment(
        job_id=job_id,
        secret=secret,
        admin_token=admin_token,
    )

    extra = f"""
      <div class="meta">
        <strong>Referensi:</strong> {escape(result.get("payment_reference", "-"))}<br>
        <strong>Download URL:</strong><br>
        <code>{escape(result.get("download_url", "-"))}</code>
      </div>
    """

    return render_admin_result_page(
        title="Pembayaran Disetujui",
        status="APPROVED",
        message="Pembayaran berhasil diverifikasi. Download dokumen sudah dibuka untuk user.",
        job_id=result["job_id"],
        payment_status=result["payment_status"],
        extra=extra,
    )


@router.post("/{job_id}/approve")
def approve_payment_by_post(
    job_id: str,
    secret: str | None = Query(None),
    admin_token: str | None = Query(None),
):
    return approve_payment(
        job_id=job_id,
        secret=secret,
        admin_token=admin_token,
    )


@router.get("/{job_id}/reject")
def reject_payment_by_link(
    job_id: str,
    secret: str | None = Query(None),
    admin_token: str | None = Query(None),
    reason: str = Query("Pembayaran tidak ditemukan atau tidak sesuai."),
):
    result = reject_payment(
        job_id=job_id,
        secret=secret,
        admin_token=admin_token,
        reason=reason,
    )

    extra = f"""
      <div class="meta">
        <strong>Alasan:</strong> {escape(result.get("reason", "-"))}
      </div>
    """

    return render_admin_result_page(
        title="Pembayaran Ditolak",
        status="REJECTED",
        message="Pembayaran ditolak. Download dokumen tetap terkunci.",
        job_id=result["job_id"],
        payment_status=result["payment_status"],
        extra=extra,
    )


@router.post("/{job_id}/reject")
def reject_payment_by_post(
    job_id: str,
    secret: str | None = Query(None),
    admin_token: str | None = Query(None),
    reason: str = Form("Pembayaran tidak ditemukan atau tidak sesuai."),
):
    return reject_payment(
        job_id=job_id,
        secret=secret,
        admin_token=admin_token,
        reason=reason,
    )
