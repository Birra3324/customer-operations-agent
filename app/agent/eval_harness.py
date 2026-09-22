"""Score the golden scenarios in evals/scenarios.json without a running server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.models.entities import Ticket


def scenarios_path() -> Path:
    return Path(__file__).resolve().parents[2] / "evals" / "scenarios.json"


def load_scenarios() -> list[dict]:
    return json.loads(scenarios_path().read_text(encoding="utf-8"))


def evaluate_scenario(db: Session, scenario: dict) -> dict:
    payload = scenario["ticket"]
    ticket = Ticket(
        subject=payload["subject"],
        body=payload["body"],
        customer_id=payload.get("customer_id"),
        channel=payload.get("channel") or "email",
        status="open",
    )
    db.add(ticket)
    db.flush()
    run = run_agent(db, ticket)
    expect = scenario["expect"]
    called = [item["tool"] for item in run.tool_calls]
    ok_tools = [item["tool"] for item in run.tool_calls if item.get("ok")]
    missing = [name for name in expect["tools"] if name not in ok_tools]
    unexpected = [name for name in expect.get("tools_absent", []) if name in called]
    reply = run.final_reply.lower()
    missing_phrases = [
        phrase for phrase in expect.get("reply_contains", []) if phrase.lower() not in reply
    ]
    passed = (
        run.intent == expect["intent"]
        and run.priority == expect["priority"]
        and run.ticket_status == expect["status"]
        and not missing
        and not unexpected
        and not missing_phrases
        and run.status == "completed"
    )
    return {
        "id": scenario["id"],
        "ok": passed,
        "intent": run.intent,
        "priority": run.priority,
        "ticket_status": run.ticket_status,
        "tools": called,
        "missing_tools": missing,
        "unexpected_tools": unexpected,
        "missing_phrases": missing_phrases,
    }


def evaluate_all(db: Session) -> list[dict]:
    return [evaluate_scenario(db, scenario) for scenario in load_scenarios()]


def main() -> None:
    import os
    import tempfile

    from app.core.config import reset_settings
    from app.db.database import get_session_factory, init_db, reset_engine

    # Score the offline planner against a throwaway database, even if .env points at Ollama.
    tmp = tempfile.mkdtemp(prefix="ops-eval-")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/eval.db"
    os.environ["AI_PROVIDER"] = "heuristic"
    os.environ["APP_ENV"] = "test"
    os.environ["SIMULATE_FLAKY_TOOL"] = "false"
    os.environ.setdefault("API_KEY", "eval-not-a-secret")
    reset_settings()
    reset_engine()
    init_db()
    db = get_session_factory()()
    try:
        results = evaluate_all(db)
    finally:
        db.close()
    failed = 0
    for row in results:
        mark = "PASS" if row["ok"] else "FAIL"
        print(
            f"{mark} {row['id']} intent={row['intent']} "
            f"priority={row['priority']} status={row['ticket_status']} tools={row['tools']}"
        )
        if not row["ok"]:
            failed += 1
            print(
                f"  missing_tools={row['missing_tools']} "
                f"unexpected={row['unexpected_tools']} phrases={row['missing_phrases']}"
            )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
