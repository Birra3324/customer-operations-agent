import json
from pathlib import Path

CRM_EMAIL = "lena.ortiz@harborline.example"


def _scenarios():
    return json.loads(Path("evals/scenarios.json").read_text(encoding="utf-8"))


def test_examples_match_scenarios():
    demos = json.loads(Path("examples/demo_requests.json").read_text(encoding="utf-8"))
    tickets = [scenario["ticket"] for scenario in _scenarios()]
    assert tickets == demos


def test_billing_run_records_tool_calls(client, auth_headers):
    scenario = _scenarios()[0]
    response = client.post("/api/v1/tickets", json=scenario["ticket"], headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    run = body["run"]
    tools = [call["tool"] for call in run["tool_calls"]]
    assert tools == ["lookup_kb", "get_customer", "update_ticket"]
    assert all(call["ok"] for call in run["tool_calls"])
    actors = {step["actor"] for step in run["plan"]}
    assert actors == {"planner", "executor"}
    kb = run["tool_calls"][0]["result"]
    assert kb["articles"][0]["id"] == "kb-billing-invoices"
    customer = run["tool_calls"][1]["result"]
    assert customer["found"] is True
    assert customer["company"] == "Harborline Logistics"
    assert "email" not in customer
    assert CRM_EMAIL not in response.text
    assert run["intent"] == "billing"
    assert run["priority"] == "medium"
    assert run["ticket_status"] == "resolved"
    assert run["status"] == "completed"
    assert run["provider"] == "heuristic"
    assert body["ticket"]["id"] == run["ticket_id"]
    assert body["ticket"]["latest_run_id"] == run["id"]
    assert "x-request-id" in response.headers


def test_get_ticket_and_run(client, auth_headers):
    created = client.post(
        "/api/v1/tickets",
        json=_scenarios()[1]["ticket"],
        headers=auth_headers,
    )
    assert created.status_code == 201
    ticket_id = created.json()["ticket"]["id"]
    run_id = created.json()["run"]["id"]

    ticket = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers)
    assert ticket.status_code == 200
    assert ticket.json()["intent"] == "password_reset"
    assert ticket.json()["status"] == "resolved"
    assert ticket.json()["latest_run_id"] == run_id

    run = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert run.status_code == 200
    names = [call["tool"] for call in run.json()["tool_calls"]]
    assert "notify_slack" in names
    slack = next(call for call in run.json()["tool_calls"] if call["tool"] == "notify_slack")
    assert slack["ok"] is True
    assert slack["result"]["mode"] == "logged"
    assert "30 minutes" in run.json()["final_reply"]


def test_list_and_missing(client, auth_headers):
    client.post("/api/v1/tickets", json=_scenarios()[0]["ticket"], headers=auth_headers)
    listed = client.get("/api/v1/tickets", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert client.get("/api/v1/tickets/missing", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/runs/missing", headers=auth_headers).status_code == 404


def test_agent_run_creates_and_reruns(client, auth_headers):
    first = client.post(
        "/api/v1/agent/run",
        json=_scenarios()[2]["ticket"],
        headers=auth_headers,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["intent"] == "escalation"
    assert body["ticket_status"] == "escalated"
    assert "VIP workspace" in body["final_reply"]
    assert any(call["tool"] == "notify_slack" and call["ok"] for call in body["tool_calls"])

    second = client.post(
        "/api/v1/agent/run",
        json={"ticket_id": body["ticket_id"]},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] != body["id"]
    assert second.json()["ticket_id"] == body["ticket_id"]
    missing = client.post(
        "/api/v1/agent/run",
        json={"ticket_id": "does-not-exist"},
        headers=auth_headers,
    )
    assert missing.status_code == 404


def test_unknown_customer_still_answers(client, auth_headers):
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate invoice on TraceLight",
            "body": "Which charge is the real September invoice?",
            "customer_id": "cust-missing",
            "channel": "email",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    customer = response.json()["run"]["tool_calls"][1]["result"]
    assert customer["found"] is False
    assert "Hi there" in response.json()["run"]["final_reply"]
