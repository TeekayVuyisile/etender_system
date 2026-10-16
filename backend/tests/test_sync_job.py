from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobLock, Tender
from app.services import job_lock, sync_job
from app.services.etenders_client import OCDS_RELEASES_URL, PORTAL_TENDERS_URL
from app.services.sync_job import LOCK_NAME, SyncScheduler, run_sync_job, seconds_until_due
from tests.conftest import InMemorySyncRunStore, TestingSessionLocal, auth_header, register
from tests.test_tender_sync import make_portal_record, make_release

HOUR = timedelta(hours=1)


def mock_apis(release_ids: tuple[int, ...] = (1, 2)) -> None:
    respx.get(OCDS_RELEASES_URL).respond(json={"releases": [make_release(i) for i in release_ids]})
    respx.get(PORTAL_TENDERS_URL).respond(
        json={"recordsTotal": 1, "data": [make_portal_record(release_ids[0])]}
    )


# --- Job lock -------------------------------------------------------------------------


def test_lock_is_exclusive_until_released(db: Session):
    assert job_lock.acquire(db, "job", HOUR, owner="worker-a")
    assert not job_lock.acquire(db, "job", HOUR, owner="worker-b")
    assert job_lock.acquire(db, "job", HOUR, owner="worker-a")  # re-entrant for the owner

    job_lock.release(db, "job", owner="worker-a")

    assert job_lock.acquire(db, "job", HOUR, owner="worker-b")


def test_expired_lock_can_be_taken_over(db: Session):
    job_lock.acquire(db, "job", HOUR, owner="crashed-worker")
    db.get(JobLock, "job").locked_until = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    assert job_lock.acquire(db, "job", HOUR, owner="new-worker")


def test_release_by_non_owner_does_nothing(db: Session):
    job_lock.acquire(db, "job", HOUR, owner="worker-a")
    job_lock.release(db, "job", owner="worker-b")

    assert not job_lock.acquire(db, "job", HOUR, owner="worker-b")


# --- Running the job ---------------------------------------------------------------------


@respx.mock
def test_sync_job_records_a_successful_run(db: Session):
    mock_apis()
    runs = InMemorySyncRunStore()

    result = run_sync_job(TestingSessionLocal, days=3, trigger="cli", runs=runs)

    assert result is not None and result.created == 2
    assert db.query(Tender).count() == 2
    [run] = runs.runs
    assert run["status"] == "success"
    assert run["trigger"] == "cli"
    assert run["created"] == 2 and run["enriched"] == 1
    # The lock is released afterwards, so the next sync can run.
    assert job_lock.acquire(db, LOCK_NAME, HOUR, owner="someone-else")


def test_sync_job_is_skipped_while_another_sync_runs(db: Session):
    job_lock.acquire(db, LOCK_NAME, HOUR, owner="other-process")
    runs = InMemorySyncRunStore()

    assert run_sync_job(TestingSessionLocal, days=3, trigger="schedule", runs=runs) is None
    assert runs.runs == []


@respx.mock
def test_failed_sync_is_recorded_and_releases_the_lock(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("app.services.etenders_client.time.sleep", lambda _: None)
    respx.get(OCDS_RELEASES_URL).mock(side_effect=httpx.ConnectError("network down"))
    runs = InMemorySyncRunStore()

    with pytest.raises(httpx.ConnectError):
        run_sync_job(TestingSessionLocal, days=3, trigger="schedule", runs=runs)

    assert runs.runs[0]["status"] == "failed"
    assert "network down" in runs.runs[0]["error"]
    assert job_lock.acquire(db, LOCK_NAME, HOUR, owner="someone-else")


# --- Scheduling ----------------------------------------------------------------------------


def test_seconds_until_due():
    now = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    interval = timedelta(hours=6)

    assert seconds_until_due(None, interval, now) == 0  # never synced: sync now
    assert seconds_until_due(now - timedelta(hours=2), interval, now) == 4 * 3600
    assert seconds_until_due(now - timedelta(hours=7), interval, now) == 0  # overdue


def test_scheduler_syncs_immediately_when_never_run(monkeypatch: pytest.MonkeyPatch):
    calls = []
    scheduler = SyncScheduler(
        TestingSessionLocal, interval=HOUR, days=3, runs=InMemorySyncRunStore()
    )

    def fake_run(*args, **kwargs):
        calls.append(kwargs["trigger"])
        scheduler._stop.set()  # stop after the first run

    monkeypatch.setattr(sync_job, "run_sync_job", fake_run)
    scheduler.run_forever()

    assert calls == ["schedule"]
    assert scheduler.next_run_at is not None


def test_scheduler_waits_if_a_recent_sync_succeeded():
    runs = InMemorySyncRunStore()
    run_id = runs.start("cli", 3)
    runs.finish(run_id, "success", {})
    scheduler = SyncScheduler(TestingSessionLocal, interval=timedelta(hours=6), runs=runs)

    delay = scheduler._initial_delay()

    assert 5.9 * 3600 < delay <= 6 * 3600


def test_scheduler_keeps_going_after_a_failed_sync(monkeypatch: pytest.MonkeyPatch):
    calls = []
    scheduler = SyncScheduler(
        TestingSessionLocal, interval=timedelta(seconds=0), runs=InMemorySyncRunStore()
    )

    def flaky_run(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("eTenders is down")
        scheduler._stop.set()

    monkeypatch.setattr(sync_job, "run_sync_job", flaky_run)
    scheduler.run_forever()

    assert len(calls) == 2


# --- Status endpoint -----------------------------------------------------------------------


def test_sync_status_before_any_sync(client: TestClient):
    headers = auth_header(register(client))

    body = client.get("/api/tenders/sync-status", headers=headers).json()

    assert body["last_run"] is None
    assert body["last_success_at"] is None
    assert body["schedule_enabled"] is False


def test_sync_status_reports_latest_run(client: TestClient, sync_runs: InMemorySyncRunStore):
    headers = auth_header(register(client))
    ok = sync_runs.start("schedule", 3)
    sync_runs.finish(ok, "success", {"created": 5, "updated": 10, "enriched": 7})
    failed = sync_runs.start("schedule", 3)
    sync_runs.finish(failed, "failed", {"error": "OCDS API unavailable"})

    body = client.get("/api/tenders/sync-status", headers=headers).json()

    assert body["last_run"]["status"] == "failed"
    assert body["last_run"]["error"] == "OCDS API unavailable"
    assert body["last_success_at"] is not None  # the earlier successful run


def test_sync_status_requires_login(client: TestClient):
    assert client.get("/api/tenders/sync-status").status_code == 401
