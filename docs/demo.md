# Recruiter demo (10–15 minutes)

Local walkthrough. No hosted demo URL. From the clone root, the commands below are copy-pasteable.

You need Python 3.12+ and `curl`. `jq` is optional. Ollama and OpenAI are optional: the default `AI_PROVIDER=heuristic` classifies the ticket and calls tools with no model and no API key. Slides, if you want them before the live run, are the PNGs in [screenshots/](screenshots/).

| Minutes | What you show |
| --- | --- |
| 2 | Setup and start uvicorn on port 8789 |
| 4 | Health, three fictional tickets, tool trace |
| 3 | Human handoff page: status, trace, assign |
| 3 | n8n bridge (curl or `scripts/post_n8n_demo.py`; n8n itself is optional) |
| 1 | Optional: flaky-tool retry |

That is about 13 minutes before questions. Docker stays optional and is outside the clock.

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

You want `"ok": true`, `"db": true`, `"ai_provider": "heuristic"`. No API key on this call. The same body is in [screenshots/health.png](screenshots/health.png).

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

Copy a `run.id` from one response. A trimmed billing response is in [screenshots/ticket-create.png](screenshots/ticket-create.png).

## 5. Read it back (~1 min)

```bash
curl -sS http://127.0.0.1:8789/api/v1/tickets \
  -H "X-API-Key: $API_KEY"

curl -sS http://127.0.0.1:8789/api/v1/runs/RUN_ID \
  -H "X-API-Key: $API_KEY"
```

You should see three tickets, and the run should still list the tool calls. The same trace is on the handoff page: [screenshots/tool-trace.png](screenshots/tool-trace.png).

Optional second pass on a stored ticket:

```bash
curl -sS -X POST http://127.0.0.1:8789/api/v1/agent/run \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"ticket_id": "TICKET_ID"}'
```

That returns a new run id for the same ticket.

## 6. Human handoff (~3 min)

Leave uvicorn running. Open [http://127.0.0.1:8789/handoff](http://127.0.0.1:8789/handoff).

Paste `API_KEY` into the password field and choose **Load queue**. The page calls `GET /api/v1/handoff/queue` and then the ticket detail route. It does not embed the key in the HTML.

Talking points:

- The Kite and Co outage ticket is already `escalated` because the heuristic planner classified it that way. Assignee is empty until a person takes it.
- The tool table is the stored run: `lookup_kb`, `get_customer`, `update_ticket`, `notify_slack`. Slack shows `"mode": "logged"` when the webhook is empty.
- Choose **ops-queue** and **Assign**. Status stays `escalated` (that queue is the human owner). A resolved billing ticket assigned this way moves to `in_progress` instead.
- **Escalate to human** forces `escalated` and defaults the assignee to `ops-queue` when you do not send one.
- **Mark resolved** sets `resolved` and does not start another agent run. `latest_run_id` stays the same.
- The note is stored on the ticket and shown on the page. It is not written to the server log.

`Escalated only` calls `GET /api/v1/handoff/queue?status=escalated`.

Queues are the three fictional names `ops-queue`, `billing-desk`, and `access-desk`. A picture of this page after assign is [screenshots/handoff-ui.png](screenshots/handoff-ui.png).

## 7. n8n bridge (~3 min)

You do not need n8n installed to show the path. The importable workflow is [n8n/vision-ops-ticket-bridge.json](../n8n/vision-ops-ticket-bridge.json). The HTTP nodes call this API and read `OPS_AGENT_URL` and `OPS_AGENT_API_KEY` from the n8n environment. The key is not in the JSON. Full notes: [n8n.md](n8n.md).

```bash
API_KEY="$API_KEY" python scripts/post_n8n_demo.py
```

The script posts [examples/n8n_inbound.json](../examples/n8n_inbound.json) to `POST /api/v1/integrations/n8n/inbound`, then posts `status: posted` to `POST /api/v1/integrations/n8n/status`.

Talking points:

- HTTP 201 the first time, with `idempotent: false`, intent `escalation`, and a tool trace.
- Run the script again. HTTP 200, `idempotent: true`, same ticket id and same run id. `external_id` is `demo-n8n-kite-outage`.
- Reload the handoff page. The ticket detail includes an n8n line: `vision-ops-ticket-bridge · status.posted`.
- `GET /api/v1/integrations/n8n/events` lists those rows. The status callback does not overwrite the ticket status.

[screenshots/n8n-canvas.png](screenshots/n8n-canvas.png) is a map of the three nodes (receive, call the agent, post status). It is not a live n8n editor. If n8n is installed, import the JSON, set the two environment variables on the n8n process, activate the workflow, and POST the subject/body from `examples/n8n_inbound.json` to the webhook path `vision-ops-ticket`. Leave the API key out of the file.

## 8. Optional: show the retry (~1 min)

Stop uvicorn, set `SIMULATE_FLAKY_TOOL=true` in `.env`, start again, and post the billing ticket. `lookup_kb` comes back `"attempts": 2` and `"ok": true`. The executor retried a simulated transient failure. Set the flag back to `false` when you are done. Architecture notes: [architecture.md](architecture.md).

## 9. Optional: Docker

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
