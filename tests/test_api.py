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


def test_watchlist_endpoint_round_trip():
    client = TestClient(app)

    create_response = client.post("/api/watchlist", json={"ticker": "MSFT", "name": "Microsoft"})
    list_response = client.get("/api/watchlist")
    delete_response = client.delete("/api/watchlist/MSFT")

    assert create_response.status_code == 200
    assert create_response.json()["ticker"] == "MSFT"
    assert list_response.status_code == 200
    assert any(item["ticker"] == "MSFT" for item in list_response.json())
    assert delete_response.json()["deleted"] is True
