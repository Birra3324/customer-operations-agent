import logging
from pathlib import Path

from sqlalchemy import create_engine, text

from app.db.database import ensure_ticket_handoff_columns

BILLING = {
    "subject": "Duplicate TraceLight invoice",
    "body": "We were charged twice for the September TraceLight Enterprise invoice.",
    "customer_id": "cust-1042",
    "channel": "email",
}


def test_handoff_page_is_public_and_has_no_key(client):
    response = client.get("/handoff")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    page = response.text
    assert "Human handoff" in page
    assert "test-api-key" not in page
    assert "innerHTML" not in page
    for queue_name in ("ops-queue", "billing-desk", "access-desk"):
        assert queue_name in page


def test_handoff_requires_api_key(client):
    assert client.get("/api/v1/handoff/queue").status_code == 401
    assert client.get("/api/v1/handoff/tickets/missing").status_code == 401
    assert client.post("/api/v1/handoff/tickets/missing", json={"action": "escalate"}).status_code == 401


def test_queue_lists_tool_names_and_detail_trace(client, auth_headers):
    created = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    assert created.status_code == 201
    ticket_id = created.json()["ticket"]["id"]
    run_id = created.json()["run"]["id"]

    listed = client.get("/api/v1/handoff/queue", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] == 1
    assert body["tickets"][0]["tool_names"] == ["lookup_kb", "get_customer", "update_ticket"]
    assert body["tickets"][0]["assignee"] is None

    detail = client.get(f"/api/v1/handoff/tickets/{ticket_id}", headers=auth_headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["ticket"]["latest_run_id"] == run_id
    assert payload["run"]["tool_calls"][0]["tool"] == "lookup_kb"
    assert payload["n8n_events"] == []
    assert client.get("/api/v1/handoff/tickets/missing", headers=auth_headers).status_code == 404


def test_escalate_assign_and_resolve_do_not_rerun_agent(client, auth_headers, caplog):
    created = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    ticket_id = created.json()["ticket"]["id"]
    run_id = created.json()["run"]["id"]
    note = "note-should-not-be-logged-99"

    with caplog.at_level(logging.INFO):
        escalated = client.post(
            f"/api/v1/handoff/tickets/{ticket_id}",
            json={"action": "escalate", "note": note},
            headers=auth_headers,
        )
    assert escalated.status_code == 200
    assert escalated.json()["action"] == "escalate"
    assert escalated.json()["ticket"]["status"] == "escalated"
    assert escalated.json()["ticket"]["assignee"] == "ops-queue"
    assert escalated.json()["ticket"]["handoff_note"] == note
    assert escalated.json()["ticket"]["latest_run_id"] == run_id
    assert note not in caplog.text
    assert "handoff_updated" in caplog.text

    assigned = client.post(
        f"/api/v1/handoff/tickets/{ticket_id}",
        json={"action": "assign", "assignee": "billing-desk"},
        headers=auth_headers,
    )
    assert assigned.status_code == 200
    assert assigned.json()["ticket"]["assignee"] == "billing-desk"
    assert assigned.json()["ticket"]["status"] == "escalated"
    assert assigned.json()["ticket"]["handoff_note"] == note

    resolved = client.post(
        f"/api/v1/handoff/tickets/{ticket_id}",
        json={"action": "resolve", "assignee": "billing-desk"},
        headers=auth_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["ticket"]["status"] == "resolved"
    assert resolved.json()["ticket"]["latest_run_id"] == run_id

    only = client.get("/api/v1/handoff/queue?status=escalated", headers=auth_headers)
    assert only.json()["count"] == 0


def test_assign_requires_known_queue(client, auth_headers):
    created = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    ticket_id = created.json()["ticket"]["id"]
    missing = client.post(
        f"/api/v1/handoff/tickets/{ticket_id}",
        json={"action": "assign"},
        headers=auth_headers,
    )
    assert missing.status_code == 422
    unknown = client.post(
        f"/api/v1/handoff/tickets/{ticket_id}",
        json={"action": "assign", "assignee": "root"},
        headers=auth_headers,
    )
    assert unknown.status_code == 422
    assert client.post(
        "/api/v1/handoff/tickets/missing",
        json={"action": "escalate"},
        headers=auth_headers,
    ).status_code == 404


def test_assign_reopens_a_resolved_ticket(client, auth_headers):
    created = client.post("/api/v1/tickets", json=BILLING, headers=auth_headers)
    ticket_id = created.json()["ticket"]["id"]
    assert created.json()["ticket"]["status"] == "resolved"
    assigned = client.post(
        f"/api/v1/handoff/tickets/{ticket_id}",
        json={"action": "assign", "assignee": "billing-desk"},
        headers=auth_headers,
    )
    assert assigned.json()["ticket"]["status"] == "in_progress"
    assert assigned.json()["ticket"]["assignee"] == "billing-desk"


def test_old_sqlite_ticket_table_gains_handoff_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tickets (id VARCHAR(36) PRIMARY KEY, subject VARCHAR(200))"))
    ensure_ticket_handoff_columns(engine)
    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tickets)"))}
    assert {"assignee", "handoff_note", "handoff_at"} <= columns


def test_handoff_template_matches_queues():
    page = Path("app/web/handoff.html").read_text(encoding="utf-8")
    assert "Escalate to human" in page
    assert "X-API-Key" in page
