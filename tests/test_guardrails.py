import json
import logging
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.core.config import get_settings
from app.models.entities import Ticket
from app.tools import ToolContext
from app.tools.executor import execute_tool
from app.tools.retry import sleep_backoff


def test_slack_channel_is_allowlisted(db_session):
    record = execute_tool(
        "notify_slack",
        {"channel": "#random", "intent": "billing", "priority": "low"},
        ToolContext(db=db_session, ticket_id="ticket-1"),
    )
    assert record["ok"] is False
    assert record["error"] == "channel_not_allowed"


def test_shell_and_widened_allowlist_never_execute(db_session):
    blocked = execute_tool("shell", {"cmd": "id"}, ToolContext(db=db_session))
    assert blocked["ok"] is False
    assert blocked["error"] == "tool_not_allowed"

    previous = get_settings().allowed_tools
    get_settings().allowed_tools = "shell,lookup_kb"
    try:
        still_blocked = execute_tool("shell", {"cmd": "id"}, ToolContext(db=db_session))
    finally:
        get_settings().allowed_tools = previous
    assert still_blocked["error"] == "tool_not_allowed"


def test_extra_arguments_rejected(db_session):
    record = execute_tool(
        "lookup_kb",
        {"query": "invoice", "url": "http://evil.example"},
        ToolContext(db=db_session),
    )
    assert record["ok"] is False
    assert record["error"] == "invalid_arguments"


def test_update_cannot_target_another_ticket(db_session):
    first = Ticket(subject="One", body="Invoice question about a charge", status="open")
    second = Ticket(subject="Two", body="Another invoice charge", status="open")
    db_session.add_all([first, second])
    db_session.flush()
    record = execute_tool(
        "update_ticket",
        {
            "ticket_id": second.id,
            "intent": "billing",
            "priority": "medium",
            "status": "resolved",
        },
        ToolContext(db=db_session, ticket_id=first.id),
    )
    assert record["error"] == "ticket_mismatch"
    assert second.status == "open"


def test_create_ticket_tool(db_session):
    record = execute_tool(
        "create_ticket",
        {
            "subject": "New TraceLight question",
            "body": "What does AlertMesh Starter include?",
            "customer_id": "cust-2088",
            "channel": "email",
        },
        ToolContext(db=db_session),
    )
    assert record["ok"] is True
    assert record["result"]["status"] == "open"
    stored = db_session.get(Ticket, record["result"]["ticket_id"])
    assert stored is not None
    assert stored.subject == "New TraceLight question"


def test_flaky_lookup_retries(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "simulate_flaky_tool", True)
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate TraceLight invoice",
            "body": "We were charged twice for the September invoice.",
            "customer_id": "cust-1042",
            "channel": "email",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    lookup = response.json()["run"]["tool_calls"][0]
    assert lookup["tool"] == "lookup_kb"
    assert lookup["ok"] is True
    assert lookup["attempts"] == 2
    assert response.json()["run"]["status"] == "completed"


def test_allowlist_blocks_lookup(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_tools", "get_customer,update_ticket,notify_slack")
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate TraceLight invoice",
            "body": "We were charged twice for the September invoice.",
            "customer_id": "cust-1042",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    lookup = response.json()["run"]["tool_calls"][0]
    assert lookup["tool"] == "lookup_kb"
    assert lookup["ok"] is False
    assert lookup["error"] == "tool_not_allowed"
    assert response.json()["run"]["status"] == "completed"


def test_max_tool_rounds(client, auth_headers, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_tool_rounds", 1)
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Duplicate TraceLight invoice",
            "body": "We were charged twice for the September invoice.",
            "customer_id": "cust-1042",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    run = response.json()["run"]
    assert run["status"] == "needs_review"
    assert run["rounds"] == 1
    assert len(run["tool_calls"]) == 1
    assert "max tool rounds" in run["final_reply"]


def test_backoff_skips_sleep_in_tests():
    with patch("app.tools.retry.time.sleep") as slept:
        delay = sleep_backoff(2)
    slept.assert_not_called()
    assert delay == pytest.approx(0.4)


def test_backoff_sleeps_outside_tests(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "tool_retry_base_seconds", 0.2)
    with patch("app.tools.retry.time.sleep") as slept:
        delay = sleep_backoff(3)
    assert delay == pytest.approx(0.8)
    slept.assert_called_once()
    assert slept.call_args[0][0] == pytest.approx(0.8)


def test_logs_omit_pii(client, auth_headers, caplog):
    crm = json.loads(Path("data/crm.json").read_text(encoding="utf-8"))
    emails = [row["email"] for row in crm["customers"]]
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/tickets",
            json={
                "subject": "Duplicate TraceLight invoice",
                "body": "We were charged twice for the September invoice.",
                "customer_id": "cust-1042",
                "channel": "email",
            },
            headers=auth_headers,
        )
    assert response.status_code == 201
    for email in emails:
        assert email not in caplog.text
    assert "Duplicate TraceLight invoice" not in caplog.text
    assert "charged twice" not in caplog.text


def test_slack_payload_has_no_customer_text(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "slack_webhook_url",
        "https://hooks.slack.example/services/not-a-real-hook",
    )
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["json"] = kwargs.get("json")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.tools.httpx.post", fake_post)
    response = client.post(
        "/api/v1/tickets",
        json={
            "subject": "Need a human — TraceLight workspace is down",
            "body": "Please escalate to a person on the ops queue. priya.shah@kite.example",
            "customer_id": "cust-3301",
            "channel": "portal",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    text = seen["json"]["text"]
    assert "priya.shah" not in text
    assert "Priya" not in text
    assert "workspace is down" not in text
    assert "intent=escalation" in text
    assert "priority=urgent" in text
