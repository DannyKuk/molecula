from fastapi.testclient import TestClient

from molecula.main import app


def test_health_reports_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
