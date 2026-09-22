from tests.conftest import AUTH


def test_health_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["db"] is True
    assert body["status"] == "ok"
    assert body["ai_provider"] == "heuristic"
    assert body["model"] == "heuristic"
    assert body["ollama"] is None
    assert "x-request-id" in response.headers


def test_health_accepts_key_but_does_not_require_it(client):
    response = client.get("/health", headers=AUTH)
    assert response.status_code == 200


def test_health_does_not_call_ollama(client, monkeypatch):
    def fail_get(*_args, **_kwargs):
        raise AssertionError("heuristic health must not call Ollama")

    monkeypatch.setattr("app.api.routes.health.httpx.get", fail_get)
    response = client.get("/health")
    assert response.status_code == 200
