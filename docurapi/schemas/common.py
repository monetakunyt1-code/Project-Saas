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
    download_url: str
    report_url: str
    summary: dict[str, Any]
