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
    summary: dict[str, Any]


class PaymentCheckoutResponse(BaseModel):
    success: bool
    job_id: str
    payment_status: str
    amount: int
    message: str
    simulate_payment_url: str | None = None


class PaymentSuccessResponse(BaseModel):
    success: bool
    job_id: str
    payment_status: str
    payment_reference: str
    message: str
    download_url: str
