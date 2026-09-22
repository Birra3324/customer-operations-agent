# Status — Days 19–25

Portfolio track for [customer-operations-agent](https://github.com/Birra3324/customer-operations-agent). Local demo only; no hosted URL. The default path is the offline heuristic planner plus SQLite and mock tools.

This is not a UiPath, Workato, MuleSoft, or ServiceNow project. The stack is FastAPI, a planner/executor loop, optional Ollama or OpenAI, SQLite, and a Slack webhook that logs when unset.

## Days 19–21 checklist

| Day | Intent | Status |
| --- | --- | --- |
| 19 | Scaffold FastAPI on port 8789, ticket and run routes, SQLite, Docker, README | **Done** |
| 20 | Tool registry, mock KB and CRM, allowlist, max rounds, retry/backoff, logs without PII payloads | **Done** |
| 21 | pytest with mocked LLM HTTP, golden scenarios, demo walkthrough, GitHub Actions | **Done** |

### Day 19 — scaffold

- [x] FastAPI on port **8789** (`8787` intake, `8788` RAG)
- [x] `GET /health`, `POST /api/v1/tickets`, `GET /api/v1/tickets/{id}`, `GET /api/v1/runs/{id}`, `POST /api/v1/agent/run`
- [x] Package layout: `app/`, `tests/`, `docs/`, `examples/`, `evals/`, `scripts/`, `.github/workflows/ci.yml`
- [x] `.env.example`, Dockerfile, docker compose (API + SQLite volume), MIT license, `.gitignore`
- [x] README with a clone-and-run path, architecture diagram, and contact line
- [x] Fictional Vision AI Ops tickets only

### Day 20 — tools and policy

- [x] Registry: `lookup_kb`, `get_customer`, `create_ticket`, `update_ticket`, `notify_slack`
- [x] Mock KB and CRM under `data/kb.json` and `data/crm.json`
- [x] Max tool rounds, tool allowlist, schema-checked arguments
- [x] No shell and no general network tool; Slack posts only when a webhook is configured
- [x] `lookup_kb` simulated flake with retry/backoff (`SIMULATE_FLAKY_TOOL`, documented in [architecture.md](architecture.md))
- [x] Default logs omit ticket body, subject, and CRM email

### Day 21 — eval and demo polish

- [x] pytest + TestClient; offline heuristic path needs no Ollama or OpenAI
- [x] LLM HTTP is mocked in tests; a missing OpenAI key falls back to the heuristic planner
- [x] Golden scenarios in `evals/scenarios.json`: billing, password reset, escalate to a human
- [x] End-to-end test asserts tool calls on the stored run
- [x] [docs/demo.md](demo.md) 5–10 minute walkthrough
- [x] GitHub Actions: Python 3.12, `pytest`, on push and pull request to `main`

## Verification

| Check | Status | Notes |
| --- | --- | --- |
| pytest (temp SQLite, mocked LLM) | Pass | **48 passed** on Python 3.12, including handoff and n8n. Same command in CI. |
| GitHub Actions | Added | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). No secrets. |
| Docker Compose | Artifact | [`docker-compose.yml`](../docker-compose.yml) runs the API with a SQLite volume. Not required for the walkthrough. |
| Secrets | Clean | `.env` is gitignored. Demo key only in `.env.example` as `change-me-to-a-long-random-string`. `OPS_AGENT_API_KEY` is blank there. The n8n workflow JSON has no key. No Slack tokens or provider keys in git. |
| Hosted demo | None | Local only. |

## Days 22–25 checklist

| Day | Intent | Status |
| --- | --- | --- |
| 22 | Human handoff UI: ticket status, tool trace, escalate or assign | **Done** |
| 23 | n8n webhook bridge (workflow JSON + inbound and status routes) | **Done** |
| 24 | Screenshots for health, ticket create, tool trace, handoff, n8n map | **Done** |
| 25 | Extended recruiter walkthrough (10–15 min) on top of those screenshots | **Done** |

### Day 22 — human handoff

- [x] Public page `GET /handoff` (no API key in the HTML). JSON routes still require `X-API-Key`
- [x] Queue shows status, assignee, and tool names. Detail shows the stored tool trace and the latest reply
- [x] `POST /api/v1/handoff/tickets/{id}` with `escalate`, `assign`, or `resolve`
- [x] Queues are `ops-queue`, `billing-desk`, and `access-desk`. Assign does not start a new agent run
- [x] Handoff notes are stored on the ticket and omitted from server logs

### Day 23 — n8n bridge

- [x] Importable workflow [n8n/vision-ops-ticket-bridge.json](../n8n/vision-ops-ticket-bridge.json): webhook, call the agent, post status
- [x] `POST /api/v1/integrations/n8n/inbound` creates a ticket and runs the heuristic planner
- [x] The same `external_id` returns the original ticket and run (`idempotent: true`)
- [x] `POST /api/v1/integrations/n8n/status` records `posted`, `failed`, or `skipped` and does not rewrite ticket status
- [x] `OPS_AGENT_URL` and `OPS_AGENT_API_KEY` are read by n8n from its environment. The workflow JSON has no key. `.env.example` leaves `OPS_AGENT_API_KEY` blank

### Day 24 — screenshots

- [x] [docs/screenshots/](screenshots/) — health, ticket create, tool trace, handoff UI
- [x] n8n canvas image is a map of the workflow JSON. The capture script does not start n8n
- [x] [scripts/capture_demo.py](../scripts/capture_demo.py) hits the live API. Playwright is optional and is not a CI dependency

### Day 25 — extended walkthrough

- [x] [docs/demo.md](demo.md) is the 10–15 minute recruiter script, including handoff and the n8n path
- [x] [docs/n8n.md](n8n.md) is the import and secret-handling note
- [x] README links the page, the workflow, and the screenshots

## Days 26–30 (next)

| Day | Intent | This repo |
| --- | --- | --- |
| 26 | Batch intake for a file of fictional tickets, reusing the n8n external id | not started |
| 27 | Downloadable run export (JSON) so a trace can be attached without opening SQLite | not started |
| 28 | Handoff audit list (action, queue, time) separate from the customer reply | not started |
| 29 | Optional Ollama pass on the same three golden scenarios; still not required for CI | not started |
| 30 | One-page case study and an explicit list of what this demo does not claim | not started |

[docs/demo.md](demo.md) is the current clone-and-run script. Days 26–30 are not in this repo yet.

Constraints that stay true for the whole track:

- Fictional Vision AI Ops data only
- No real API keys, Slack tokens, or customer traces in git
- No UiPath / Workato / MuleSoft / ServiceNow claims
- Default path works offline
