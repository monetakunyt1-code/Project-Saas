from fastapi.testclient import TestClient

from docurapi.core.security import (
    create_admin_action_token,
    verify_admin_action_token,
)
from docurapi.core.settings import settings
from docurapi.db.connection import initialize_database
from docurapi.main import app
from docurapi.services.invoice_service import build_invoice_fields
from docurapi.services.payment_service import get_payment_provider
from docurapi.services.pricing_service import get_available_prices, get_processing_price

initialize_database()

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_jobs_history():
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert "jobs" in response.json()


def test_templates_list():
    response = client.get("/api/templates")
    assert response.status_code == 200
    assert "templates" in response.json()


def test_payment_checkout_unknown_job():
    response = client.get("/api/payments/unknown-job/checkout?token=dummy")
    assert response.status_code == 404


def test_payment_status_unknown_job():
    response = client.get("/api/payments/unknown-job/status?token=dummy")
    assert response.status_code == 404


def test_admin_pending_requires_valid_secret():
    response = client.get("/api/admin/payments/pending?secret=wrong")
    assert response.status_code == 403


def test_admin_dashboard_requires_valid_secret():
    response = client.get("/api/admin/dashboard/overview?secret=wrong")
    assert response.status_code == 403


def test_admin_dashboard_overview_valid_secret():
    response = client.get(
        f"/api/admin/dashboard/overview?secret={settings.ADMIN_APPROVAL_SECRET}"
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "jobs" in response.json()
    assert "payments" in response.json()


def test_admin_audit_logs_valid_secret():
    response = client.get(
        f"/api/admin/dashboard/audit-logs?secret={settings.ADMIN_APPROVAL_SECRET}"
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "audit_logs" in response.json()


def test_admin_expire_overdue_valid_secret():
    response = client.post(
        f"/api/admin/dashboard/invoices/expire-overdue?secret={settings.ADMIN_APPROVAL_SECRET}"
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_admin_proof_unknown_without_access():
    response = client.get("/api/admin/payments/unknown/proof")
    assert response.status_code == 403


def test_payment_provider_default_is_manual_qris_whatsapp():
    assert settings.PAYMENT_MODE in {"manual_qris_whatsapp", "manual_qris"}
    assert get_payment_provider().provider_name == "manual_qris_whatsapp"


def test_env_settings_loaded():
    assert settings.ADMIN_APPROVAL_SECRET
    assert settings.PUBLIC_BASE_URL
    assert settings.PAYMENT_PROOF_DIR.exists()


def test_admin_action_token_validation():
    token = create_admin_action_token(job_id="job-test", action="approve")

    assert verify_admin_action_token(
        job_id="job-test",
        action="approve",
        token=token,
    )

    assert not verify_admin_action_token(
        job_id="job-test",
        action="reject",
        token=token,
    )

    assert not verify_admin_action_token(
        job_id="other-job",
        action="approve",
        token=token,
    )


def test_admin_view_token_validation():
    token = create_admin_action_token(job_id="job-test", action="view")

    assert verify_admin_action_token(
        job_id="job-test",
        action="view",
        token=token,
    )

    assert not verify_admin_action_token(
        job_id="job-test",
        action="approve",
        token=token,
    )


def test_unique_payment_amount_generation():
    base_amount = 12000
    fields = build_invoice_fields(base_amount)

    assert fields["amount"] == fields["base_amount"] + fields["unique_code"]
    assert fields["base_amount"] == base_amount
    assert fields["unique_code"] >= settings.UNIQUE_CODE_MIN
    assert fields["unique_code"] <= settings.UNIQUE_CODE_MAX
    assert fields["invoice_expires_at"]


def test_pricing_endpoint():
    response = client.get("/api/pricing")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["currency"] == "IDR"
    assert response.json()["prices"]["format"] > 0


def test_pricing_service_values():
    prices = get_available_prices()
    assert prices["analyze"] == settings.PRICE_ANALYZE
    assert prices["format"] == settings.PRICE_FORMAT
    assert prices["journal"] == settings.PRICE_JOURNAL
    assert get_processing_price("format") == settings.PRICE_FORMAT


def test_admin_cleanup_requires_valid_secret():
    response = client.post("/api/admin/cleanup/run?secret=wrong&dry_run=true")
    assert response.status_code == 403


def test_admin_cleanup_dry_run_valid_secret():
    response = client.post(
        f"/api/admin/cleanup/run?secret={settings.ADMIN_APPROVAL_SECRET}&dry_run=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["dry_run"] is True
    assert "summary" in data
    assert "retention_policy" in data
