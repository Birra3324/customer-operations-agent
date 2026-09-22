"""Ticket and agent-run tables. UUID ids, JSON plan and tool trace."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="email")
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", index=True)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handoff_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    plan: Mapped[list] = mapped_column(JSON, nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSON, nullable=False)
    final_reply: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ticket_status: Mapped[str] = mapped_column(String(40), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class IntegrationEvent(Base):
    """n8n bridge receipt. Stores ids and a short note, not a copy of the ticket body."""

    __tablename__ = "integration_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="n8n")
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow: Mapped[str] = mapped_column(String(80), nullable=False)
    ticket_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tickets.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(220), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
