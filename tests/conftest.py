"""Test env must be set before app imports so settings pick up SQLite and the API key."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="ops-test-"))
_DB = _TMP / "test.db"

os.environ["APP_ENV"] = "test"
os.environ["APP_NAME"] = "Customer Operations Agent"
os.environ["API_KEY"] = "test-api-key"
os.environ["AI_PROVIDER"] = "heuristic"
os.environ["OLLAMA_URL"] = "http://127.0.0.1:11434"
os.environ["OLLAMA_MODEL"] = "llama3.2"
os.environ["OPENAI_API_KEY"] = ""
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["FIXTURES_DIR"] = "data"
os.environ["SLACK_WEBHOOK_URL"] = ""
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["SIMULATE_FLAKY_TOOL"] = "false"
os.environ["MAX_TOOL_ROUNDS"] = "6"
os.environ["ALLOWED_TOOLS"] = "lookup_kb,get_customer,create_ticket,update_ticket,notify_slack"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import reset_settings  # noqa: E402
from app.db.database import Base, get_engine, get_session_factory, init_db, reset_engine  # noqa: E402
from app.main import app  # noqa: E402

reset_settings()
reset_engine()
init_db()

AUTH = {"X-API-Key": "test-api-key"}


@pytest.fixture(autouse=True)
def _fresh_db():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return dict(AUTH)


@pytest.fixture
def db_session():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
