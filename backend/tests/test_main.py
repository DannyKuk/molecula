from fastapi.testclient import TestClient

from molecula.main import app


def test_frontend_origin_may_call_the_api() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_gets_no_cors_header() -> None:
    response = TestClient(app).get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers
