"""Command-line tasks. Run from the backend folder, e.g.:

python -m app.cli sync-tenders --days 30
"""

import argparse
import logging
from datetime import UTC, datetime

from pymongo.errors import PyMongoError

from app.db.mongo import get_mongo_db
from app.db.session import SessionLocal
from app.services.tender_sync import default_client, sync_tenders

logger = logging.getLogger("app.cli")


def run_sync(days: int, enrich: bool) -> None:
    started_at = datetime.now(UTC)
    with SessionLocal() as db, default_client() as client:
        result = sync_tenders(db, client, days=days, enrich=enrich)

    logger.info("Sync finished: %s", result.as_dict())
    try:
        get_mongo_db()["tender_sync_runs"].insert_one(
            {"started_at": started_at, "days": days, "enrich": enrich, **result.as_dict()}
        )
    except PyMongoError:
        logger.warning("Could not record sync run in MongoDB", exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync-tenders", help="Import tenders from the eTenders APIs")
    sync.add_argument("--days", type=int, default=30, help="How many days back to import")
    sync.add_argument("--no-enrich", action="store_true", help="Skip eTenders portal enrichment")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "sync-tenders":
        run_sync(days=args.days, enrich=not args.no_enrich)


if __name__ == "__main__":
    main()
