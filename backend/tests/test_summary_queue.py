from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import llm as llm_module
from app.services import summary_queue
from app.services.cache import Cache
from app.services.llm import LLMError, TokenBudget, estimate_tokens
from app.services.notifications import InAppChannel, Notifier
from app.services.summary_queue import STREAM, SummaryConsumer
from tests.conftest import (
    FakeLLM,
    InMemoryNotificationStore,
    InMemorySummaryStore,
    TestingSessionLocal,
    add_tender,
    auth_header,
    register,
)


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return auth_header(register(client))


@pytest.fixture
def queue_services(
    monkeypatch: pytest.MonkeyPatch,
    summary_store: InMemorySummaryStore,
    llm: FakeLLM,
    notification_store: InMemoryNotificationStore,
) -> None:
    """Point the queue's job runner at the test stores (the API's overrides don't reach it)."""
    monkeypatch.setattr(summary_queue, "get_summary_store", lambda: summary_store)
    monkeypatch.setattr(summary_queue, "get_llm_client", lambda: llm)
    monkeypatch.setattr(
        summary_queue, "get_notifier", lambda: Notifier([InAppChannel(notification_store)])
    )


def make_consumer(redis_cache: Cache, name: str = "worker-1", **kwargs) -> SummaryConsumer:
    return SummaryConsumer(
        redis_cache.client,
        handle=kwargs.pop(
            "handle",
            lambda job: summary_queue.run_job(job, session_factory=TestingSessionLocal),
        ),
        give_up=kwargs.pop("give_up", summary_queue.give_up_job),
        name=name,
    )


# --- Queueing ----------------------------------------------------------------------------


def test_summary_request_is_queued_not_run_in_the_api(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    llm: FakeLLM,
    redis_cache: Cache,
):
    tender = add_tender(db)

    response = client.post(f"/api/tenders/{tender.id}/summary", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "processing"
    assert llm.prompts == []  # nothing ran in the request
    [(_, job)] = redis_cache.client.xrange(STREAM)
    assert job["tender_id"] == str(tender.id)


def test_consumer_generates_the_summary_and_notifies(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    redis_cache: Cache,
    queue_services: None,
    notification_store: InMemoryNotificationStore,
):
    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)

    assert make_consumer(redis_cache).process_next() is True

    result = client.get(f"/api/tenders/{tender.id}/summary", headers=headers).json()
    assert result["status"] == "ready"
    assert [n["type"] for n in notification_store.docs] == ["summary_ready"]
    # Finished jobs are acknowledged and removed.
    assert redis_cache.client.xlen(STREAM) == 0
    assert make_consumer(redis_cache).process_next() is False


def test_each_job_goes_to_one_consumer(
    client: TestClient, db: Session, headers: dict[str, str], redis_cache: Cache
):
    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)
    handled: list[str] = []

    for name in ("api-1", "worker-1"):
        consumer = make_consumer(redis_cache, name, handle=lambda job, n=name: handled.append(n))
        consumer.process_next()

    assert handled == ["api-1"]


def test_without_redis_the_summary_runs_in_the_api(
    client: TestClient, db: Session, headers: dict[str, str], llm: FakeLLM
):
    tender = add_tender(db)

    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)

    assert len(llm.prompts) == 1
    assert client.get(f"/api/tenders/{tender.id}/summary", headers=headers).json()["status"] == (
        "ready"
    )


# --- Surviving crashes ---------------------------------------------------------------------


def test_job_of_a_crashed_consumer_is_claimed_by_another(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    redis_cache: Cache,
    queue_services: None,
    monkeypatch: pytest.MonkeyPatch,
):
    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)

    def crash(job: dict[str, str]) -> None:
        raise RuntimeError("process killed mid-job")

    with pytest.raises(RuntimeError):
        make_consumer(redis_cache, "api-1", handle=crash).process_next()
    # The job wasn't acknowledged: it's still pending, owned by the dead consumer.
    assert redis_cache.client.xpending(STREAM, summary_queue.GROUP)["pending"] == 1

    monkeypatch.setattr(summary_queue, "CLAIM_IDLE", timedelta(0))
    assert make_consumer(redis_cache, "worker-1").process_next() is True

    assert client.get(f"/api/tenders/{tender.id}/summary", headers=headers).json()["status"] == (
        "ready"
    )
    assert redis_cache.client.xpending(STREAM, summary_queue.GROUP)["pending"] == 0


