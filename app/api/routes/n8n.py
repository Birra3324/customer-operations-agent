"""Bridge used by the importable n8n workflow. Same API key as the other routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.database import get_db
from app.models.schemas import N8nEventList, N8nEventOut, N8nInbound, N8nInboundOut, N8nStatusIn
from app.services.handoff import event_out
from app.services.n8n_bridge import accept_inbound, list_events, record_status
from app.services.store import run_out, ticket_out

router = APIRouter(tags=["integrations"], dependencies=[Depends(require_api_key)])


@router.post("/api/v1/integrations/n8n/inbound", response_model=N8nInboundOut, status_code=status.HTTP_201_CREATED)
def n8n_inbound(payload: N8nInbound, response: Response, db: Session = Depends(get_db)) -> N8nInboundOut:
    ticket, run, idempotent = accept_inbound(db, payload)
    if idempotent:
        response.status_code = status.HTTP_200_OK
    return N8nInboundOut(
        accepted=True,
        idempotent=idempotent,
        event=payload.event,
        external_id=payload.external_id,
        workflow=payload.workflow,
        ticket=ticket_out(db, ticket),
        run=run_out(run),
    )


@router.post("/api/v1/integrations/n8n/status", response_model=N8nEventOut, status_code=status.HTTP_201_CREATED)
def n8n_status(payload: N8nStatusIn, db: Session = Depends(get_db)) -> N8nEventOut:
    event = record_status(db, payload)
    if event is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return event_out(event)


@router.get("/api/v1/integrations/n8n/events", response_model=N8nEventList)
def n8n_events(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> N8nEventList:
    return list_events(db, limit)
