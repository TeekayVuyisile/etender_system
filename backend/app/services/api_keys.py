"""API keys for the public API: creation, verification and a simple rate limit."""

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ApiKey, User

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


class RateLimiter:
    """Sliding one-minute window per key, kept in memory.

    Good enough for a single server process; with several servers this would move to a
    shared store such as Redis.
    """

    def __init__(self, limit: int = RATE_LIMIT_PER_MINUTE, window_seconds: float = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key_id: int) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key_id]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = int(self.window - (now - hits[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit of {self.limit} requests per minute exceeded",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


rate_limiter = RateLimiter()
