# Recruiter demo (5–10 minutes)

Local walkthrough. No hosted demo URL. From the clone root, the commands below are copy-pasteable.

You need Python 3.12+ and `curl`. `jq` is optional. Ollama and OpenAI are optional: the default `AI_PROVIDER=heuristic` classifies the ticket and calls tools with no model and no API key.

## 1. Setup (~2 min)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export API_KEY=change-me-to-a-long-random-string
```

Leave `AI_PROVIDER=heuristic` and `SLACK_WEBHOOK_URL` empty.

## 2. Run the API (~30 s)

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8789
```

Or: `./scripts/run_dev.sh`

Wait until uvicorn is listening on `127.0.0.1:8789`.

## 3. Health (~15 s)

```bash
curl -sS http://127.0.0.1:8789/health
```

You want `"ok": true`, `"db": true`, `"ai_provider": "heuristic"`. No API key on this call.

## 4. Post the three fictional tickets (~3 min)

Payloads are [examples/demo_requests.json](../examples/demo_requests.json).

```bash
# billing — Harborline Logistics, duplicate invoice
curl -sS -X POST http://127.0.0.1:8789/api/v1/tickets \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d @<(jq '.[0]' examples/demo_requests.json)

# password reset — Northglass Bakery
curl -sS -X POST http://127.0.0.1:8789/api/v1/tickets \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d @<(jq '.[1]' examples/demo_requests.json)

# escalate — Kite and Co, workspace outage
curl -sS -X POST http://127.0.0.1:8789/api/v1/tickets \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d @<(jq '.[2]' examples/demo_requests.json)
```

Without `jq`:

```bash
API_KEY="$API_KEY" python scripts/post_demo.py
```

Each call returns HTTP 201. Talking points while you scroll the JSON:

- `plan` alternates `actor: planner` and `actor: executor`. That is the handoff, not a single chat completion.
- Billing calls `lookup_kb`, `get_customer`, and `update_ticket`. Priority is medium, so Slack is not called. Status is `resolved`. The reply names Harborline Logistics and the billing article.
- Password reset adds `notify_slack`. With `SLACK_WEBHOOK_URL` empty, the tool result is `"mode": "logged"` (the server log says `slack_skipped`, not the customer text).
- The outage ticket is `intent: escalation`, `priority: urgent`, `ticket_status: escalated`, and the reply says it went to the ops queue. Priya's workspace is marked VIP in the mock CRM.
- `get_customer` does not echo the fictional email that lives in `data/crm.json`.

Copy a `run.id` from one response.

## 5. Read it back (~1 min)

```bash
curl -sS http://127.0.0.1:8789/api/v1/tickets \
  -H "X-API-Key: $API_KEY"

curl -sS http://127.0.0.1:8789/api/v1/runs/RUN_ID \
  -H "X-API-Key: $API_KEY"
```

You should see three tickets, and the run should still list the tool calls.

Optional second pass on a stored ticket:

```bash
curl -sS -X POST http://127.0.0.1:8789/api/v1/agent/run \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"ticket_id": "TICKET_ID"}'
```

That returns a new run id for the same ticket.

## 6. Optional: show the retry (~1 min)

Stop uvicorn, set `SIMULATE_FLAKY_TOOL=true` in `.env`, start again, and post the billing ticket. `lookup_kb` comes back `"attempts": 2` and `"ok": true`. The executor retried a simulated transient failure. Set the flag back to `false` when you are done. Architecture notes: [architecture.md](architecture.md).

## 7. Optional: Docker

```bash
docker compose up --build
```

Same `curl` commands against port 8789. Compose will not start until `API_KEY` is set (a copied `.env` is enough).

## Tests (not part of the live demo)

```bash
.venv/bin/pytest -q
./scripts/eval.sh
```

Pytest mocks LLM HTTP and uses a temp SQLite file. The eval script scores the three golden scenarios with the offline planner.
