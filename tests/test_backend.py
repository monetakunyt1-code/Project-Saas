from fastapi.testclient import TestClient

from docurapi.core.settings import settings
from docurapi.main import app
from docurapi.services.payment_service import get_payment_provider

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


def test_payment_provider_default_is_manual_qris_whatsapp():
    assert settings.PAYMENT_MODE in {"manual_qris_whatsapp", "manual_qris"}
    assert get_payment_provider().provider_name == "manual_qris_whatsapp"
