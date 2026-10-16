"""Command-line tasks. Run from the backend folder, e.g.:

python -m app.cli sync-tenders --days 30   # one sync now
python -m app.cli scheduler                # keep syncing on a schedule (worker process)
"""

import argparse
import logging
import signal
from datetime import timedelta

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.sync_job import SyncScheduler, run_sync_job

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

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "sync-tenders":
        result = run_sync_job(SessionLocal, args.days, trigger="cli", enrich=not args.no_enrich)
        if result is None:
            logger.warning("Another tender sync is already running; try again later")
    elif args.command == "scheduler":
        scheduler = SyncScheduler(
            SessionLocal, interval=timedelta(hours=args.interval_hours), days=args.days
        )
        # Stop cleanly on Ctrl+C or `docker stop` (SIGTERM).
        signal.signal(signal.SIGTERM, lambda *_: scheduler.stop(timeout=0))
        try:
            scheduler.run_forever()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
