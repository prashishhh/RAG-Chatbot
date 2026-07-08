from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_standard_response_and_request_id() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "req_test"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req_test"
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Application is healthy."
    assert body["errors"] == {}
    assert body["data"]["status"] == "healthy"
    assert body["data"]["service"] == "knowbase-api"


def test_unknown_route_returns_standard_error_response() -> None:
    response = client.get("/api/v1/unknown", headers={"X-Request-ID": "req_missing"})

    assert response.status_code == 404
    assert response.headers["x-request-id"] == "req_missing"
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["requestId"] == "req_missing"


def test_health_db_requires_auth() -> None:
    response = client.get("/api/v1/health/db")
    assert response.status_code == 401


def test_health_vector_store_requires_auth() -> None:
    response = client.get("/api/v1/health/vector-store")
    assert response.status_code == 401


