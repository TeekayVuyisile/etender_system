"""History of tender sync runs, stored in MongoDB (collection: tender_sync_runs)."""

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.db.mongo import get_mongo_db

logger = logging.getLogger(__name__)


class SyncRunStore(Protocol):
    def start(self, trigger: str, days: int) -> str | None: ...
    def finish(self, run_id: str | None, status: str, details: dict[str, Any]) -> None: ...
    def latest(self) -> dict[str, Any] | None: ...
    def latest_success(self) -> dict[str, Any] | None: ...


class MongoSyncRunStore:
    """Recording runs is best-effort: a MongoDB outage must never stop a sync."""

    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def start(self, trigger: str, days: int) -> str | None:
        try:
            result = self.collection.insert_one(
                {
                    "status": "running",
                    "trigger": trigger,
                    "days": days,
                    "started_at": datetime.now(UTC),
                }
            )
            return str(result.inserted_id)
        except PyMongoError:
            logger.warning("Could not record sync start in MongoDB", exc_info=True)
            return None

    def finish(self, run_id: str | None, status: str, details: dict[str, Any]) -> None:
        fields = {**details, "status": status, "finished_at": datetime.now(UTC)}
        try:
            if run_id:
                self.collection.update_one({"_id": ObjectId(run_id)}, {"$set": fields})
            else:
                self.collection.insert_one(fields)
        except PyMongoError:
            logger.warning("Could not record sync result in MongoDB", exc_info=True)

    def latest(self) -> dict[str, Any] | None:
        return self.collection.find_one(sort=[("started_at", DESCENDING)])

    def latest_success(self) -> dict[str, Any] | None:
        # Runs recorded before statuses existed count as successful.
        query = {"$or": [{"status": "success"}, {"status": {"$exists": False}}]}
        return self.collection.find_one(query, sort=[("started_at", DESCENDING)])


def get_sync_run_store() -> SyncRunStore:
    return MongoSyncRunStore(get_mongo_db()["tender_sync_runs"])
