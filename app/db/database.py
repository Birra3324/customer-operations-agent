"""SQLAlchemy engine and session. SQLite for the local demo and tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in url:
            return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
        engine = create_engine(url, connect_args=connect_args)

        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def reset_engine() -> None:
    """Rebuild engine/session after settings change (tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite") or ":///" not in url:
        return
    raw = url.split("sqlite:///", 1)[-1]
    if not raw or raw == ":memory:":
        return
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_ticket_handoff_columns(engine: Engine) -> None:
    """Add Day 22 columns on an existing SQLite file. create_all does not ALTER."""
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "tickets" not in tables:
            return
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(tickets)"))}
        additions = {
            "assignee": "VARCHAR(64)",
            "handoff_note": "TEXT",
            "handoff_at": "DATETIME",
        }
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """create_all for the local demo. See docs/architecture.md (no Alembic)."""
    from app.models import entities as _entities  # noqa: F401

    settings = get_settings()
    _ensure_sqlite_parent(settings.database_url)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if settings.is_sqlite:
        ensure_ticket_handoff_columns(engine)


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def db_healthy() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
