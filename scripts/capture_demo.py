#!/usr/bin/env python3
"""Capture README screenshots from a running local API.

Writes:
  docs/screenshots/health.png
  docs/screenshots/ticket-create.png
  docs/screenshots/tool-trace.png
  docs/screenshots/handoff-ui.png
  docs/screenshots/n8n-canvas.png

The handoff image is the real /handoff page. Health and ticket-create are
browser shots of live JSON. The n8n image is a map of the workflow file,
because this script does not start n8n.

Requires Chrome and the optional playwright package (not installed by CI).
"""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
WORKFLOW = ROOT / "n8n" / "vision-ops-ticket-bridge.json"
DEMOS = ROOT / "examples" / "demo_requests.json"


def _call(method: str, url: str, key: str | None, payload: dict | None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise


def _card(title: str, request_line: str, body: dict) -> str:
    pretty = html.escape(json.dumps(body, indent=2))
    title = html.escape(title)
    request_line = html.escape(request_line)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ margin: 0; background: #efe7dc; color: #1c1916; font: 15px/1.4 "Segoe UI", system-ui, sans-serif; }}
  main {{ padding: 28px; }}
  h1 {{ font-size: 22px; margin: 0 0 8px; }}
  p {{ margin: 0 0 12px; color: #5e564c; }}
  pre {{ background: #fffdf9; border: 1px solid #ddcfc0; border-radius: 12px; padding: 16px; overflow: auto; }}
</style></head>
<body><main>
  <h1>{title}</h1>
  <p>{request_line}</p>
  <pre>{pretty}</pre>
</main></body></html>"""


def _canvas(workflow: dict) -> str:
    nodes = workflow["nodes"]
    boxes = []
    for index, node in enumerate(nodes):
        left = 40 + index * 280
        label = node["name"]
        kind = node["type"].split(".")[-1]
        boxes.append(
            f'<div class="node" style="left:{left}px"><strong>{label}</strong><span>{kind}</span></div>'
        )
        if index < len(nodes) - 1:
            boxes.append(f'<div class="arrow" style="left:{left + 210}px"></div>')
    inner = "\n".join(boxes)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>n8n workflow map</title>
<style>
  body {{ margin: 0; background: #f3efe8; color: #1c1916; font: 15px/1.4 "Segoe UI", system-ui, sans-serif; }}
  main {{ padding: 28px 32px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; }}
  p {{ margin: 0 0 18px; color: #5e564c; max-width: 640px; }}
  .canvas {{ position: relative; height: 220px; background: #fffdf9; border: 1px solid #ddcfc0; border-radius: 12px; }}
  .node {{ position: absolute; top: 70px; width: 190px; background: white; border: 1px solid #0e5f57; border-radius: 10px; padding: 12px; }}
  .node strong {{ display: block; }}
  .node span {{ color: #5e564c; font-size: 12px; }}
  .arrow {{ position: absolute; top: 98px; width: 60px; height: 2px; background: #0e5f57; }}
  .arrow:after {{ content: ""; position: absolute; right: -1px; top: -4px; border: 5px solid transparent; border-left-color: #0e5f57; }}
</style></head>
<body><main>
  <h1>Workflow map — n8n/vision-ops-ticket-bridge.json</h1>
  <p>Not a live n8n editor. Import the JSON to open this graph in n8n. The HTTP nodes read OPS_AGENT_URL and OPS_AGENT_API_KEY from the n8n environment.</p>
  <div class="canvas">{inner}</div>
</main></body></html>"""


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright   # optional, not required for pytest", file=sys.stderr)
        sys.exit(1)

    key = os.environ.get("API_KEY", "")
    if not key:
        print("Set API_KEY to the same value as .env", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8789").rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)

    health_status, health = _call("GET", f"{base}/health", None, None)
    if health_status != 200 or health.get("ai_provider") != "heuristic":
        print("Health check failed or provider is not heuristic", file=sys.stderr)
        sys.exit(1)

    tickets = json.loads(DEMOS.read_text(encoding="utf-8"))
    created_status, created = _call("POST", f"{base}/api/v1/tickets", key, tickets[0])
    if created_status != 201:
        print("Ticket create failed", file=sys.stderr)
        sys.exit(1)
    for ticket in tickets[1:]:
        _call("POST", f"{base}/api/v1/tickets", key, ticket)

    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    pages = {
        "health.png": _card("GET /health", f"{base}/health", health),
        "ticket-create.png": _card(
            "POST /api/v1/tickets",
            "Harborline Logistics billing ticket — live response",
            {
                "ticket": {
                    "id": created["ticket"]["id"],
                    "status": created["ticket"]["status"],
                    "intent": created["ticket"]["intent"],
                    "priority": created["ticket"]["priority"],
                    "subject": created["ticket"]["subject"],
                },
                "run": {
                    "id": created["run"]["id"],
                    "provider": created["run"]["provider"],
                    "intent": created["run"]["intent"],
                    "priority": created["run"]["priority"],
                    "ticket_status": created["run"]["ticket_status"],
                    "tools": [call["tool"] for call in created["run"]["tool_calls"]],
                },
            },
        ),
        "n8n-canvas.png": _canvas(workflow),
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 720})
        for name, html in pages.items():
            page.set_content(html)
            page.screenshot(path=str(OUT / name), full_page=True)
            print(OUT / name)

        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{base}/handoff", wait_until="domcontentloaded")
        page.fill("#api-key", key)
        page.click("#load")
        page.locator(".ticket", has_text="workspace").click()
        page.wait_for_selector("table")
        page.locator("table").screenshot(path=str(OUT / "tool-trace.png"))
        print(OUT / "tool-trace.png")
        page.fill("#note", "Assigned from the handoff desk.")
        page.get_by_role("button", name="Assign", exact=True).click()
        page.wait_for_selector("text=Queue note:")
        page.screenshot(path=str(OUT / "handoff-ui.png"), full_page=True)
        print(OUT / "handoff-ui.png")
        browser.close()


if __name__ == "__main__":
    main()
