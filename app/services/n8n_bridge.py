"""n8n inbound ticket events and status callbacks.

The workflow JSON calls these routes with OPS_AGENT_URL and OPS_AGENT_API_KEY
from the n8n environment. Those values are not stored on the event row.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.entities import AgentRun, IntegrationEvent, Ticket
from app.models.schemas import N8nEventList, N8nInbound, N8nStatusIn, TicketCreate
from app.services.handoff import event_out
from app.services.store import add_ticket, get_ticket, latest_run, run_for_ticket

log = logging.getLogger("ops.n8n")


def _dedupe_key(external_id: str) -> str:
    return f"n8n:ticket.created:{external_id}"


def accept_inbound(db: Session, payload: N8nInbound) -> tuple[Ticket, AgentRun, bool]:
    if payload.external_id:
        existing = (
            db.query(IntegrationEvent)
            .filter(IntegrationEvent.dedupe_key == _dedupe_key(payload.external_id))
            .one_or_none()
        )
        if existing is not None and existing.ticket_id:
            ticket = get_ticket(db, existing.ticket_id)
            run = latest_run(db, existing.ticket_id) if ticket else None
            if ticket is not None and run is not None:
                log.info("n8n_inbound idempotent=true channel=%s", ticket.channel)
                return ticket, run, True

    ticket = add_ticket(
        db,
        TicketCreate(
            subject=payload.subject,
            body=payload.body,
            customer_id=payload.customer_id,
            channel=payload.channel,
        ),
    )
    run = run_for_ticket(db, ticket)
    event = IntegrationEvent(
        source="n8n",
        event="ticket.created",
        external_id=payload.external_id,
        workflow=payload.workflow,
        ticket_id=ticket.id,
        status="accepted",
        note=None,
        dedupe_key=_dedupe_key(payload.external_id) if payload.external_id else None,
    )
    db.add(event)
    db.commit()
    log.info("n8n_inbound idempotent=false channel=%s", ticket.channel)
    return ticket, run, False


def record_status(db: Session, payload: N8nStatusIn) -> IntegrationEvent | None:
    ticket = get_ticket(db, payload.ticket_id)
    if ticket is None:
        return None
    event = IntegrationEvent(
        source="n8n",
        event="status.posted",
        external_id=payload.external_id,
        workflow=payload.workflow,
        ticket_id=ticket.id,
        status=payload.status,
        note=payload.note,
        dedupe_key=None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info("n8n_status workflow=%s status=%s", payload.workflow, payload.status)
    return event


def list_events(db: Session, limit: int) -> N8nEventList:
    rows = (
        db.query(IntegrationEvent)
        .filter(IntegrationEvent.source == "n8n")
        .order_by(IntegrationEvent.created_at.desc(), IntegrationEvent.id.desc())
        .limit(limit)
        .all()
    )
    return N8nEventList(events=[event_out(row) for row in rows], count=len(rows))
