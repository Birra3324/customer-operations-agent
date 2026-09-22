# Status — Days 19–21

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
| pytest (temp SQLite, mocked LLM) | Pass | **33 passed** on Python 3.12. Same command in CI. |
| GitHub Actions | Added | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). No secrets. |
| Docker Compose | Artifact | [`docker-compose.yml`](../docker-compose.yml) runs the API with a SQLite volume. Not required for the walkthrough. |
| Secrets | Clean | `.env` is gitignored. Demo key only in `.env.example` as `change-me-to-a-long-random-string`. No Slack tokens or provider keys in git. |
| Hosted demo | None | Local only. |

## Days 22–25 (next)

| Day | Intent | This repo |
| --- | --- | --- |
| 22 | Human handoff UI for escalated tickets | not started |
| 23 | n8n webhook bridge into `POST /api/v1/tickets` | not started |
| 24 | Screenshots of health, a tool trace, and the Slack log line | not started |
| 25 | Extended recruiter walkthrough on top of the screenshots | not started |

[docs/demo.md](demo.md) is the Day 21 clone-and-run script. Day 25 is the later pass once screenshots exist. Do not treat this file as claiming those days are done.

Constraints that stay true for the whole track:

- Fictional Vision AI Ops data only
- No real API keys, Slack tokens, or customer traces in git
- No UiPath / Workato / MuleSoft / ServiceNow claims
- Default path works offline
