import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import Session

from app.services import cache as cache_module
from app.services.api_keys import RateLimiter
from app.services.cache import Cache
from app.services.sync_job import run_sync_job
from tests.conftest import (
    InMemorySyncRunStore,
    TestingSessionLocal,
    add_tender,
    auth_header,
    register,
)
from tests.test_sync_job import mock_apis


class BrokenRedis:
    """A Redis client whose server is down: every command fails."""

    def __init__(self) -> None:
        self.calls = 0

    def __getattr__(self, name: str):
        def fail(*args, **kwargs):
            self.calls += 1
            raise RedisConnectionError("Connection refused")

        return fail


@pytest.fixture
def owner(client: TestClient) -> dict[str, str]:
    return auth_header(register(client))


# --- Read-through caching ----------------------------------------------------------------


def test_repeated_search_is_served_from_redis(
    client: TestClient, db: Session, owner: dict[str, str], redis_cache: Cache
):
    add_tender(db, title="Road maintenance")

    first = client.get("/api/tenders?q=road", headers=owner)
    # A tender added without a sync isn't seen: the second request never reaches the database.
    add_tender(db, title="Road resurfacing")
    second = client.get("/api/tenders?q=road", headers=owner)

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()
    assert second.json()["total"] == 1


def test_different_filters_and_pages_are_cached_separately(
    client: TestClient, db: Session, owner: dict[str, str], redis_cache: Cache
):
    add_tender(db)
    client.get("/api/tenders", headers=owner)

    assert client.get("/api/tenders?page=2", headers=owner).headers["X-Cache"] == "MISS"
    assert client.get("/api/tenders?province=Limpopo", headers=owner).headers["X-Cache"] == "MISS"


@respx.mock
def test_sync_invalidates_cached_tender_data(
    client: TestClient, db: Session, owner: dict[str, str], redis_cache: Cache
):
    assert client.get("/api/tenders", headers=owner).json()["total"] == 0
    mock_apis()

    run_sync_job(TestingSessionLocal, days=3, trigger="cli", runs=InMemorySyncRunStore())

    after = client.get("/api/tenders", headers=owner)
    assert after.headers["X-Cache"] == "MISS"
    assert after.json()["total"] == 2


def test_tender_detail_and_buyers_are_cached(
    client: TestClient, db: Session, owner: dict[str, str], redis_cache: Cache
):
    tender = add_tender(db, buyer_name="City of Tshwane")

    client.get(f"/api/tenders/{tender.id}", headers=owner)
    client.get("/api/tenders/buyers", headers=owner)
    detail = client.get(f"/api/tenders/{tender.id}", headers=owner)
    buyers = client.get("/api/tenders/buyers", headers=owner)

    assert detail.headers["X-Cache"] == "HIT"
    assert detail.json()["buyer_name"] == "City of Tshwane"
    assert buyers.headers["X-Cache"] == "HIT"
    assert buyers.json() == [{"name": "City of Tshwane", "open_tenders": 1}]


def test_missing_tender_is_not_cached(
    client: TestClient, owner: dict[str, str], redis_cache: Cache
):
    assert client.get("/api/tenders/999", headers=owner).status_code == 404
    assert redis_cache.client.keys("tih:tender:*") == []


def test_cache_hits_still_count_towards_the_free_plan_limit(
    client: TestClient, db: Session, redis_cache: Cache
):
    token = auth_header(register(client, plan="free"))
    add_tender(db)
    for q in ("road", "water", "school"):
        assert client.get(f"/api/tenders?q={q}", headers=token).status_code == 200

    blocked = client.get("/api/tenders?q=bridge", headers=token)

    assert blocked.status_code == 403
    # Repeating an already counted search is allowed, and now comes from the cache.
    assert client.get("/api/tenders?q=road", headers=token).headers["X-Cache"] == "HIT"


def test_sync_status_is_cached_until_a_sync_runs(
    client: TestClient,
    owner: dict[str, str],
    sync_runs: InMemorySyncRunStore,
    redis_cache: Cache,
):
    assert client.get("/api/tenders/sync-status", headers=owner).json()["last_run"] is None
    assert client.get("/api/tenders/sync-status", headers=owner).headers["X-Cache"] == "HIT"

    with respx.mock:
        mock_apis()
        run_sync_job(TestingSessionLocal, days=3, trigger="cli", runs=sync_runs)

    status = client.get("/api/tenders/sync-status", headers=owner)
    assert status.headers["X-Cache"] == "MISS"
    assert status.json()["last_run"]["status"] == "success"


def test_without_redis_there_is_no_cache_header(
    client: TestClient, db: Session, owner: dict[str, str]
):
    add_tender(db)
    response = client.get("/api/tenders", headers=owner)

    assert response.status_code == 200
    assert "X-Cache" not in response.headers


# --- Failing open --------------------------------------------------------------------------


def test_requests_still_work_when_redis_is_down(
    client: TestClient, db: Session, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    broken = BrokenRedis()
    monkeypatch.setattr(cache_module, "_cache", Cache(broken))
    add_tender(db)

    first = client.get("/api/tenders", headers=owner)
    calls_after_first = broken.calls
    second = client.get("/api/tenders", headers=owner)

    assert first.status_code == second.status_code == 200
    assert second.json()["total"] == 1
    # After the first error Redis is skipped for a while, instead of timing out every request.
    assert broken.calls == calls_after_first == 1


def test_health_reports_cache_status(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    assert client.get("/api/health").json()["cache"] == "disabled"

    monkeypatch.setattr(cache_module, "_cache", Cache(BrokenRedis()))
    assert client.get("/api/health").json()["cache"] == "unavailable"


def test_health_reports_connected_redis(client: TestClient, redis_cache: Cache):
    assert client.get("/api/health").json()["cache"] == "connected"


# --- Shared rate limits --------------------------------------------------------------------


def test_rate_limit_is_shared_between_api_processes(redis_cache: Cache):
    # Two limiter objects stand in for two API processes: in memory each would allow 2 requests.
    process_a = RateLimiter("test", limit=2, window_seconds=60)
    process_b = RateLimiter("test", limit=2, window_seconds=60)

    process_a.check("key-1")
    process_b.check("key-1")
    with pytest.raises(HTTPException) as error:
        process_a.check("key-1")

    assert error.value.status_code == 429
    assert 0 < int(error.value.headers["Retry-After"]) <= 60
    process_b.check("key-2")  # other keys are unaffected


def test_rate_limit_keys_expire_with_the_window(redis_cache: Cache):
    RateLimiter("test", limit=5, window_seconds=60).check("key-1")

    ttl_ms = redis_cache.client.pttl("tih:ratelimit:test:key-1")

    assert 0 < ttl_ms <= 60_000


def test_rate_limit_falls_back_to_memory_when_redis_is_down(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cache_module, "_cache", Cache(BrokenRedis()))
    limiter = RateLimiter("test", limit=1, window_seconds=60)

    limiter.check("key-1")
    with pytest.raises(HTTPException):
        limiter.check("key-1")
