"""Human handoff updates. Does not call the planner or any tool."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.entities import IntegrationEvent, Ticket, _utcnow
from app.models.schemas import (
    HandoffDetail,
    HandoffIn,
    HandoffQueue,
    HandoffSummary,
    N8nEventOut,
    TicketStatus,
)
from app.services.store import get_ticket, latest_run, run_out, ticket_out

log = logging.getLogger("ops.handoff")


def _tool_names(db: Session, ticket_id: str) -> tuple[str | None, list[str]]:
    run = latest_run(db, ticket_id)
    if run is None:
        return None, []
    names = [str(call.get("tool")) for call in (run.tool_calls or []) if isinstance(call, dict)]
    return run.id, names


def summarize(db: Session, ticket: Ticket) -> HandoffSummary:
    run_id, names = _tool_names(db, ticket.id)
    return HandoffSummary(
        id=ticket.id,
        subject=ticket.subject,
        customer_id=ticket.customer_id,
        channel=ticket.channel,
        intent=ticket.intent,
        priority=ticket.priority,
        status=ticket.status,
        assignee=ticket.assignee,
        handoff_note=ticket.handoff_note,
        handoff_at=ticket.handoff_at,
        latest_run_id=run_id,
        tool_names=names,
    )


def queue(db: Session, limit: int, status: TicketStatus | None) -> HandoffQueue:
    query = db.query(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc())
    if status is not None:
        query = query.filter(Ticket.status == status)
    rows = query.limit(limit).all()
    return HandoffQueue(tickets=[summarize(db, row) for row in rows], count=len(rows))


def detail(db: Session, ticket: Ticket) -> HandoffDetail:
    run = latest_run(db, ticket.id)
    events = (
        db.query(IntegrationEvent)
        .filter(IntegrationEvent.ticket_id == ticket.id)
        .order_by(IntegrationEvent.created_at.desc(), IntegrationEvent.id.desc())
        .limit(10)
        .all()
    )
    return HandoffDetail(
        ticket=ticket_out(db, ticket),
        run=run_out(run) if run else None,
        n8n_events=[event_out(event) for event in events],
    )


def apply_handoff(db: Session, ticket: Ticket, payload: HandoffIn) -> Ticket:
    if payload.action == "escalate":
        ticket.status = "escalated"
        ticket.assignee = payload.assignee or "ops-queue"
    elif payload.action == "assign":
        ticket.assignee = payload.assignee
        if ticket.status != "escalated":
            ticket.status = "in_progress"
    elif payload.action == "resolve":
        ticket.status = "resolved"
        if payload.assignee:
            ticket.assignee = payload.assignee
    if payload.note is not None:
        ticket.handoff_note = payload.note
    ticket.handoff_at = _utcnow()
    ticket.updated_at = ticket.handoff_at
    db.commit()
    db.refresh(ticket)
    log.info(
        "handoff_updated action=%s assignee=%s status=%s",
        payload.action,
        ticket.assignee or "-",
        ticket.status,
    )
    return ticket


def event_out(event: IntegrationEvent) -> N8nEventOut:
    return N8nEventOut(
        id=event.id,
        source=event.source,
        event=event.event,
        external_id=event.external_id,
        workflow=event.workflow,
        ticket_id=event.ticket_id,
        status=event.status,
        note=event.note,
        created_at=event.created_at,
    )


def require_ticket(db: Session, ticket_id: str) -> Ticket | None:
    return get_ticket(db, ticket_id)
