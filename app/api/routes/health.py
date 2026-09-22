"""Public health check. Does not require an API key."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter

from app.core.config import get_settings
from app.db.database import db_healthy
from app.models.schemas import HealthOut

log = logging.getLogger("ops.health")
router = APIRouter(tags=["health"])


def _ollama_up() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    db_ok = db_healthy()
    if settings.ai_provider == "ollama":
        model = settings.ollama_model
        ollama: bool | None = _ollama_up()
    elif settings.ai_provider == "openai":
        model = settings.openai_model
        ollama = None
    else:
        model = "heuristic"
        ollama = None
    if not db_ok:
        log.error("health_database_unreachable")
    return HealthOut(
        ok=db_ok,
        status="ok" if db_ok else "degraded",
        db=db_ok,
        ai_provider=settings.ai_provider,
        model=model,
        ollama=ollama,
    )
