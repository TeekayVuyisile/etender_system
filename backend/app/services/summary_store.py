"""Stores AI summary results in MongoDB (collection: tender_summaries, one document per tender)."""

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.db.mongo import get_mongo_db
from app.schemas.summary import TenderSummaryResponse

# A job stuck in "processing" longer than this (e.g. the server restarted) can be retried.
STALE_AFTER = timedelta(minutes=10)


class SummaryStore(Protocol):
    def get(self, tender_id: int) -> dict[str, Any] | None: ...
    def get_many(self, tender_ids: list[int]) -> dict[int, dict[str, Any]]: ...
    def try_start(self, tender_id: int, user_id: int, team_id: int) -> bool: ...
    def save_ready(self, tender_id: int, result: dict[str, Any]) -> None: ...
    def save_failed(self, tender_id: int, error: str) -> None: ...


class MongoSummaryStore:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def get(self, tender_id: int) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": tender_id})

    def get_many(self, tender_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not tender_ids:
            return {}
        return {doc["_id"]: doc for doc in self.collection.find({"_id": {"$in": tender_ids}})}

    def try_start(self, tender_id: int, user_id: int, team_id: int) -> bool:
        """Mark a summary as processing. Returns False if another job is already running."""
        now = datetime.now(UTC)
        try:
            self.collection.find_one_and_update(
                {
                    "_id": tender_id,
                    "$or": [
                        {"status": {"$ne": "processing"}},
                        {"updated_at": {"$lt": now - STALE_AFTER}},
                    ],
                },
                {
                    "$set": {
                        "status": "processing",
                        "error": None,
                        "requested_by": {"user_id": user_id, "team_id": team_id},
                        "updated_at": now,
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return False  # the document exists and is already processing
        return True

    def save_ready(self, tender_id: int, result: dict[str, Any]) -> None:
        self.collection.update_one(
            {"_id": tender_id},
            {"$set": {**result, "status": "ready", "error": None, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )

    def save_failed(self, tender_id: int, error: str) -> None:
        self.collection.update_one(
            {"_id": tender_id},
            {"$set": {"status": "failed", "error": error, "updated_at": datetime.now(UTC)}},
            upsert=True,
        )


def get_summary_store() -> SummaryStore:
    return MongoSummaryStore(get_mongo_db()["tender_summaries"])


def to_response(tender_id: int, doc: dict[str, Any] | None) -> TenderSummaryResponse:
    if doc is None:
        return TenderSummaryResponse(tender_id=tender_id, status="none")
    return TenderSummaryResponse(
        tender_id=tender_id, **{k: v for k, v in doc.items() if k != "_id"}
    )
