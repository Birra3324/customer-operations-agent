"""Mock knowledge base, CRM, ticket, and Slack tools. No shell and no open network."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.models.entities import Ticket, _utcnow
from app.models.schemas import Channel, Intent, Priority, TicketStatus

log = logging.getLogger("ops.tools")

_TOKEN = re.compile(r"[a-z0-9]+")


class ToolError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TransientToolError(ToolError):
    def __init__(self) -> None:
        super().__init__("transient_failure")


class LookupKbArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)


class GetCustomerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str = Field(min_length=1, max_length=64)


class CreateTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    customer_id: str | None = Field(default=None, max_length=64)
    channel: Channel = "email"


class UpdateTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str = Field(min_length=1, max_length=36)
    intent: Intent
    priority: Priority
    status: TicketStatus


class NotifySlackArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: str = "#vision-ops-alerts"
    intent: Intent
    priority: Priority


@dataclass
class ToolContext:
    db: Any
    ticket_id: str | None = None
    simulate_flake: bool = False
    flake_used: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    fn: Callable[[ToolContext, BaseModel], dict]


REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> None:
    REGISTRY[spec.name] = spec


def fixtures_root() -> Path:
    raw = Path(get_settings().fixtures_dir)
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    return raw


@lru_cache
def _load_json(name: str) -> dict:
    path = fixtures_root() / name
    return json.loads(path.read_text(encoding="utf-8"))


def clear_fixture_cache() -> None:
    _load_json.cache_clear()


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if len(token) >= 3}


def lookup_kb(ctx: ToolContext, args: LookupKbArgs) -> dict:
    """Local article search. Fails once per run when the flake simulation is on."""
    if ctx.simulate_flake and not ctx.flake_used:
        ctx.flake_used = True
        raise TransientToolError()
    payload = _load_json("kb.json")
    query_tokens = _tokens(args.query)
    ranked: list[tuple[int, dict]] = []
    for article in payload["articles"]:
        haystack = " ".join(
            [
                article.get("title", ""),
                article.get("body", ""),
                " ".join(article.get("tags", [])),
            ]
        )
        score = len(query_tokens & _tokens(haystack))
        if score:
            ranked.append((score, article))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    articles = [
        {
            "id": article["id"],
            "title": article["title"],
            "excerpt": article["body"][:320],
        }
        for _, article in ranked[:2]
    ]
    return {"articles": articles, "match_count": len(articles)}


def get_customer(ctx: ToolContext, args: GetCustomerArgs) -> dict:
    """CRM lookup. Email stays in the fixture file and is not returned."""
    del ctx
    payload = _load_json("crm.json")
    for row in payload["customers"]:
        if row["customer_id"] == args.customer_id:
            return {
                "found": True,
                "customer_id": row["customer_id"],
                "name": row["name"],
                "company": row["company"],
                "plan": row["plan"],
                "region": row["region"],
                "vip": bool(row.get("vip", False)),
            }
    return {"found": False, "customer_id": args.customer_id}


def create_ticket(ctx: ToolContext, args: CreateTicketArgs) -> dict:
    if ctx.db is None:
        raise ToolError("database_unavailable")
    row = Ticket(
        subject=args.subject,
        body=args.body,
        customer_id=args.customer_id,
        channel=args.channel,
        status="open",
    )
    ctx.db.add(row)
    ctx.db.flush()
    return {"ticket_id": row.id, "status": row.status}


def update_ticket(ctx: ToolContext, args: UpdateTicketArgs) -> dict:
    if ctx.db is None:
        raise ToolError("database_unavailable")
    if ctx.ticket_id and args.ticket_id != ctx.ticket_id:
        raise ToolError("ticket_mismatch")
    row = ctx.db.get(Ticket, args.ticket_id)
    if row is None:
        raise ToolError("ticket_not_found")
    row.intent = args.intent
    row.priority = args.priority
    row.status = args.status
    row.updated_at = _utcnow()
    ctx.db.flush()
    return {
        "ticket_id": row.id,
        "intent": row.intent,
        "priority": row.priority,
        "status": row.status,
    }


def notify_slack(ctx: ToolContext, args: NotifySlackArgs) -> dict:
    """Post a metadata-only line, or log when SLACK_WEBHOOK_URL is unset."""
    allowed = (get_settings().slack_channel or "#vision-ops-alerts").strip()
    if args.channel != allowed:
        raise ToolError("channel_not_allowed")
    # Planner-supplied prose is ignored. The payload is ticket metadata only.
    text = (
        f"ticket_id={ctx.ticket_id or 'unknown'} "
        f"intent={args.intent} priority={args.priority}"
    )
    webhook = get_settings().slack_webhook_url
    if not webhook:
        log.info("slack_skipped reason=webhook_unset channel=%s", args.channel)
        return {"delivered": False, "mode": "logged", "channel": args.channel}
    try:
        response = httpx.post(webhook, json={"text": text}, timeout=5.0)
        response.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL):
        log.info("slack_failed channel=%s", args.channel)
        return {"delivered": False, "mode": "error", "channel": args.channel}
    log.info("slack_delivered channel=%s", args.channel)
    return {"delivered": True, "mode": "webhook", "channel": args.channel}


register(ToolSpec("lookup_kb", LookupKbArgs, lookup_kb))
register(ToolSpec("get_customer", GetCustomerArgs, get_customer))
register(ToolSpec("create_ticket", CreateTicketArgs, create_ticket))
register(ToolSpec("update_ticket", UpdateTicketArgs, update_ticket))
register(ToolSpec("notify_slack", NotifySlackArgs, notify_slack))


def known_tool_names() -> frozenset[str]:
    return frozenset(REGISTRY)
