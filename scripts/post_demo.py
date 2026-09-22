#!/usr/bin/env python3
"""Post examples/demo_requests.json to a local Customer Operations Agent."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    key = os.environ.get("API_KEY", "")
    if not key:
        print("Set API_KEY to the same value as .env", file=sys.stderr)
        sys.exit(1)
    base = os.environ.get("BASE_URL", "http://127.0.0.1:8789").rstrip("/")
    path = Path(__file__).resolve().parents[1] / "examples" / "demo_requests.json"
    tickets = json.loads(path.read_text(encoding="utf-8"))
    for ticket in tickets:
        request = urllib.request.Request(
            f"{base}/api/v1/tickets",
            data=json.dumps(ticket).encode(),
            headers={"content-type": "application/json", "X-API-Key": key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                body = json.loads(response.read().decode())
                status = response.status
        except urllib.error.HTTPError as exc:
            print(exc.read().decode(), file=sys.stderr)
            raise
        tools = [call["tool"] for call in body["run"]["tool_calls"]]
        print(
            f"{status} intent={body['run']['intent']} "
            f"priority={body['run']['priority']} "
            f"status={body['run']['ticket_status']} tools={tools}"
        )


if __name__ == "__main__":
    main()
