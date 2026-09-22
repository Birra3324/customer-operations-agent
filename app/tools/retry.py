"""Retry helper for transient tool failures. Sleep is skipped when APP_ENV=test."""

from __future__ import annotations

import time

from app.core.config import get_settings


def backoff_delay(attempt: int) -> float:
    """Delay after a failed attempt. `attempt` is 1-based."""
    settings = get_settings()
    base = max(0.0, settings.tool_retry_base_seconds)
    return min(2.0, base * (2 ** (attempt - 1)))


def sleep_backoff(attempt: int) -> float:
    delay = backoff_delay(attempt)
    if delay > 0 and not get_settings().is_test:
        time.sleep(delay)
    return delay
