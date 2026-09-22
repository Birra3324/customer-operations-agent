"""Human handoff queue. The HTML page is public; the JSON routes require the API key."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.database import get_db
from app.models.schemas import HandoffDetail, HandoffIn, HandoffQueue, HandoffResult, TicketStatus
from app.services.handoff import apply_handoff, detail, queue, require_ticket
from app.services.store import ticket_out

page_router = APIRouter(tags=["handoff"])
router = APIRouter(tags=["handoff"], dependencies=[Depends(require_api_key)])

_PAGE = Path(__file__).resolve().parents[2] / "web" / "handoff.html"


@page_router.get("/handoff", include_in_schema=False)
def handoff_page() -> FileResponse:
    return FileResponse(_PAGE, media_type="text/html")


@router.get("/api/v1/handoff/queue", response_model=HandoffQueue)
def handoff_queue(
    limit: int = Query(default=20, ge=1, le=50),
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> HandoffQueue:
    return queue(db, limit, status_filter)


@router.get("/api/v1/handoff/tickets/{ticket_id}", response_model=HandoffDetail)
def handoff_ticket(ticket_id: str, db: Session = Depends(get_db)) -> HandoffDetail:
    ticket = require_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return detail(db, ticket)


@router.post("/api/v1/handoff/tickets/{ticket_id}", response_model=HandoffResult)
def handoff_update(
    ticket_id: str,
    payload: HandoffIn,
    db: Session = Depends(get_db),
) -> HandoffResult:
    ticket = require_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    updated = apply_handoff(db, ticket, payload)
    return HandoffResult(action=payload.action, ticket=ticket_out(db, updated))
