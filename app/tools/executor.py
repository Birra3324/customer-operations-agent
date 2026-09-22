"""Allowlisted tool execution with retry on simulated transient failures."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.config import get_settings
from app.tools import REGISTRY, ToolContext, ToolError, TransientToolError
from app.tools.retry import sleep_backoff

log = logging.getLogger("ops.executor")


def execute_tool(name: str, arguments: dict | None, ctx: ToolContext) -> dict:
    """Run one registry tool. Unknown names and extra argument fields never execute."""
    settings = get_settings()
    clean_name = (name or "").strip()
    spec = REGISTRY.get(clean_name)
    allowed = clean_name in settings.tool_allowlist and spec is not None
    record = {
        "tool": clean_name or "unknown",
        "arguments": arguments or {},
        "ok": False,
        "attempts": 0,
        "result": None,
        "error": None,
    }
    if not allowed:
        record["error"] = "tool_not_allowed"
        log.info("tool_blocked tool=%s", record["tool"])
        return record
    try:
        parsed = spec.args_model.model_validate(arguments or {})
    except ValidationError:
        record["error"] = "invalid_arguments"
        log.info("tool_rejected tool=%s code=invalid_arguments", clean_name)
        return record

    attempts_allowed = max(1, settings.tool_max_attempts)
    last_code = "transient_failure"
    for attempt in range(1, attempts_allowed + 1):
        record["attempts"] = attempt
        try:
            result = spec.fn(ctx, parsed)
        except TransientToolError:
            last_code = "transient_failure"
            log.warning("tool_transient tool=%s attempt=%s", clean_name, attempt)
            if attempt >= attempts_allowed:
                break
            sleep_backoff(attempt)
            continue
        except ToolError as exc:
            record["error"] = exc.code
            log.info("tool_rejected tool=%s code=%s", clean_name, exc.code)
            return record
        except Exception:  # noqa: BLE001
            record["error"] = "tool_failed"
            log.error("tool_failed tool=%s error_type=Exception", clean_name)
            return record
        record["ok"] = True
        record["result"] = result
        record["error"] = None
        log.info("tool_finished tool=%s ok=true attempts=%s", clean_name, attempt)
        return record

    record["ok"] = False
    record["error"] = last_code
    log.info("tool_finished tool=%s ok=false attempts=%s", clean_name, record["attempts"])
    return record
