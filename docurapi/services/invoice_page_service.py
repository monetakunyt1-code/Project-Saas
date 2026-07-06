from __future__ import annotations

from html import escape
from typing import Any

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from docurapi.core.settings import settings
from docurapi.db.payments_repository import list_payments_for_job
from docurapi.services.invoice_service import is_invoice_expired
from docurapi.services.payment_service import ensure_payment_access


def rupiah(value: int | str | None) -> str:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0

    return f"Rp{number:,}".replace(",", ".")


def build_invoice_payload(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)
    payments = list_payments_for_job(job_id)

    return {
        "success": True,
        "type": "invoice",
        "job_id": job_id,
        "original_name": job.get("original_name"),
        "mode": job.get("mode"),
        "preset": job.get("preset"),
        "payment_status": job.get("payment_status"),
        "amount": job.get("amount", 0),
        "base_amount": job.get("base_amount", job.get("amount", 0)),
        "unique_code": job.get("unique_code", 0),
        "invoice_expires_at": job.get("invoice_expires_at"),
        "invoice_expired": is_invoice_expired(job),
        "merchant_name": settings.MERCHANT_NAME,
        "qris_static_image_url": settings.QRIS_STATIC_IMAGE_URL,
        "confirm_manual_url": f"/api/payments/{job_id}/confirm-manual?token={token}",
        "refresh_invoice_url": f"/api/payments/{job_id}/refresh-invoice?token={token}",
        "payments": payments,
    }


def build_receipt_payload(job_id: str, token: str) -> dict[str, Any]:
    job = ensure_payment_access(job_id, token)

    if job.get("payment_status") != "paid":
        raise HTTPException(
            status_code=403,
            detail="Receipt hanya tersedia setelah pembayaran disetujui.",
        )

    payments = list_payments_for_job(job_id)

    return {
        "success": True,
        "type": "receipt",
        "job_id": job_id,
        "original_name": job.get("original_name"),
        "mode": job.get("mode"),
        "preset": job.get("preset"),
        "payment_status": job.get("payment_status"),
        "amount": job.get("amount", 0),
        "base_amount": job.get("base_amount", job.get("amount", 0)),
        "unique_code": job.get("unique_code", 0),
        "payment_reference": job.get("payment_reference"),
        "paid_at": job.get("paid_at"),
        "merchant_name": settings.MERCHANT_NAME,
        "download_url": f"/api/jobs/{job_id}/download?token={token}",
        "payments": payments,
    }


