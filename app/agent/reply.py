"""Customer-facing reply built only from tool results already on the trace."""

from __future__ import annotations

from app.agent.classify import Classification


def _first_name(customer: dict | None) -> str:
    if not customer or not customer.get("found"):
        return "there"
    name = str(customer.get("name") or "").strip()
    return name.split()[0] if name else "there"


def _article(kb: dict | None) -> dict | None:
    articles = (kb or {}).get("articles") or []
    if not articles:
        return None
    return articles[0]


def compose_reply(
    classification: Classification,
    kb: dict | None,
    customer: dict | None,
) -> str:
    who = _first_name(customer)
    plan_bit = ""
    if customer and customer.get("found"):
        plan_bit = f" I see {customer['company']} is on {customer['plan']}."
        if customer.get("vip") and classification.intent == "escalation":
            plan_bit += " This is a VIP workspace contact."
    article = _article(kb)
    excerpt = article["excerpt"] if article else "I could not find a matching help article."
    if classification.intent == "escalation":
        return (
            f"Hi {who},{plan_bit} I escalated this to the on-call ops queue. {excerpt}"
        )
    if classification.intent == "password_reset":
        return (
            f"Hi {who},{plan_bit} Here is the password reset path from our notes. {excerpt}"
        )
    if classification.intent == "billing":
        return f"Hi {who},{plan_bit} Here is what our billing notes say. {excerpt}"
    return (
        f"Hi {who},{plan_bit} I need a little more detail before I can close this. {excerpt}"
    )
