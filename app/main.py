"""Application factory. Keep this module importable as `app.main:app`."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.routes import agent, handoff, health, n8n, runs, tickets
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestIdMiddleware, setup_logging
from app.db.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not get_settings().api_key.strip():
        raise RuntimeError("API_KEY must be configured before starting the service")
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Customer operations agent: classify a support ticket, call mock tools, "
            "store the plan and tool trace, and hand escalated tickets to a person. "
            "An n8n workflow can post the same ticket contract."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)
    application.include_router(health.router)
    application.include_router(handoff.page_router)
    application.include_router(tickets.router)
    application.include_router(runs.router)
    application.include_router(agent.router)
    application.include_router(handoff.router)
    application.include_router(n8n.router)
    return application


app = create_app()
