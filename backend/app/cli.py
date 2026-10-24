"""Command-line tasks. Run from the backend folder, e.g.:

python -m app.cli sync-tenders --days 30   # one sync now
python -m app.cli scheduler                # sync, reminders and summary queue (worker process)
python -m app.cli prepare-demo             # AI summaries for demo workspaces
"""

import argparse
import logging
import signal
from datetime import timedelta

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import summary_queue
from app.services.demo import prepare_demo_summaries
from app.services.llm import get_llm_client
from app.services.summary_store import get_summary_store
from app.services.sync_job import SyncScheduler, demo_upkeep_job, reminder_job, run_sync_job

logger = logging.getLogger("app.cli")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync-tenders", help="Import tenders from the eTenders APIs now")
    sync.add_argument("--days", type=int, default=30, help="How many days back to import")
    sync.add_argument("--no-enrich", action="store_true", help="Skip eTenders portal enrichment")

    schedule = commands.add_parser("scheduler", help="Sync tenders on a schedule until stopped")
    schedule.add_argument(
        "--interval-hours",
        type=float,
        default=settings.sync_interval_hours,
        help=f"Hours between syncs (default {settings.sync_interval_hours})",
    )
    schedule.add_argument(
        "--days",
        type=int,
        default=settings.sync_days,
        help=f"How many days back each sync imports (default {settings.sync_days})",
    )

    commands.add_parser(
        "prepare-demo", help="Generate AI summaries so new demo workspaces show them"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "sync-tenders":
        result = run_sync_job(SessionLocal, args.days, trigger="cli", enrich=not args.no_enrich)
        if result is None:
            logger.warning("Another tender sync is already running; try again later")
    elif args.command == "prepare-demo":
        generated = prepare_demo_summaries(SessionLocal, get_summary_store(), get_llm_client())
        logger.info("Generated %d demo summaries", generated)
    elif args.command == "scheduler":
        scheduler = SyncScheduler(
            SessionLocal, interval=timedelta(hours=args.interval_hours), days=args.days
        )
        # Hourly background jobs alongside the sync: reminders, and demo upkeep if enabled.
        jobs = [reminder_job(SessionLocal)]
        if settings.demo_mode_enabled:
            jobs.append(demo_upkeep_job(SessionLocal))
        for job in jobs:
            job.start()
        # Also work through queued AI summaries (with Redis), alongside the API processes.
        if settings.summary_worker_enabled and (
            consumer := summary_queue.start_consumer(SessionLocal)
        ):
            jobs.append(consumer)

        def stop(*_: object) -> None:
            scheduler.stop(timeout=0)
            for job in jobs:
                job.stop(timeout=0)

        # Stop cleanly on Ctrl+C or `docker stop` (SIGTERM).
        signal.signal(signal.SIGTERM, stop)
        try:
            scheduler.run_forever()
        except KeyboardInterrupt:
            stop()
            logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
