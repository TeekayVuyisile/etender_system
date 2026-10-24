"""Durable queue for AI summary jobs, on a Redis Stream.

A summary takes up to a minute (downloading documents, waiting for the Groq token budget), so it
runs outside the request. FastAPI's BackgroundTasks would lose the job if the process restarted
or crashed; a Redis Stream keeps it until a consumer confirms it's done:

- The API adds the job with XADD and returns straight away.
- Consumers (the worker, and each API process) read the stream as one consumer group, so each
  job goes to exactly one of them.
- A job is acknowledged (XACK) only once it has finished. If its consumer dies first, the job
  stays pending, and another consumer claims it (XAUTOCLAIM) after it has been idle a while.
- A job that has been delivered MAX_DELIVERIES times without finishing is given up, so a job
  that crashes its consumer can't loop forever.

Without Redis, the API runs summaries in-process with BackgroundTasks, as before.
"""

import logging
import os
import socket
import threading
import time
from collections.abc import Callable
from datetime import timedelta
from functools import partial

from redis import Redis
from redis.exceptions import RedisError, ResponseError
from sqlalchemy.orm import Session

from app.db.redis import create_redis_client
from app.services import cache
from app.services import notification_events as events
from app.services.llm import LLMError, get_llm_client
from app.services.notifications import get_notifier
from app.services.summarizer import run_summary_job
from app.services.summary_store import STALE_AFTER, get_summary_store

logger = logging.getLogger(__name__)

STREAM = cache.KEY_PREFIX + "queue:summaries"
GROUP = "summarizers"
# Finished jobs are deleted, so the stream only holds waiting and running jobs; this is a cap.
MAX_LENGTH = 1000
# Matches the summary store, which lets users retry a summary stuck this long.
CLAIM_IDLE = STALE_AFTER
CLAIM_CHECK_INTERVAL = timedelta(minutes=1)
MAX_DELIVERIES = 3
BLOCK_SECONDS = 10

Job = dict[str, str]


def _ensure_group(client: Redis) -> None:
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):  # the group already exists
            raise


def enqueue(redis_cache: cache.Cache, tender_id: int, user_id: int, team_id: int) -> bool:
    """Queue a summary job. Returns False if Redis isn't available (run it in-process then)."""
    job = {"tender_id": str(tender_id), "user_id": str(user_id), "team_id": str(team_id)}

    def add(client: Redis) -> str:
        _ensure_group(client)
        return client.xadd(STREAM, job, maxlen=MAX_LENGTH, approximate=True)

    return redis_cache.run(add) is not None


class SummaryConsumer:
    """Works through the queue in a background thread, one job at a time."""

    def __init__(
        self,
        client: Redis,
        handle: Callable[[Job], None],
        give_up: Callable[[Job], None],
        name: str | None = None,
    ) -> None:
        self.client = client
        self.handle = handle
        self.give_up = give_up
        self.name = name or f"{socket.gethostname()}-{os.getpid()}"
        self._group_ready = False
        self._next_claim_check = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def process_next(self, block_seconds: float | None = None) -> bool:
        """Handle one job: a stuck one that's due to be claimed, otherwise a new one (waiting up
        to `block_seconds` for it). Returns whether there was a job."""
        if not self._group_ready:
            _ensure_group(self.client)
            self._group_ready = True
        message = self._claim_stuck() or self._read_new(block_seconds)
        if message is None:
            return False
        message_id, job = message

        if self._deliveries(message_id) > MAX_DELIVERIES:
            logger.warning("Giving up on summary job %s after %d attempts", job, MAX_DELIVERIES)
            self.give_up(job)
        else:
            # If this raises (or the process dies), the job isn't acknowledged and is retried.
            self.handle(job)
        self.client.xack(STREAM, GROUP, message_id)
        self.client.xdel(STREAM, message_id)
        return True

    def _read_new(self, block_seconds: float | None) -> tuple[str, Job] | None:
        block = int(block_seconds * 1000) if block_seconds else None
        reply = self.client.xreadgroup(GROUP, self.name, {STREAM: ">"}, count=1, block=block)
        return reply[0][1][0] if reply else None

    def _claim_stuck(self) -> tuple[str, Job] | None:
        if time.monotonic() < self._next_claim_check:
            return None
        _, messages, *_ = self.client.xautoclaim(
            STREAM,
            GROUP,
            self.name,
            min_idle_time=int(CLAIM_IDLE.total_seconds() * 1000),
            start_id="0-0",
            count=1,
        )
        if messages:
            logger.info("Claimed stuck summary job %s", messages[0][1])
            return messages[0]
        self._next_claim_check = time.monotonic() + CLAIM_CHECK_INTERVAL.total_seconds()
        return None

    def _deliveries(self, message_id: str) -> int:
        pending = self.client.xpending_range(STREAM, GROUP, min=message_id, max=message_id, count=1)
        return pending[0]["times_delivered"] if pending else 1

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                self.process_next(block_seconds=BLOCK_SECONDS)
            except RedisError as error:
                # e.g. Redis restarted and lost the group: recreate it once it's back.
                logger.warning("Summary queue unavailable, retrying shortly: %s", error)
                self._group_ready = False
                self._stop.wait(5)
            except Exception:
                logger.exception("Summary job failed; it will be retried")
                self._stop.wait(5)

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self.run_forever, name="summary-consumer", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        self.leave_group()

    def leave_group(self) -> None:
        """Remove this consumer's name from the group (each process has its own, so they'd pile
        up otherwise). Skipped if it still has unfinished jobs: deleting them would lose them."""
        try:
            pending = self.client.xpending_range(
                STREAM, GROUP, min="-", max="+", count=1, consumername=self.name
            )
            if not pending:
                self.client.xgroup_delconsumer(STREAM, GROUP, self.name)
        except RedisError as error:
            logger.warning("Could not leave the summary queue group: %s", error)


def run_job(job: Job, session_factory: Callable[[], Session]) -> None:
    tender_id, user_id, team_id = (int(job[k]) for k in ("tender_id", "user_id", "team_id"))
    store = get_summary_store()
    try:
        llm = get_llm_client()
    except LLMError as error:
        store.save_failed(tender_id, str(error))
        return
    notifier = get_notifier()
    run_summary_job(
        tender_id,
        session_factory=session_factory,
        store=store,
        llm=llm,
        on_ready=lambda tender: notifier.send(events.summary_ready(user_id, team_id, tender)),
    )


def give_up_job(job: Job) -> None:
    get_summary_store().save_failed(
        int(job["tender_id"]), "Something went wrong while generating the summary"
    )


def start_consumer(session_factory: Callable[[], Session]) -> SummaryConsumer | None:
    """Start working through the queue in this process (no-op without Redis)."""
    # Its own client: waiting for jobs needs a longer timeout than the cache's.
    client = create_redis_client(socket_timeout=BLOCK_SECONDS + 5)
    if client is None:
        return None
    consumer = SummaryConsumer(
        client, handle=partial(run_job, session_factory=session_factory), give_up=give_up_job
    )
    consumer.start()
    return consumer


consumer: SummaryConsumer | None = None  # set when this process is consuming the queue