def test_job_that_keeps_crashing_is_given_up(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    redis_cache: Cache,
    queue_services: None,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(summary_queue, "CLAIM_IDLE", timedelta(0))
    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)

    def crash(job: dict[str, str]) -> None:
        raise RuntimeError("crashes every time")

    for attempt in range(summary_queue.MAX_DELIVERIES):
        with pytest.raises(RuntimeError):
            make_consumer(redis_cache, f"worker-{attempt}", handle=crash).process_next()
    make_consumer(redis_cache, "worker-last", handle=crash).process_next()

    result = client.get(f"/api/tenders/{tender.id}/summary", headers=headers).json()
    assert result["status"] == "failed"
    assert redis_cache.client.xlen(STREAM) == 0


def test_job_fails_cleanly_when_ai_is_not_configured(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    redis_cache: Cache,
    queue_services: None,
    monkeypatch: pytest.MonkeyPatch,
):
    def no_key():
        raise LLMError("AI summaries are not configured (GROQ_API_KEY is missing)")

    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)
    monkeypatch.setattr(summary_queue, "get_llm_client", no_key)

    make_consumer(redis_cache).process_next()

    result = client.get(f"/api/tenders/{tender.id}/summary", headers=headers).json()
    assert result["status"] == "failed"
    assert "GROQ_API_KEY" in result["error"]


def test_stopped_consumer_leaves_the_group_unless_it_has_unfinished_jobs(
    client: TestClient, db: Session, headers: dict[str, str], redis_cache: Cache
):
    tender = add_tender(db)
    client.post(f"/api/tenders/{tender.id}/summary", headers=headers)
    idle = make_consumer(redis_cache, "idle", handle=lambda job: None)
    idle.process_next()  # finishes the job
    busy = make_consumer(redis_cache, "busy")
    client.post(f"/api/tenders/{add_tender(db).id}/summary", headers=headers)
    busy._read_new(None)  # takes a job and never finishes it

    idle.leave_group()
    busy.leave_group()

    consumers = redis_cache.client.xinfo_consumers(STREAM, summary_queue.GROUP)
    assert [c["name"] for c in consumers] == ["busy"]


# --- Shared Groq token budget --------------------------------------------------------------


def test_token_budget_is_shared_between_processes(redis_cache: Cache):
    # Two budget objects stand in for the API and the worker using the same Groq key.
    api, worker = TokenBudget(1000), TokenBudget(1000)

    assert api.try_reserve(600) == 0
    wait = worker.try_reserve(600)

    assert 0 < wait <= 60.1
    assert worker.try_reserve(400) == 0  # still fits in what's left


def test_call_larger_than_the_budget_runs_when_nothing_else_is_running(redis_cache: Cache):
    budget = TokenBudget(1000)

    with budget.reserve(5000):
        pass

    assert budget.try_reserve(1) > 0


def test_waiting_longer_than_allowed_raises(redis_cache: Cache):
    budget = TokenBudget(1000, max_wait_seconds=1)
    budget.try_reserve(1000)

    with pytest.raises(LLMError, match="busy"):
        with budget.reserve(500):
            pass


def test_without_redis_calls_run_one_at_a_time_in_the_process():
    budget = TokenBudget(1000)

    with budget.reserve(1000):
        assert llm_module._llm_lock.locked()
    assert budget.try_reserve(1000) is None


def test_estimate_includes_prompt_and_requested_output():
    assert estimate_tokens("a" * 400, "b" * 3600, max_tokens=1600) == 2600
