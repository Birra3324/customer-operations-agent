"""Create a ticket and run the operations agent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.db.database import get_db
from app.models.schemas import TicketCreate, TicketCreated, TicketList, TicketOut
from app.services.store import add_ticket, get_ticket, list_tickets, run_for_ticket, run_out, ticket_out

router = APIRouter(tags=["tickets"], dependencies=[Depends(require_api_key)])


@router.post("/api/v1/tickets", response_model=TicketCreated, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> TicketCreated:
    ticket = add_ticket(db, payload)
    run = run_for_ticket(db, ticket)
    rid = getattr(request.state, "request_id", None) or get_request_id()
    return TicketCreated(ticket=ticket_out(db, ticket), run=run_out(run), request_id=rid)


@router.get("/api/v1/tickets", response_model=TicketList)
def get_tickets(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> TicketList:
    rows = list_tickets(db, limit)
    return TicketList(tickets=[ticket_out(db, row) for row in rows], count=len(rows))


@router.get("/api/v1/tickets/{ticket_id}", response_model=TicketOut)
def get_one_ticket(ticket_id: str, db: Session = Depends(get_db)) -> TicketOut:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket_out(db, ticket)
