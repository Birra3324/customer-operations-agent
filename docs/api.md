# API

Base URL for the local demo: `http://127.0.0.1:8789`

Authenticated routes expect `X-API-Key`. Errors look like:

```json
{"error": "Invalid or missing API key", "request_id": "..."}
```

Validation errors use HTTP 422 and `{"error": "Validation failed", "details": [...], "request_id": "..."}`.

## GET /health

Public.

```json
{
  "ok": true,
  "status": "ok",
  "db": true,
  "ai_provider": "heuristic",
  "model": "heuristic",
  "ollama": null
}
```

`ollama` is true or false only when `AI_PROVIDER=ollama`. Otherwise it is null.

## POST /api/v1/tickets

Creates a ticket and runs the agent. HTTP 201.

```json
{
  "subject": "Duplicate TraceLight invoice",
  "body": "We were charged twice for the September TraceLight Enterprise invoice. Can you confirm which charge is valid?",
  "customer_id": "cust-1042",
  "channel": "email"
}
```

`customer_id` is optional. `channel` is `email`, `chat`, `portal`, or `slack` (default `email`).

Response (`ticket` + `run`):

| Field | Meaning |
| --- | --- |
| `ticket.status` | `open` before the agent, then whatever `update_ticket` wrote |
| `run.plan` | Planner thoughts and executor result lines, in order |
| `run.tool_calls` | `{tool, arguments, ok, attempts, result, error}` |
| `run.final_reply` | Customer-facing text |
| `run.ticket_status` | Status after the run |
| `run.intent` / `run.priority` | `billing`, `password_reset`, `escalation`, or `general`; priority `low` through `urgent` |
| `run.provider` | `heuristic`, `ollama`, or `openai` |
| `run.fallback` | `heuristic` when a remote planner failed and the offline planner finished the run |
| `run.status` | `completed`, or `needs_review` when max tool rounds stopped the loop |

A captured offline body is in [examples/sample_responses.json](../examples/sample_responses.json).

## GET /api/v1/tickets

Newest first. Query `limit` from 1 to 50 (default 20).

```json
{"tickets": [], "count": 0}
```

## GET /api/v1/tickets/{id}

One ticket, including `latest_run_id`. HTTP 404 when the id is unknown.

## GET /api/v1/runs/{id}

The full plan and tool trace. HTTP 404 when the id is unknown.

## POST /api/v1/agent/run

Either a new ticket (`subject` and `body`, optional `customer_id` and `channel`) or `{"ticket_id": "..."}` to run again. HTTP 200 and an `AgentRun` body. Unknown `ticket_id` is HTTP 404.

Interactive docs: [http://127.0.0.1:8789/docs](http://127.0.0.1:8789/docs) while the server is running.
