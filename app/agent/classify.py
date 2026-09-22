"""Offline intent and priority labels for the heuristic planner."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import Intent, Priority, TicketStatus

KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "escalation": (
        "escalate",
        "human",
        "a person",
        "manager",
        "outage",
        "sev-1",
        "sev1",
        "ops queue",
        "legal",
    ),
    "password_reset": (
        "password",
        "forgot",
        "sign in",
        "signin",
        "login",
        "locked out",
        "mfa",
        "reset email",
    ),
    "billing": (
        "invoice",
        "billing",
        "charged",
        "charge",
        "refund",
        "payment",
        "receipt",
    ),
}

PRIORITY: dict[Intent, Priority] = {
    "escalation": "urgent",
    "password_reset": "high",
    "billing": "medium",
    "general": "low",
}

STATUS_FOR: dict[Intent, TicketStatus] = {
    "escalation": "escalated",
    "password_reset": "resolved",
    "billing": "resolved",
    "general": "waiting_customer",
}


@dataclass(frozen=True)
class Classification:
    intent: Intent
    priority: Priority
    status: TicketStatus


def classify(subject: str, body: str) -> Classification:
    text = f"{subject}\n{body}".lower()
    scores = {intent: sum(1 for word in words if word in text) for intent, words in KEYWORDS.items()}
    best: Intent = max(scores, key=lambda name: scores[name])  # type: ignore[assignment]
    if scores[best] == 0:
        best = "general"
    priority = PRIORITY[best]
    if best == "billing" and any(word in text for word in ("urgent", "overcharged", "asap")):
        priority = "high"
    return Classification(intent=best, priority=priority, status=STATUS_FOR[best])


def should_notify(classification: Classification) -> bool:
    return classification.priority in {"high", "urgent"} or classification.intent == "escalation"