def render_invoice_html(payload: dict[str, Any]) -> HTMLResponse:
    invoice_expired = bool(payload.get("invoice_expired"))
    payment_status = str(payload.get("payment_status") or "-")

    if payload.get("payment_status") == "paid":
        badge_bg = "#dcfce7"
        badge_color = "#166534"
        status_text = "PAID"
    elif invoice_expired:
        badge_bg = "#fee2e2"
        badge_color = "#991b1b"
        status_text = "EXPIRED"
    elif payload.get("payment_status") == "pending_verification":
        badge_bg = "#fef9c3"
        badge_color = "#854d0e"
        status_text = "PENDING VERIFICATION"
    else:
        badge_bg = "#e0f2fe"
        badge_color = "#0369a1"
        status_text = payment_status.upper()

    html = f"""
    <!doctype html>
    <html lang="id">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Invoice DocuRapi</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background: #f4f6f8;
          margin: 0;
          padding: 24px;
          color: #0f172a;
        }}
        .card {{
          max-width: 760px;
          margin: 32px auto;
          background: white;
          border-radius: 16px;
          padding: 28px;
          box-shadow: 0 8px 24px rgba(15, 23, 42, 0.10);
        }}
        .badge {{
          display: inline-block;
          padding: 8px 12px;
          border-radius: 999px;
          background: {badge_bg};
          color: {badge_color};
          font-weight: bold;
          margin-bottom: 16px;
        }}
        h1 {{ margin-top: 0; }}
        .grid {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
        }}
        .box {{
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 16px;
          line-height: 1.7;
          overflow-wrap: anywhere;
        }}
        .amount {{
          font-size: 32px;
          font-weight: 800;
          margin: 6px 0;
        }}
        .warning {{
          margin-top: 18px;
          padding: 14px;
          border-radius: 12px;
          background: #fff7ed;
          border: 1px solid #fed7aa;
          color: #9a3412;
          line-height: 1.6;
        }}
        .note {{
          margin-top: 18px;
          color: #475569;
          line-height: 1.6;
        }}
        @media (max-width: 700px) {{
          .grid {{ grid-template-columns: 1fr; }}
        }}
      </style>
    </head>
    <body>
      <main class="card">
        <div class="badge">{escape(status_text)}</div>
        <h1>Invoice Pembayaran DocuRapi</h1>
        <p>Gunakan nominal unik berikut saat membayar melalui QRIS statis.</p>

        <div class="grid">
          <div class="box">
            <strong>Job ID</strong><br>
            {escape(str(payload.get("job_id") or "-"))}<br><br>
            <strong>File</strong><br>
            {escape(str(payload.get("original_name") or "-"))}<br><br>
            <strong>Layanan</strong><br>
            {escape(str(payload.get("mode") or "-"))} / {escape(str(payload.get("preset") or "-"))}
          </div>

          <div class="box">
            <strong>Merchant</strong><br>
            {escape(str(payload.get("merchant_name") or "-"))}<br><br>
            <strong>Expired</strong><br>
            {escape(str(payload.get("invoice_expires_at") or "-"))}<br><br>
            <strong>Status</strong><br>
            {escape(payment_status)}
          </div>
        </div>

        <div class="box" style="margin-top: 16px;">
          <strong>Harga dasar</strong><br>
          {rupiah(payload.get("base_amount"))}<br><br>
          <strong>Kode unik</strong><br>
          {rupiah(payload.get("unique_code"))}<br><br>
          <strong>Total bayar</strong>
          <div class="amount">{rupiah(payload.get("amount"))}</div>
        </div>

        <div class="warning">
          Jangan membulatkan nominal. Bayar sesuai total nominal unik agar admin mudah mencocokkan pembayaran.
        </div>

        <p class="note">
          Setelah membayar, upload bukti pembayaran melalui halaman/fitur konfirmasi pembayaran.
          Download dokumen akan terbuka setelah admin menyetujui pembayaran.
        </p>
      </main>
    </body>
    </html>
    """

    return HTMLResponse(html)


def render_receipt_html(payload: dict[str, Any]) -> HTMLResponse:
    html = f"""
    <!doctype html>
    <html lang="id">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Receipt DocuRapi</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          background: #f4f6f8;
          margin: 0;
          padding: 24px;
          color: #0f172a;
        }}
        .card {{
          max-width: 760px;
          margin: 32px auto;
          background: white;
          border-radius: 16px;
          padding: 28px;
          box-shadow: 0 8px 24px rgba(15, 23, 42, 0.10);
        }}
        .badge {{
          display: inline-block;
          padding: 8px 12px;
          border-radius: 999px;
          background: #dcfce7;
          color: #166534;
          font-weight: bold;
          margin-bottom: 16px;
        }}
        h1 {{ margin-top: 0; }}
        .box {{
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          padding: 16px;
          line-height: 1.7;
          overflow-wrap: anywhere;
          margin-top: 16px;
        }}
        .amount {{
          font-size: 32px;
          font-weight: 800;
          margin: 6px 0;
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
        <div class="badge">PAID</div>
        <h1>Receipt Pembayaran DocuRapi</h1>
        <p>Pembayaran sudah diverifikasi dan dokumen dapat di-download.</p>

        <div class="box">
          <strong>Job ID:</strong> {escape(str(payload.get("job_id") or "-"))}<br>
          <strong>File:</strong> {escape(str(payload.get("original_name") or "-"))}<br>
          <strong>Layanan:</strong> {escape(str(payload.get("mode") or "-"))} / {escape(str(payload.get("preset") or "-"))}<br>
          <strong>Merchant:</strong> {escape(str(payload.get("merchant_name") or "-"))}<br>
          <strong>Referensi pembayaran:</strong> {escape(str(payload.get("payment_reference") or "-"))}<br>
          <strong>Dibayar pada:</strong> {escape(str(payload.get("paid_at") or "-"))}
        </div>

        <div class="box">
          <strong>Total dibayar</strong>
          <div class="amount">{rupiah(payload.get("amount"))}</div>
          <strong>Harga dasar:</strong> {rupiah(payload.get("base_amount"))}<br>
          <strong>Kode unik:</strong> {rupiah(payload.get("unique_code"))}
        </div>

        <p class="note">
          Simpan halaman ini sebagai bukti pembayaran. Download URL tersedia melalui respons API atau halaman aplikasi.
        </p>
      </main>
    </body>
    </html>
    """

    return HTMLResponse(html)
