"""Redis cache for tender data, invalidated whenever tenders change.

Tender data only changes when the sync runs (every few hours), so searches, buyer lists and
tender details can be served from Redis instead of PostgreSQL. Rather than finding and deleting
every affected key after a sync, cached tender keys include a version number: the sync bumps
the version, new requests build new keys, and the old entries are never read again (their TTL
cleans them up).

Redis is optional and only ever an optimisation: if it isn't configured or can't be reached,
every lookup is a miss and the app reads from PostgreSQL as before.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import Response
from redis import Redis
from redis.exceptions import RedisError

from app.db.redis import create_redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Every key starts with this, so the app can share one Redis database with other projects.
KEY_PREFIX = "tih:"
TENDERS_VERSION_KEY = "tenders:version"
# After a Redis error, skip Redis for a while instead of waiting for a timeout on every request.
RETRY_AFTER_ERROR_SECONDS = 30


def digest(params: dict[str, Any]) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class Cache:
    def __init__(self, client: Redis | None) -> None:
        self.client = client
        self._skip_until = 0.0

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def run(self, operation: Callable[[Redis], T]) -> T | None:
        """Run a Redis command. Returns None if Redis is off or failing (callers treat it as a
        miss), so a Redis outage never turns into an error for the user."""
        if self.client is None or time.monotonic() < self._skip_until:
            return None
        try:
            return operation(self.client)
        except RedisError as error:
            logger.warning("Redis unavailable, continuing without it: %s", error)
            self._skip_until = time.monotonic() + RETRY_AFTER_ERROR_SECONDS
            return None

    def get_json(self, key: str) -> Any | None:
        raw = self.run(lambda r: r.get(KEY_PREFIX + key))
        return json.loads(raw) if raw is not None else None

    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = json.dumps(value, default=str)
        self.run(lambda r: r.set(KEY_PREFIX + key, payload, ex=ttl_seconds))

    def delete(self, key: str) -> None:
        self.run(lambda r: r.delete(KEY_PREFIX + key))

    def get_or_load(self, key: str, ttl_seconds: int, load: Callable[[], T]) -> tuple[T, bool]:
        """Read-through caching: the cached value if there is one, otherwise `load()` (stored
        for next time). Also returns whether it was a cache hit."""
        cached = self.get_json(key)
        if cached is not None:
            return cached, True
        value = load()
        if value is not None:
            self.set_json(key, value, ttl_seconds)
        return value, False

    def tenders_version(self) -> int:
        return int(self.run(lambda r: r.get(KEY_PREFIX + TENDERS_VERSION_KEY)) or 0)

    def tender_key(self, name: str, params: dict[str, Any]) -> str:
        """Key for cached tender data, tied to the current tenders version."""
        return f"{name}:v{self.tenders_version()}:{digest(params)}"

    def invalidate_tenders(self) -> None:
        """Call after tenders change: every cached search, buyer list and detail goes stale."""
        self.run(lambda r: r.incr(KEY_PREFIX + TENDERS_VERSION_KEY))

    def status(self) -> str:
        if self.client is None:
            return "disabled"
        return "connected" if self.run(lambda r: r.ping()) else "unavailable"


def mark_response(response: Response, cache: Cache, hit: bool) -> None:
    """X-Cache header, to see in the browser's network tab whether Redis answered."""
    if cache.enabled:
        response.headers["X-Cache"] = "HIT" if hit else "MISS"


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(create_redis_client())
    return _cache
