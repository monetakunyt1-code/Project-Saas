from __future__ import annotations

from fastapi import APIRouter, Query

from docurapi.services.admin_dashboard_service import (
    expire_overdue_invoices,
    get_admin_overview,
    get_audit_logs,
    list_expired_admin_invoices,
    list_pending_admin_payments,
)

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin-dashboard"])


@router.get("/overview")
def overview(secret: str = Query(...)):
    return get_admin_overview(secret=secret)


@router.get("/payments/pending")
def pending_payments(
    secret: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
):
    return list_pending_admin_payments(secret=secret, limit=limit)


@router.get("/payments/expired")
def expired_payments(
    secret: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
):
    return list_expired_admin_invoices(secret=secret, limit=limit)


@router.post("/invoices/expire-overdue")
def expire_overdue(secret: str = Query(...)):
    return expire_overdue_invoices(secret=secret)


@router.get("/audit-logs")
def audit_logs(
    secret: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
):
    return get_audit_logs(secret=secret, limit=limit)
