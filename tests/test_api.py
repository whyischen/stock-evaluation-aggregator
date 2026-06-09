from fastapi.testclient import TestClient

from sea_api.main import app


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_evaluate_endpoint_returns_plugin_results():
    client = TestClient(app)

    response = client.post("/api/evaluate", json={"ticker": "AAPL"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["success_count"] == 2
    assert payload["failed_count"] == 2
    assert len(payload["results"]) == 4
