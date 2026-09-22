import json
import logging
from pathlib import Path

CRM_EMAIL = "priya.shah@kite.example"
WORKFLOW = Path("n8n/vision-ops-ticket-bridge.json")
INBOUND = Path("examples/n8n_inbound.json")


def _inbound() -> dict:
    return json.loads(INBOUND.read_text(encoding="utf-8"))


def test_inbound_runs_agent_and_status_round_trip(client, auth_headers, caplog):
    payload = _inbound()
    with caplog.at_level(logging.INFO):
        created = client.post("/api/v1/integrations/n8n/inbound", json=payload, headers=auth_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["accepted"] is True
    assert body["idempotent"] is False
    assert body["workflow"] == "vision-ops-ticket-bridge"
    assert body["external_id"] == payload["external_id"]
    assert body["run"]["intent"] == "escalation"
    assert body["run"]["ticket_status"] == "escalated"
    assert body["ticket"]["id"] == body["run"]["ticket_id"]
    assert any(call["tool"] == "notify_slack" and call["ok"] for call in body["run"]["tool_calls"])
    assert CRM_EMAIL not in created.text
    assert payload["subject"] not in caplog.text
    assert payload["body"] not in caplog.text

    note = "status-note-should-not-be-logged-42"
    with caplog.at_level(logging.INFO):
        posted = client.post(
            "/api/v1/integrations/n8n/status",
            json={
                "ticket_id": body["ticket"]["id"],
                "workflow": body["workflow"],
                "status": "posted",
                "external_id": body["external_id"],
                "note": note,
            },
            headers=auth_headers,
        )
    assert posted.status_code == 201
    assert posted.json()["status"] == "posted"
    assert note not in caplog.text

    detail = client.get(f"/api/v1/handoff/tickets/{body['ticket']['id']}", headers=auth_headers)
    assert detail.json()["n8n_events"][0]["note"] == note
    events = client.get("/api/v1/integrations/n8n/events", headers=auth_headers)
    assert events.status_code == 200
    kinds = [event["event"] for event in events.json()["events"]]
    assert kinds == ["status.posted", "ticket.created"]


def test_inbound_is_idempotent_for_the_same_external_id(client, auth_headers):
    payload = _inbound()
    first = client.post("/api/v1/integrations/n8n/inbound", json=payload, headers=auth_headers)
    second = client.post("/api/v1/integrations/n8n/inbound", json=payload, headers=auth_headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["idempotent"] is True
    assert second.json()["ticket"]["id"] == first.json()["ticket"]["id"]
    assert second.json()["run"]["id"] == first.json()["run"]["id"]
    listed = client.get("/api/v1/tickets", headers=auth_headers)
    assert listed.json()["count"] == 1


def test_n8n_routes_require_a_key_and_reject_bad_payloads(client, auth_headers):
    assert client.post("/api/v1/integrations/n8n/inbound", json=_inbound()).status_code == 401
    assert client.post("/api/v1/integrations/n8n/status", json={"ticket_id": "x", "status": "posted"}).status_code == 401
    assert client.get("/api/v1/integrations/n8n/events").status_code == 401

    bad_event = _inbound()
    bad_event["event"] = "ticket.deleted"
    assert client.post("/api/v1/integrations/n8n/inbound", json=bad_event, headers=auth_headers).status_code == 422

    bad_id = _inbound()
    bad_id["external_id"] = "has space"
    assert client.post("/api/v1/integrations/n8n/inbound", json=bad_id, headers=auth_headers).status_code == 422

    missing = client.post(
        "/api/v1/integrations/n8n/status",
        json={"ticket_id": "missing-ticket", "status": "failed"},
        headers=auth_headers,
    )
    assert missing.status_code == 404


def test_workflow_json_calls_the_bridge_without_secrets():
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = json.loads(raw)
    names = [node["name"] for node in workflow["nodes"]]
    assert names == ["Receive ticket event", "Call agent API", "Post status"]
    assert workflow["active"] is False
    assert workflow["connections"]["Receive ticket event"]["main"][0][0]["node"] == "Call agent API"
    assert workflow["connections"]["Call agent API"]["main"][0][0]["node"] == "Post status"
    joined = json.dumps(workflow)
    assert "$env.OPS_AGENT_URL" in joined
    assert "$env.OPS_AGENT_API_KEY" in joined
    assert "/api/v1/integrations/n8n/inbound" in joined
    assert "/api/v1/integrations/n8n/status" in joined
    assert "change-me" not in raw
    assert "sk-" not in raw
    assert "hooks.slack.com" not in raw
    assert "BEGIN PRIVATE" not in raw
    for node in workflow["nodes"]:
        assert "credentials" not in node


def test_env_example_leaves_the_n8n_key_blank():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "OPS_AGENT_URL=http://127.0.0.1:8789" in text
    matched = [line for line in text.splitlines() if line.startswith("OPS_AGENT_API_KEY=")]
    assert matched == ["OPS_AGENT_API_KEY="]
