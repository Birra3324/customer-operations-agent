#!/usr/bin/env python3
"""Post examples/n8n_inbound.json, then the status callback the n8n workflow sends."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _request(url: str, key: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "X-API-Key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        raise


def main() -> None:
    key = os.environ.get("API_KEY", "")
    if not key:
        print("Set API_KEY to the same value as .env", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8789").rstrip("/")
    path = Path(__file__).resolve().parents[1] / "examples" / "n8n_inbound.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    status, body = _request(f"{base}/api/v1/integrations/n8n/inbound", key, payload)
    run = body["run"]
    print(
        f"{status} idempotent={str(body['idempotent']).lower()} "
        f"ticket={body['ticket']['id']} intent={run['intent']} "
        f"ticket_status={run['ticket_status']}"
    )
    status_payload = {
        "ticket_id": body["ticket"]["id"],
        "workflow": body["workflow"],
        "status": "posted",
        "external_id": body["external_id"],
        "note": "n8n bridge posted agent status",
    }
    posted, event = _request(f"{base}/api/v1/integrations/n8n/status", key, status_payload)
    print(f"{posted} n8n_event={event['id']} status={event['status']}")


if __name__ == "__main__":
    main()
