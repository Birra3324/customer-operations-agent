"""Pydantic request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Channel = Literal["email", "chat", "portal", "slack"]
Intent = Literal["billing", "password_reset", "escalation", "general"]
Priority = Literal["low", "medium", "high", "urgent"]
TicketStatus = Literal["open", "in_progress", "waiting_customer", "resolved", "escalated"]


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
