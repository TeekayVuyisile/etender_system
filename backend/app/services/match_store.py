"""Stores readiness ("Match This Tender") results in MongoDB, one per team per tender."""

from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo.collection import Collection

from app.db.mongo import get_mongo_db


class MatchStore(Protocol):
    def get(self, team_id: int, tender_id: int) -> dict[str, Any] | None: ...
    def get_many(self, team_id: int, tender_ids: list[int]) -> dict[int, dict[str, Any]]: ...
    def save(self, team_id: int, tender_id: int, result: dict[str, Any]) -> dict[str, Any]: ...


class MongoMatchStore:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    @staticmethod
    def _id(team_id: int, tender_id: int) -> str:
        return f"{team_id}:{tender_id}"

    def get(self, team_id: int, tender_id: int) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": self._id(team_id, tender_id)})

    def get_many(self, team_id: int, tender_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not tender_ids:
            return {}
        query = {"team_id": team_id, "tender_id": {"$in": tender_ids}}
        return {doc["tender_id"]: doc for doc in self.collection.find(query)}

    def save(self, team_id: int, tender_id: int, result: dict[str, Any]) -> dict[str, Any]:
        doc = {
            **result,
            "_id": self._id(team_id, tender_id),
            "team_id": team_id,
            "tender_id": tender_id,
            "checked_at": datetime.now(UTC),
        }
        self.collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        return doc


def get_match_store() -> MatchStore:
    return MongoMatchStore(get_mongo_db()["match_results"])
