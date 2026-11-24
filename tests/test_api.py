from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# داتابيز SQLite وهمية في الرامات للاختبار السريع فقط
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_dashboard_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "URL Monitor" in response.text


def test_health_endpoint():
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    with patch("app.main.redis.from_url", return_value=mock_redis):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_create_and_fetch_job():
    with patch("app.main.check_url_task.delay") as mock_delay:
        create_res = client.post("/jobs", json={"target_url": "https://example.com"})
        assert create_res.status_code == 202
        body = create_res.json()
        assert body["status"] == "PENDING"
        mock_delay.assert_called_once_with(body["job_id"])

        get_res = client.get(f"/jobs/{body['job_id']}")
        assert get_res.status_code == 200
        assert get_res.json()["target_url"] == "https://example.com/"


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text