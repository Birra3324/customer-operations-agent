"""Planner role: heuristic state machine or one-step LLM JSON decisions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from app.agent.classify import Classification, classify, should_notify
from app.agent.reply import compose_reply
from app.core.config import get_settings
from app.models.entities import Ticket
from app.services.llm import complete, parse_json_object

log = logging.getLogger("ops.planner")


@dataclass
class Decision:
    thought: str
    action: str
    tool: str | None = None
    arguments: dict = field(default_factory=dict)
    final_reply: str | None = None


class LlmDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    thought: str
    action: str
    tool: str | None = None
    arguments: dict = {}
    final_reply: str | None = None


def _seen(history: list[dict], name: str) -> bool:
    return any(item.get("tool") == name for item in history)


def _ok_result(history: list[dict], name: str) -> dict | None:
    for item in history:
        if item.get("tool") == name and item.get("ok"):
            return item.get("result") or {}
    return None


class HeuristicPlanner:
    """Deterministic planner. Each call returns the next tool or the final reply."""

    def next(self, ticket: Ticket, history: list[dict]) -> Decision:
        classification = classify(ticket.subject, ticket.body)
        if not _seen(history, "lookup_kb"):
            query = f"{ticket.subject}. {ticket.body}"[:500]
            return Decision(
                thought="Look up Vision AI Ops notes before answering.",
                action="tool",
                tool="lookup_kb",
                arguments={"query": query},
            )
        if ticket.customer_id and not _seen(history, "get_customer"):
            return Decision(
                thought="Load the CRM profile so the reply names the workspace plan.",
                action="tool",
                tool="get_customer",
                arguments={"customer_id": ticket.customer_id},
            )
        if not _seen(history, "update_ticket"):
            return Decision(
                thought="Write intent, priority, and status onto the ticket.",
                action="tool",
                tool="update_ticket",
                arguments={
                    "ticket_id": ticket.id,
                    "intent": classification.intent,
                    "priority": classification.priority,
                    "status": classification.status,
                },
            )
        if should_notify(classification) and not _seen(history, "notify_slack"):
            return Decision(
                thought="Notify the ops channel because this is high priority or needs a human.",
                action="tool",
                tool="notify_slack",
                arguments={
                    "channel": get_settings().slack_channel or "#vision-ops-alerts",
                    "intent": classification.intent,
                    "priority": classification.priority,
                },
            )
        return Decision(
            thought="Draft the customer reply from the knowledge base and CRM results.",
            action="final",
            final_reply=compose_reply(
                classification,
                _ok_result(history, "lookup_kb"),
                _ok_result(history, "get_customer"),
            ),
        )


class LlmPlanner:
    """Ask a remote model for the next JSON action. Fall back to the heuristic planner."""

    def __init__(self) -> None:
        self.used_fallback = False
        self._heuristic = HeuristicPlanner()

    def next(self, ticket: Ticket, history: list[dict]) -> Decision:
        if self.used_fallback:
            return self._heuristic.next(ticket, history)
        try:
            return self._remote_next(ticket, history)
        except Exception as exc:  # noqa: BLE001 — a dead model must not fail the ticket
            self.used_fallback = True
            log.warning("llm_fallback error_type=%s", type(exc).__name__)
            return self._heuristic.next(ticket, history)

    def _remote_next(self, ticket: Ticket, history: list[dict]) -> Decision:
        messages = _messages(ticket, history)
        raw = complete(messages)
        data = parse_json_object(raw)
        parsed = LlmDecision.model_validate(data)
        action = parsed.action.strip().lower()
        if action == "final":
            reply = (parsed.final_reply or "").strip()
            if not reply:
                raise ValueError("empty final reply")
            return Decision(
                thought=parsed.thought[:500],
                action="final",
                final_reply=reply[:4000],
            )
        if action != "tool" or not parsed.tool:
            raise ValueError("planner action was not tool or final")
        return Decision(
            thought=parsed.thought[:500],
            action="tool",
            tool=parsed.tool.strip().lower(),
            arguments=parsed.arguments,
        )


def _messages(ticket: Ticket, history: list[dict]) -> list[dict[str, str]]:
    tool_list = "lookup_kb, get_customer, create_ticket, update_ticket, notify_slack"
    system = (
        "You are the planner for a Vision AI Ops customer operations agent. "
        "Reply with ONLY JSON: "
        '{"thought":"short","action":"tool"|"final","tool":"name or null",'
        '"arguments":{},"final_reply":"string or null"}. '
        f"Tools you may name: {tool_list}. "
        "Never request shell, filesystem, or arbitrary HTTP. "
        "lookup_kb arguments: {query}. get_customer arguments: {customer_id}. "
        "update_ticket arguments: {ticket_id, intent, priority, status} where "
        "intent is billing|password_reset|escalation|general, "
        "priority is low|medium|high|urgent, "
        "status is open|in_progress|waiting_customer|resolved|escalated. "
        "notify_slack arguments: {channel, intent, priority} and channel must be "
        "#vision-ops-alerts. Use tools before the final reply."
    )
    summary = [
        {
            "tool": item.get("tool"),
            "ok": item.get("ok"),
            "error": item.get("error"),
            "result": item.get("result"),
        }
        for item in history
    ]
    user = (
        f"ticket_id={ticket.id}\n"
        f"channel={ticket.channel}\n"
        f"customer_id={ticket.customer_id or 'none'}\n"
        f"subject={ticket.subject}\n"
        f"body={ticket.body}\n"
        f"tool_history={summary}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def classification_for(ticket: Ticket) -> Classification:
    return classify(ticket.subject, ticket.body)
