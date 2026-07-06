from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    application: str
    version: str


class MessageResponse(BaseModel):
    success: bool
    message: str


class ProcessingResponse(BaseModel):
    success: bool
    job_id: str
    message: str
    preview_url: str
    report_url: str
    payment_url: str
    download_url: str | None = None
    payment_status: str
    amount: int
    base_amount: int | None = None
    unique_code: int | None = None
    invoice_expires_at: str | None = None
    summary: dict[str, Any]


class PaymentCheckoutResponse(BaseModel):
    success: bool
    job_id: str
    payment_id: str | None = None
    provider: str | None = None
    payment_status: str
    amount: int
    base_amount: int | None = None
    unique_code: int | None = None
    invoice_expires_at: str | None = None
    message: str
    qris_type: str | None = None
    merchant_name: str | None = None
    qris_static_image_url: str | None = None
    payment_instruction: list[str] | None = None
    proof_required: bool | None = None
    proof_allowed_extensions: list[str] | None = None
    confirm_manual_url: str | None = None
    simulate_payment_url: str | None = None


class ManualPaymentConfirmResponse(BaseModel):
    success: bool
    job_id: str
    payment_id: str | None = None
    payment_status: str
    amount: int
    message: str
    proof_uploaded: bool = False
    proof_file_name: str | None = None
    admin_whatsapp_url: str | None = None


class PaymentSuccessResponse(BaseModel):
    success: bool
    job_id: str
    payment_status: str
    payment_reference: str
    message: str
    download_url: str


class PaymentStatusResponse(BaseModel):
    success: bool
    job_id: str
    job_payment_status: str
    amount: int
    payments: list[dict[str, Any]]
