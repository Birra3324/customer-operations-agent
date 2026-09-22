# Demo screenshots

Generated from a local API on port 8789 by [scripts/capture_demo.py](../../scripts/capture_demo.py). The script posts the fictional Vision AI Ops tickets, then opens Chrome.

| File | What it shows |
| --- | --- |
| [health.png](health.png) | Live `GET /health` body |
| [ticket-create.png](ticket-create.png) | Live `POST /api/v1/tickets` response, trimmed to id, status, and tool names |
| [tool-trace.png](tool-trace.png) | Tool table on the handoff page for the escalated ticket |
| [handoff-ui.png](handoff-ui.png) | `/handoff` after load, with queue, status, and assign |
| [n8n-canvas.png](n8n-canvas.png) | Map of `n8n/vision-ops-ticket-bridge.json`. Not a live n8n editor. |

Regenerate (API already running, heuristic provider, no model key):

```bash
pip install playwright
export API_KEY=change-me-to-a-long-random-string
python scripts/capture_demo.py
```

Playwright is only for this script. pytest and GitHub Actions do not install it. The API key is typed into a password field and is not part of the images.
