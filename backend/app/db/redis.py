from redis import Redis

from app.core.config import settings


def create_redis_client(socket_timeout: float = 1) -> Redis | None:
    """A Redis client, or None when REDIS_URL isn't set.

    Like MongoClient, it connects lazily and keeps a connection pool, so one is shared by the
    whole process. The timeouts are short on purpose: Redis only speeds things up, so a slow or
    unreachable Redis must fail fast rather than hold up requests. (The summary queue consumer
    passes a longer one, because it waits on Redis for new jobs.)
    """
    if not settings.redis_url:
        return None
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=socket_timeout,
        socket_connect_timeout=1,
        health_check_interval=30,
    )
