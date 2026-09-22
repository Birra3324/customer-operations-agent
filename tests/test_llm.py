import json

import httpx

from app.core.config import get_settings


BILLING = {
    "subject": "Duplicate TraceLight invoice",
    "body": "We were charged twice for the September invoice.",
    "customer_id": "cust-1042",
    "channel": "email",
}


def _openai_response(payload: dict) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        request=request,
    )


def test_openai_http_tool_then_final(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_provider", "openai")
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")
    steps = [
        {
            "thought": "Search the billing notes",
            "action": "tool",
            "tool": "lookup_kb",
            "arguments": {"query": "duplicate invoice"},
        },
        {
            "thought": "Answer from the article",
            "action": "final",
            "final_reply": "Credit the duplicate September invoice.",
        },
    ]

    def fake_post(url, **_kwargs):
        assert "openai.com" in url
        return _openai_response(steps.pop(0))

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    response = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    assert response.status_code == 201
    run = response.json()["run"]
    assert run["provider"] == "openai"
    assert run["fallback"] is None
    assert run["tool_calls"][0]["tool"] == "lookup_kb"
    assert run["tool_calls"][0]["ok"] is True
    assert run["final_reply"] == "Credit the duplicate September invoice."
    assert steps == []


def test_model_cannot_call_shell(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_provider", "openai")
    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key-not-real")
    steps = [
        {
            "thought": "Try a shell command",
            "action": "tool",
            "tool": "shell",
            "arguments": {"cmd": "id"},
        },
        {
            "thought": "Stop",
            "action": "final",
            "final_reply": "I cannot run that.",
        },
    ]

    def fake_post(url, **_kwargs):
        return _openai_response(steps.pop(0))

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    response = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    assert response.status_code == 201
    call = response.json()["run"]["tool_calls"][0]
    assert call["tool"] == "shell"
    assert call["ok"] is False
    assert call["error"] == "tool_not_allowed"


def test_missing_openai_key_falls_back(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_provider", "openai")
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    response = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    assert response.status_code == 201
    run = response.json()["run"]
    assert run["provider"] == "openai"
    assert run["fallback"] == "heuristic"
    assert run["intent"] == "billing"
    assert any(call["tool"] == "lookup_kb" and call["ok"] for call in run["tool_calls"])


def test_ollama_transport_error_falls_back(client, auth_headers, monkeypatch, caplog):
    monkeypatch.setattr(get_settings(), "ai_provider", "ollama")
    calls = {"n": 0}

    def fake_post(_url, **_kwargs):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.services.llm.httpx.post", fake_post)
    import logging

    with caplog.at_level(logging.INFO):
        response = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    assert response.status_code == 201
    assert calls["n"] == 3
    assert response.json()["run"]["fallback"] == "heuristic"
    assert "Duplicate TraceLight invoice" not in caplog.text
    assert "charged twice" not in caplog.text
