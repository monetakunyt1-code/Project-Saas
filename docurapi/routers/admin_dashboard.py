from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from docurapi.routers.admin_auth import get_admin_secret
from docurapi.services.admin_dashboard_service import (
    expire_overdue_invoices,
    get_admin_overview,
    get_audit_logs,
    list_expired_admin_invoices,
    list_pending_admin_payments,
)

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin-dashboard"])


@router.get("/overview")
def overview(admin_secret: str = Depends(get_admin_secret)):
    return get_admin_overview(secret=admin_secret)


@router.get("/payments/pending")
def pending_payments(
    admin_secret: str = Depends(get_admin_secret),
    limit: int = Query(50, ge=1, le=100),
):
    return list_pending_admin_payments(secret=admin_secret, limit=limit)


@router.get("/payments/expired")
def expired_payments(
    admin_secret: str = Depends(get_admin_secret),
    limit: int = Query(50, ge=1, le=100),
):
    return list_expired_admin_invoices(secret=admin_secret, limit=limit)


@router.post("/invoices/expire-overdue")
def expire_overdue(admin_secret: str = Depends(get_admin_secret)):
    return expire_overdue_invoices(secret=admin_secret)


@router.get("/audit-logs")
def audit_logs(
    admin_secret: str = Depends(get_admin_secret),
    limit: int = Query(50, ge=1, le=200),
):
    return get_audit_logs(secret=admin_secret, limit=limit)
