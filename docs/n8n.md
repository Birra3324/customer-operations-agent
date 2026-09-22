# n8n webhook bridge

The file [n8n/vision-ops-ticket-bridge.json](../n8n/vision-ops-ticket-bridge.json) is an n8n 1.x workflow you import. It is not a running n8n server, and this repo does not claim a Workato, MuleSoft, or ServiceNow integration.

The workflow does three things:

1. **Receive ticket event** — webhook `POST /webhook/vision-ops-ticket`
2. **Call agent API** — `POST /api/v1/integrations/n8n/inbound` on this service
3. **Post status** — `POST /api/v1/integrations/n8n/status` with the ticket id the agent returned

`active` is false in the file. Import it, then turn the workflow on in n8n when you want the webhook to listen.

## Secrets

The HTTP nodes read two values from the **n8n process environment**. They are not in the workflow JSON.

| Variable | Value |
| --- | --- |
| `OPS_AGENT_URL` | `http://127.0.0.1:8789` (or the host n8n can reach) |
| `OPS_AGENT_API_KEY` | The same string as this service's `API_KEY` |

`.env.example` lists `OPS_AGENT_API_KEY` blank. Put the real value only in the n8n environment or a local `.env` that is not committed. Do not paste it into the workflow, a credential export, or a screenshot.

This service does not read `OPS_AGENT_URL` or `OPS_AGENT_API_KEY`. Those names exist so the workflow and the API key stay in different places.

## Webhook body

n8n's webhook node puts the JSON on `$json.body`. Send:

```json
{
  "subject": "Need a human — TraceLight workspace is down",
  "body": "Our whole team is locked out and this looks like an outage. Please escalate to a person on the ops queue.",
  "customer_id": "cust-3301",
  "channel": "portal"
}
```

The agent node adds `event`, `external_id` (`$execution.id`), and `workflow`. The same `external_id` posted again returns the original ticket and run (`idempotent: true`, HTTP 200) instead of a second run.

## Demo without n8n

The bridge routes are the contract. You can show them with curl while n8n is not installed. Payload: [examples/n8n_inbound.json](../examples/n8n_inbound.json).

```bash
export API_KEY=change-me-to-a-long-random-string
API_KEY="$API_KEY" python scripts/post_n8n_demo.py
```

Or by hand:

```bash
curl -sS -X POST http://127.0.0.1:8789/api/v1/integrations/n8n/inbound \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d @examples/n8n_inbound.json
```

Then post status (the script does this for you):

```bash
curl -sS -X POST http://127.0.0.1:8789/api/v1/integrations/n8n/status \
  -H "content-type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"ticket_id":"TICKET_ID","workflow":"vision-ops-ticket-bridge","status":"posted","external_id":"demo-n8n-kite-outage","note":"n8n bridge posted agent status"}'
```

`status` on that callback is `posted`, `failed`, or `skipped`. It records a row. It does not change the ticket status the agent already wrote. Open [http://127.0.0.1:8789/handoff](http://127.0.0.1:8789/handoff) and the ticket detail lists the n8n line.

`GET /api/v1/integrations/n8n/events` returns the same rows.

## Calling the ticket route instead

The inbound route is the one the committed workflow uses, because it stores `external_id`. A workflow that only needs to create a ticket can POST `/api/v1/tickets` with the same `X-API-Key` header and the subject/body JSON from [docs/api.md](api.md). Keep the key in the n8n environment either way.

## Canvas screenshot

[docs/screenshots/n8n-canvas.png](screenshots/n8n-canvas.png) is a map of this JSON, drawn by `scripts/capture_demo.py`. The capture environment does not run n8n, so that image is not the n8n editor. Import the workflow to see the real canvas.
