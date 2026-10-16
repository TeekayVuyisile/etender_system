"""Running the tender sync as a job: one at a time, recorded, and on a schedule."""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import job_lock
from app.services.sync_runs import SyncRunStore, get_sync_run_store
from app.services.tender_sync import SyncResult, default_client, sync_tenders

logger = logging.getLogger(__name__)

LOCK_NAME = "tender_sync"
# Longer than any realistic sync; if a process dies mid-sync, the lock frees itself after this.
LOCK_TTL = timedelta(hours=2)


def run_sync_job(
    session_factory: Callable[[], Session],
    days: int,
    trigger: str,
    enrich: bool = True,
    runs: SyncRunStore | None = None,
    client_factory: Callable[[], httpx.Client] = default_client,
) -> SyncResult | None:
    """Run one tender sync. Returns None (without syncing) if another sync is running."""
    runs = runs or get_sync_run_store()
    with session_factory() as db:
        if not job_lock.acquire(db, LOCK_NAME, LOCK_TTL):
            logger.info("Tender sync skipped: another sync is already running")
            return None
        run_id = runs.start(trigger, days)
        try:
            with client_factory() as client:
                result = sync_tenders(db, client, days=days, enrich=enrich)
        except Exception as error:
            db.rollback()
            logger.exception("Tender sync failed")
            runs.finish(run_id, "failed", {"error": str(error)[:500]})
            raise
        finally:
            job_lock.release(db, LOCK_NAME)

    runs.finish(run_id, "success", result.as_dict())
    logger.info("Tender sync finished: %s", result.as_dict())
    return result


def seconds_until_due(
    last_success_at: datetime | None, interval: timedelta, now: datetime | None = None
) -> float:
    """How long to wait before the next sync (0 if one is due now)."""
    if last_success_at is None:
        return 0.0
    now = now or datetime.now(UTC)
    last = last_success_at if last_success_at.tzinfo else last_success_at.replace(tzinfo=UTC)
    return max(0.0, (last + interval - now).total_seconds())


class SyncScheduler:
    """Runs the tender sync every `interval` in a background thread.

    On start it checks when the last successful sync was, so restarting the app doesn't
    trigger an immediate re-sync if one ran recently.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        interval: timedelta | None = None,
        days: int | None = None,
        runs: SyncRunStore | None = None,
    ) -> None:
        self.session_factory = session_factory
        # `is not None` rather than `or`: a zero interval (used in tests) is falsy.
        self.interval = (
            interval if interval is not None else timedelta(hours=settings.sync_interval_hours)
        )
        self.days = days if days is not None else settings.sync_days
        self.runs = runs
        self.next_run_at: datetime | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _initial_delay(self) -> float:
        try:
            last = (self.runs or get_sync_run_store()).latest_success()
        except Exception:
            logger.warning("Could not read sync history; syncing now", exc_info=True)
            return 0.0
        last_at = (last.get("finished_at") or last.get("started_at")) if last else None
        return seconds_until_due(last_at, self.interval)

    def run_forever(self) -> None:
        delay = self._initial_delay()
        while not self._stop.is_set():
            self.next_run_at = datetime.now(UTC) + timedelta(seconds=delay)
            logger.info("Next tender sync at %s", self.next_run_at.isoformat(timespec="minutes"))
            if self._stop.wait(delay):
                break
            try:
                run_sync_job(self.session_factory, self.days, trigger="schedule", runs=self.runs)
            except Exception:
                pass  # already logged and recorded; try again next interval
            delay = self.interval.total_seconds()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run_forever, name="tender-sync", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)


scheduler: SyncScheduler | None = None  # set when the in-app scheduler is running
