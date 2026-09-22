"""Planner/executor loop. Persists the agent run and the updated ticket."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.agent.planner import HeuristicPlanner, LlmPlanner, classification_for
from app.core.config import get_settings
from app.core.logging import get_request_id
from app.models.entities import AgentRun, Ticket
from app.tools import ToolContext
from app.tools.executor import execute_tool

log = logging.getLogger("ops.agent")


def build_planner() -> HeuristicPlanner | LlmPlanner:
    if get_settings().ai_provider == "heuristic":
        return HeuristicPlanner()
    return LlmPlanner()


def run_agent(db: Session, ticket: Ticket) -> AgentRun:
    settings = get_settings()
    planner = build_planner()
    ctx = ToolContext(
        db=db,
        ticket_id=ticket.id,
        simulate_flake=settings.simulate_flaky_tool,
    )
    history: list[dict] = []
    plan: list[dict] = []
    tool_calls: list[dict] = []
    final_reply = ""
    status = "needs_review"
    rounds = 0

    log.info("agent_start provider=%s", settings.ai_provider)
    for round_index in range(1, settings.max_tool_rounds + 1):
        rounds = round_index
        decision = planner.next(ticket, history)
        plan.append(
            {
                "round": round_index,
                "actor": "planner",
                "thought": decision.thought[:500],
                "action": decision.action,
                "tool": decision.tool,
            }
        )
        log.info(
            "planner_step round=%s action=%s tool=%s",
            round_index,
            decision.action,
            decision.tool or "-",
        )
        if decision.action == "final":
            final_reply = (decision.final_reply or "").strip()
            status = "completed"
            break
        record = execute_tool(decision.tool or "", decision.arguments, ctx)
        tool_calls.append(record)
        history.append(record)
        plan.append(
            {
                "round": round_index,
                "actor": "executor",
                "thought": f"{record['tool']} ok={str(record['ok']).lower()} attempts={record['attempts']}",
                "action": "tool_result",
                "tool": record["tool"],
            }
        )
    else:
        final_reply = "Stopped: max tool rounds reached before a final reply."
        status = "needs_review"

    if not ticket.intent or not ticket.priority:
        # Remote planners can finish without update_ticket. Keep the row labeled.
        fallback_label = classification_for(ticket)
        ticket.intent = ticket.intent or fallback_label.intent
        ticket.priority = ticket.priority or fallback_label.priority
        if ticket.status == "open" and status == "needs_review":
            ticket.status = "in_progress"

    run = AgentRun(
        ticket_id=ticket.id,
        provider=settings.ai_provider,
        status=status,
        plan=plan,
        tool_calls=tool_calls,
        final_reply=final_reply,
        ticket_status=ticket.status,
        intent=ticket.intent,
        priority=ticket.priority,
        rounds=rounds,
        fallback="heuristic" if getattr(planner, "used_fallback", False) else None,
        request_id=get_request_id(),
    )
    db.add(run)
    db.commit()
    log.info(
        "agent_done status=%s rounds=%s intent=%s priority=%s",
        run.status,
        run.rounds,
        run.intent,
        run.priority,
    )
    return run
