"""API keys for the public API: creation, verification and a simple rate limit."""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Hashable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ApiKey, User
from app.services import cache

KEY_PREFIX = "tih_"
RATE_LIMIT_PER_MINUTE = 60
# Writing last_used_at on every request would add a database write per call; once a
# minute is plenty to show "last used" in the UI.
LAST_USED_RESOLUTION = timedelta(minutes=1)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_key(db: Session, user: User, name: str) -> tuple[ApiKey, str]:
    """Create a key for the user's team. Returns the record and the raw key (shown once)."""
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    api_key = ApiKey(
        team_id=user.team_id,
        name=name,
        prefix=raw_key[:12],
        key_hash=hash_key(raw_key),
        created_by_id=user.id,
    )
    db.add(api_key)
    db.commit()
    return api_key, raw_key


def verify_key(db: Session, raw_key: str) -> ApiKey | None:
    if not raw_key.startswith(KEY_PREFIX):
        return None
    api_key = db.scalar(
        select(ApiKey)
        .where(ApiKey.key_hash == hash_key(raw_key), ApiKey.revoked_at.is_(None))
        .options(joinedload(ApiKey.team))
    )
    if api_key is None:
        return None
    now = datetime.now(UTC)
    last = api_key.last_used_at
    if (
        last is None
        or now - (last if last.tzinfo else last.replace(tzinfo=UTC)) > LAST_USED_RESOLUTION
    ):
        api_key.last_used_at = now
        db.commit()
    return api_key


# Sliding-window rate limit, run inside Redis as one atomic step so two API processes checking
# the same key at once can't both slip under the limit. KEYS[1] is a sorted set of request
# times; ARGV: window (ms), limit, a unique request id. Returns -1 if allowed, otherwise the
# milliseconds until a slot frees up. Redis's own clock is used so servers can't disagree.
SLIDING_WINDOW_SCRIPT = """
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms - window)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return window - (now_ms - tonumber(oldest[2]))
end
redis.call('ZADD', KEYS[1], now_ms, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return -1
"""


class RateLimiter:
    """Sliding-window rate limit per key.

    Requests are counted in Redis when it's configured, so the limit holds across every API
    process and survives restarts. Without Redis (or while it's unreachable) each process
    counts in memory instead.
    """

    def __init__(
        self, name: str, limit: int = RATE_LIMIT_PER_MINUTE, window_seconds: float = 60
    ) -> None:
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self.period_label = (
            "minute" if window_seconds == 60 else f"{window_seconds / 3600:g} hour(s)"
        )
        self._hits: dict[Hashable, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key_id: Hashable) -> None:
        retry_after = self._check_redis(key_id)
        if retry_after is None:
            retry_after = self._check_memory(key_id)
        if retry_after > 0:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests: the limit is {self.limit} per {self.period_label}",
                headers={"Retry-After": str(retry_after)},
            )

    def _check_redis(self, key_id: Hashable) -> int | None:
        """Seconds to wait (0 if allowed), or None if Redis isn't available."""
        key = f"{cache.KEY_PREFIX}ratelimit:{self.name}:{key_id}"
        wait_ms = cache.get_cache().run(
            lambda r: r.register_script(SLIDING_WINDOW_SCRIPT)(
                keys=[key], args=[int(self.window * 1000), self.limit, uuid4().hex]
            )
        )
        if wait_ms is None:
            return None
        return 0 if int(wait_ms) < 0 else int(wait_ms) // 1000 + 1

    def _check_memory(self, key_id: Hashable) -> int:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key_id]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return int(self.window - (now - hits[0])) + 1
            hits.append(now)
            return 0


rate_limiter = RateLimiter("api_key")
