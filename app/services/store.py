"""Load and shape ticket and run records for the API."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.models.entities import AgentRun, Ticket
from app.models.schemas import AgentRunOut, TicketCreate, TicketOut

log = logging.getLogger("ops.store")


def add_ticket(db: Session, payload: TicketCreate) -> Ticket:
    ticket = Ticket(
        subject=payload.subject,
        body=payload.body,
        customer_id=payload.customer_id,
        channel=payload.channel,
        status="open",
    )
    db.add(ticket)
    db.flush()
    log.info("ticket_accepted channel=%s", ticket.channel)
    return ticket


def run_for_ticket(db: Session, ticket: Ticket) -> AgentRun:
    return run_agent(db, ticket)


def get_ticket(db: Session, ticket_id: str) -> Ticket | None:
    return db.get(Ticket, ticket_id)


def list_tickets(db: Session, limit: int) -> list[Ticket]:
    return (
        db.query(Ticket)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(limit)
        .all()
    )


def get_run(db: Session, run_id: str) -> AgentRun | None:
    return db.get(AgentRun, run_id)


def latest_run(db: Session, ticket_id: str) -> AgentRun | None:
    return (
        db.query(AgentRun)
        .filter(AgentRun.ticket_id == ticket_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .first()
    )


def ticket_out(db: Session, ticket: Ticket) -> TicketOut:
    latest = latest_run(db, ticket.id)
    return TicketOut(
        id=ticket.id,
        subject=ticket.subject,
        body=ticket.body,
        customer_id=ticket.customer_id,
        channel=ticket.channel,
        intent=ticket.intent,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        latest_run_id=latest.id if latest else None,
    )


def run_out(run: AgentRun) -> AgentRunOut:
    return AgentRunOut(
        id=run.id,
        ticket_id=run.ticket_id,
        provider=run.provider,
        status=run.status,
        plan=run.plan,
        tool_calls=run.tool_calls,
        final_reply=run.final_reply,
        ticket_status=run.ticket_status,
        intent=run.intent,
        priority=run.priority,
        rounds=run.rounds,
        fallback=run.fallback,
        request_id=run.request_id,
        created_at=run.created_at,
    )
