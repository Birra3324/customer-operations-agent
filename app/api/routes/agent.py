"""Run the agent for a new or existing ticket."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.database import get_db
from app.models.schemas import AgentRunIn, AgentRunOut, TicketCreate
from app.services.store import add_ticket, get_ticket, run_for_ticket, run_out

router = APIRouter(tags=["agent"], dependencies=[Depends(require_api_key)])


@router.post("/api/v1/agent/run", response_model=AgentRunOut)
def run_agent_endpoint(payload: AgentRunIn, db: Session = Depends(get_db)) -> AgentRunOut:
    if payload.ticket_id:
        ticket = get_ticket(db, payload.ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
    else:
        ticket = add_ticket(
            db,
            TicketCreate(
                subject=payload.subject or "",
                body=payload.body or "",
                customer_id=payload.customer_id,
                channel=payload.channel,
            ),
        )
    run = run_for_ticket(db, ticket)
    return run_out(run)
