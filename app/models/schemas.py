"""Pydantic request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Channel = Literal["email", "chat", "portal", "slack"]
Intent = Literal["billing", "password_reset", "escalation", "general"]
Priority = Literal["low", "medium", "high", "urgent"]
TicketStatus = Literal["open", "in_progress", "waiting_customer", "resolved", "escalated"]
Assignee = Literal["ops-queue", "billing-desk", "access-desk"]
HandoffAction = Literal["escalate", "assign", "resolve"]
N8nBridgeStatus = Literal["posted", "failed", "skipped"]


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    customer_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    channel: Channel = "email"


class AgentRunIn(BaseModel):
    ticket_id: str | None = Field(default=None, max_length=36)
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=8000)
    customer_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    channel: Channel = "email"

    @model_validator(mode="after")
    def need_target(self) -> AgentRunIn:
        if self.ticket_id:
            return self
        if self.subject and self.body:
            return self
        raise ValueError("Provide ticket_id or both subject and body")


class PlanStep(BaseModel):
    round: int
    actor: Literal["planner", "executor"]
    thought: str
    action: str
    tool: str | None = None


class ToolCallOut(BaseModel):
    tool: str
    arguments: dict
    ok: bool
    attempts: int
    result: dict | None = None
    error: str | None = None


class AgentRunOut(BaseModel):
    id: str
    ticket_id: str
    provider: str
    status: str
    plan: list[PlanStep]
    tool_calls: list[ToolCallOut]
    final_reply: str
    ticket_status: str
    intent: str | None
    priority: str | None
    rounds: int
    fallback: str | None = None
    request_id: str | None = None
    created_at: datetime


class TicketOut(BaseModel):
    id: str
    subject: str
    body: str
    customer_id: str | None
    channel: str
    intent: str | None
    priority: str | None
    status: str
    assignee: str | None = None
    handoff_note: str | None = None
    handoff_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    latest_run_id: str | None = None


class TicketCreated(BaseModel):
    ticket: TicketOut
    run: AgentRunOut
    request_id: str


class TicketList(BaseModel):
    tickets: list[TicketOut]
    count: int


class HealthOut(BaseModel):
    ok: bool
    status: str
    db: bool
    ai_provider: str
    model: str
    ollama: bool | None = None


class HandoffIn(BaseModel):
    action: HandoffAction
    assignee: Assignee | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check_action(self) -> "HandoffIn":
        if self.note is not None:
            self.note = self.note.strip() or None
        if self.action == "escalate" and self.assignee is None:
            self.assignee = "ops-queue"
        if self.action == "assign" and self.assignee is None:
            raise ValueError("assign requires assignee")
        return self


class HandoffSummary(BaseModel):
    id: str
    subject: str
    customer_id: str | None
    channel: str
    intent: str | None
    priority: str | None
    status: str
    assignee: str | None
    handoff_note: str | None
    handoff_at: datetime | None
    latest_run_id: str | None
    tool_names: list[str]


class HandoffQueue(BaseModel):
    tickets: list[HandoffSummary]
    count: int


class N8nEventOut(BaseModel):
    id: str
    source: str
    event: str
    external_id: str | None
    workflow: str
    ticket_id: str | None
    status: str
    note: str | None
    created_at: datetime


class HandoffDetail(BaseModel):
    ticket: TicketOut
    run: AgentRunOut | None
    n8n_events: list[N8nEventOut]


class HandoffResult(BaseModel):
    action: str
    ticket: TicketOut


class N8nInbound(BaseModel):
    event: Literal["ticket.created"]
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    customer_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    channel: Channel = "portal"
    external_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    workflow: str = Field(default="vision-ops-ticket-bridge", max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")


class N8nInboundOut(BaseModel):
    accepted: bool
    idempotent: bool
    event: str
    external_id: str | None
    workflow: str
    ticket: TicketOut
    run: AgentRunOut


class N8nStatusIn(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=36)
    workflow: str = Field(default="vision-ops-ticket-bridge", max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    status: N8nBridgeStatus
    external_id: str | None = Field(default=None, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def strip_note(self) -> "N8nStatusIn":
        if self.note is not None:
            self.note = self.note.strip() or None
        return self


class N8nEventList(BaseModel):
    events: list[N8nEventOut]
    count: int
