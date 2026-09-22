"""Fetch one persisted agent run."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.database import get_db
from app.models.schemas import AgentRunOut
from app.services.store import get_run, run_out

router = APIRouter(tags=["runs"], dependencies=[Depends(require_api_key)])


@router.get("/api/v1/runs/{run_id}", response_model=AgentRunOut)
def get_one_run(run_id: str, db: Session = Depends(get_db)) -> AgentRunOut:
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_out(run)
