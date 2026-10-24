"""Minimal client for Groq's OpenAI-compatible chat completions API."""

import json
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx

from app.core.config import settings
from app.services import cache

logger = logging.getLogger(__name__)

# Without Redis, LLM calls are made one at a time in this process instead (one summary uses
# most of the free tier's per-minute tokens).
_llm_lock = threading.Lock()

# Like the API rate limit (see api_keys.py), but each entry in the window counts its tokens:
# entries are "<request id>:<tokens>", and the call may go ahead only if the tokens used in the
# last minute plus its own fit the budget. Returns -1 when the tokens are reserved, otherwise
# the milliseconds until the oldest entry leaves the window.
TOKEN_BUDGET_SCRIPT = """
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
local window = tonumber(ARGV[1])
local tokens = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms - window)
local used = 0
for _, member in ipairs(redis.call('ZRANGE', KEYS[1], 0, -1)) do
  used = used + tonumber(string.match(member, ':(%d+)$'))
end
if used > 0 and used + tokens > tonumber(ARGV[2]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return window - (now_ms - tonumber(oldest[2]))
end
redis.call('ZADD', KEYS[1], now_ms, ARGV[4] .. ':' .. tokens)
redis.call('PEXPIRE', KEYS[1], window)
return -1
"""


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    data: dict[str, Any]
    model: str
    total_tokens: int | None


class LLMClient(Protocol):
    def chat_json(self, system: str, user: str, max_tokens: int = 2000) -> LLMResponse: ...


class TokenBudget:
    """Groq's per-minute token limit, shared by every process that calls Groq.

    The limit applies to the API key, so the API processes and the worker all spend the same
    budget. Each call reserves its tokens in Redis first and waits if the last minute's calls
    have used the budget up, instead of all of them hitting Groq and getting 429 errors.
    """

    KEY = "llm:tokens"

    def __init__(self, tokens_per_minute: int, max_wait_seconds: float = 90) -> None:
        self.tokens_per_minute = tokens_per_minute
        self.max_wait_seconds = max_wait_seconds

    def try_reserve(self, tokens: int) -> float | None:
        """Seconds to wait before trying again (0 if reserved), or None without Redis."""
        wait_ms = cache.get_cache().run(
            lambda r: r.register_script(TOKEN_BUDGET_SCRIPT)(
                keys=[cache.KEY_PREFIX + self.KEY],
                args=[60_000, self.tokens_per_minute, tokens, uuid4().hex],
            )
        )
        if wait_ms is None:
            return None
        return 0 if int(wait_ms) < 0 else int(wait_ms) / 1000 + 0.1

    @contextmanager
    def reserve(self, tokens: int) -> Iterator[None]:
        # A call larger than the whole budget still goes ahead once nothing else is running.
        tokens = min(tokens, self.tokens_per_minute)
        deadline = time.monotonic() + self.max_wait_seconds
        while (wait := self.try_reserve(tokens)) is not None and wait > 0:
            if time.monotonic() + wait > deadline:
                raise LLMError("AI service is busy, please try again later")
            logger.info("Groq token budget used up, waiting %.0fs", wait)
            time.sleep(wait)
        if wait is None:
            with _llm_lock:
                yield
        else:
            yield


def estimate_tokens(system: str, user: str, max_tokens: int) -> int:
    """Groq counts the prompt plus the requested max_tokens against the limit up front."""
    return (len(system) + len(user)) // 4 + max_tokens


token_budget = TokenBudget(settings.groq_tokens_per_minute)


class GroqClient:
    def __init__(self, api_key: str, model: str, base_url: str, max_wait_seconds: float = 65):
        self.model = model
        self.max_wait_seconds = max_wait_seconds
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(120.0, connect=15.0),
        )

    def chat_json(self, system: str, user: str, max_tokens: int = 2000) -> LLMResponse:
        """Send a chat request that must return a JSON object."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_completion_tokens": max_tokens,
        }
        if self.model.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"  # reasoning tokens count towards rate limits

        with token_budget.reserve(estimate_tokens(system, user, max_tokens)):
            body = self._post_with_retries(payload)

        try:
            content = body["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise LLMError("The AI model returned an invalid response") from error
        if not isinstance(data, dict):
            raise LLMError("The AI model returned an invalid response")
        return LLMResponse(
            data=data,
            model=body.get("model", self.model),
            total_tokens=(body.get("usage") or {}).get("total_tokens"),
        )

    def _post_with_retries(self, payload: dict[str, Any], attempts: int = 4) -> dict[str, Any]:
        for attempt in range(1, attempts + 1):
            try:
                response = self._http.post("/chat/completions", json=payload)
            except httpx.HTTPError as error:
                if attempt == attempts:
                    raise LLMError(f"Could not reach the AI service: {error}") from error
                time.sleep(3 * attempt)
                continue

            if response.status_code == 429 and attempt < attempts:
                # Rate limited: wait as long as Groq asks (at least a few seconds, capped).
                # Groq counts the requested max tokens against the per-minute limit up front.
                retry_after = float(response.headers.get("retry-after") or 20)
                wait = min(max(retry_after, 5.0) + 1, self.max_wait_seconds)
                logger.info("Groq rate limit hit, waiting %.0fs", wait)
                time.sleep(wait)
                continue
            if response.status_code >= 500 and attempt < attempts:
                time.sleep(3 * attempt)
                continue
            if response.status_code != 200:
                raise LLMError(f"AI service error ({response.status_code}): {response.text[:200]}")
            return response.json()
        raise LLMError("AI service is busy, please try again later")


_client: GroqClient | None = None


def get_llm_client() -> LLMClient:
    """FastAPI dependency (and job helper) returning the shared Groq client."""
    global _client
    if not settings.groq_api_key:
        raise LLMError("AI summaries are not configured (GROQ_API_KEY is missing)")
    if _client is None:
        _client = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_base_url)
    return _client
