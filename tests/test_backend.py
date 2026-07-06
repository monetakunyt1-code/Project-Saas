from fastapi.testclient import TestClient

from docurapi.core.security import (
    create_admin_action_token,
    verify_admin_action_token,
)
from docurapi.core.settings import settings
from docurapi.main import app
from docurapi.services.payment_service import get_payment_provider
from docurapi.services.pricing_service import get_available_prices, get_processing_price
from docurapi.services.invoice_service import build_invoice_fields
from docurapi.services.processing_service import generate_unique_payment_amount

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
    amount, unique_code = generate_unique_payment_amount(base_amount)

    assert amount == base_amount + unique_code
    assert unique_code >= settings.UNIQUE_CODE_MIN
    assert unique_code <= settings.UNIQUE_CODE_MAX


def test_invoice_fields_builder():
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
