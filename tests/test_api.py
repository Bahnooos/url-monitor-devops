from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_dashboard_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "URL Monitor" in response.text


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "up"
    assert data["redis"] == "up"


def test_create_and_fetch_job():
    # نعمل Mock لـ Celery delay عشان نختبر الـ API بدون انتظار طلب HTTP خارجي
    with patch("app.main.check_url_task.delay") as mock_delay:
        create_res = client.post("/jobs", json={"target_url": "https://example.com"})
        assert create_res.status_code == 202
        body = create_res.json()
        assert body["status"] == "PENDING"
        assert "job_id" in body
        mock_delay.assert_called_once_with(body["job_id"])

        # نتاكد إن المهمة اتسجلت في PostgreSQL ونقدر نجيبها
        job_id = body["job_id"]
        get_res = client.get(f"/jobs/{job_id}")
        assert get_res.status_code == 200
        assert get_res.json()["target_url"] == "https://example.com/"


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text