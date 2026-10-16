"""Minimal client for Groq's OpenAI-compatible chat completions API."""

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# The free tier allows ~8,000 tokens per minute, and one summary uses most of that,
# so LLM calls are made one at a time across the whole app.
_llm_lock = threading.Lock()


class LLMError(Exception):
    pass


@dataclass
class LLMResponse:
    data: dict[str, Any]
    model: str
    total_tokens: int | None


class LLMClient(Protocol):
    def chat_json(self, system: str, user: str, max_tokens: int = 2000) -> LLMResponse: ...


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

        with _llm_lock:
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
