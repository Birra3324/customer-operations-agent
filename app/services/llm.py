"""Optional Ollama or OpenAI JSON completion. The default provider never calls this."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.core.config import get_settings

log = logging.getLogger("ops.llm")

JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)


def parse_json_object(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty model response")
    fence = JSON_FENCE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    else:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]
    data: Any = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("model JSON was not an object")
    return data


def _sleep(attempt: int) -> None:
    if get_settings().is_test:
        return
    time.sleep(0.35 * attempt)


def _post_with_retries(url: str, **kwargs: Any) -> httpx.Response:
    settings = get_settings()
    last: Exception | None = None
    attempts = max(1, settings.ai_max_retries)
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {
                408,
                429,
                500,
                502,
                503,
                504,
            }:
                raise
            last = exc
            log.warning(
                "llm_http attempt=%s/%s error_type=%s",
                attempt,
                attempts,
                type(exc).__name__,
            )
            if attempt < attempts:
                _sleep(attempt)
    raise RuntimeError(f"LLM HTTP failed after {attempts} attempts") from last


def _call_ollama(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    url = f"{settings.ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "format": "json",
    }
    response = _post_with_retries(url, json=payload, timeout=settings.ai_timeout_seconds)
    text = ((response.json().get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("empty Ollama response")
    return text


def _call_openai(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    response = _post_with_retries(
        url, json=payload, headers=headers, timeout=settings.ai_timeout_seconds
    )
    text = (
        response.json().get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    ).strip()
    if not text:
        raise RuntimeError("empty OpenAI response")
    return text


def complete(messages: list[dict[str, str]]) -> str:
    """Return raw model text. Callers validate JSON. Prompts are not logged."""
    settings = get_settings()
    log.info("llm_call provider=%s", settings.ai_provider)
    if settings.ai_provider == "openai":
        return _call_openai(messages)
    if settings.ai_provider == "ollama":
        return _call_ollama(messages)
    raise RuntimeError("complete() requires AI_PROVIDER=ollama or openai")
