import logging

from app.core.config import get_settings
from tests.conftest import AUTH


BILLING = {
    "subject": "Duplicate TraceLight invoice",
    "body": "We were charged twice for the September invoice.",
    "customer_id": "cust-1042",
    "channel": "email",
}


def test_missing_key(client):
    response = client.post("/api/v1/tickets", json=BILLING)
    assert response.status_code == 401
    assert response.json()["error"] == "Invalid or missing API key"


def test_wrong_key(client):
    response = client.post(
        "/api/v1/tickets",
        json=BILLING,
        headers={"X-API-Key": "nope"},
    )
    assert response.status_code == 401


def test_reads_require_key(client):
    assert client.get("/api/v1/tickets").status_code == 401
    assert client.get("/api/v1/tickets/missing").status_code == 401
    assert client.get("/api/v1/runs/missing").status_code == 401
    assert client.post("/api/v1/agent/run", json={"ticket_id": "missing"}).status_code == 401


def test_empty_api_key_fails_closed(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "")
    response = client.post("/api/v1/tickets", json=BILLING, headers=AUTH)
    assert response.status_code == 503
    assert response.json()["error"] == "API authentication is not configured"
    health = client.get("/health")
    assert health.status_code == 200


def test_validation_log_omits_body(client, caplog):
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/tickets",
            json={"body": "secret-phrase-do-not-log", "channel": "email"},
            headers=AUTH,
        )
    assert response.status_code == 422
    assert "secret-phrase-do-not-log" not in caplog.text
