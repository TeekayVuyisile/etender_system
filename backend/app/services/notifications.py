"""In-app notifications.

Code that wants to notify people calls the `Notifier`, which hands each notification to its
delivery channels. Today the only channel is in-app (stored in MongoDB and shown under the
bell in the header); an email channel could be added later without changing any callers.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, PyMongoError

from app.db.mongo import get_mongo_db

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    user_id: int
    team_id: int
    type: str  # e.g. "task_assigned", "status_changed", "deadline_reminder"
    title: str
    body: str = ""
    link: str | None = None  # app route to open, e.g. "/workspace/12"
    actor_name: str | None = None
    # Notifications with the same key are only ever sent once (e.g. one reminder per tender).
    dedupe_key: str | None = None

    def as_document(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "user_id": self.user_id,
            "team_id": self.team_id,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "link": self.link,
            "actor_name": self.actor_name,
            "created_at": datetime.now(UTC),
            "read_at": None,
        }
        if self.dedupe_key:
            doc["dedupe_key"] = f"{self.user_id}:{self.dedupe_key}"
        return doc


# --- Storage ------------------------------------------------------------------------


class NotificationStore(Protocol):
    def add(self, notifications: list[Notification]) -> int: ...
    def list(self, user_id: int, unread_only: bool, limit: int) -> list[dict[str, Any]]: ...
    def unread_count(self, user_id: int) -> int: ...
    def mark_read(self, user_id: int, notification_id: str | None = None) -> int: ...


class MongoNotificationStore:
    _indexes_ready = False
    _index_lock = threading.Lock()

    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def _ensure_indexes(self) -> None:
        # Indexes are created once per process (create_index is idempotent, but a round trip).
        with MongoNotificationStore._index_lock:
            if MongoNotificationStore._indexes_ready:
                return
            self.collection.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
            self.collection.create_index("dedupe_key", unique=True, sparse=True)
            MongoNotificationStore._indexes_ready = True

    def add(self, notifications: list[Notification]) -> int:
        if not notifications:
            return 0
        self._ensure_indexes()
        try:
            result = self.collection.insert_many(
                [n.as_document() for n in notifications], ordered=False
            )
            return len(result.inserted_ids)
        except BulkWriteError as error:
            # Duplicate dedupe keys (code 11000) are expected and skipped; anything else isn't.
            if any(e.get("code") != 11000 for e in error.details.get("writeErrors", [])):
                raise
            return error.details.get("nInserted", 0)

    def list(self, user_id: int, unread_only: bool, limit: int) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": user_id}
        if unread_only:
            query["read_at"] = None
        return list(self.collection.find(query).sort("created_at", DESCENDING).limit(limit))

    def unread_count(self, user_id: int) -> int:
        return self.collection.count_documents({"user_id": user_id, "read_at": None})

    def mark_read(self, user_id: int, notification_id: str | None = None) -> int:
        query: dict[str, Any] = {"user_id": user_id, "read_at": None}
        if notification_id:
            try:
                query["_id"] = ObjectId(notification_id)
            except InvalidId:
                return 0
        result = self.collection.update_many(query, {"$set": {"read_at": datetime.now(UTC)}})
        return result.modified_count


def get_notification_store() -> NotificationStore:
    return MongoNotificationStore(get_mongo_db()["notifications"])


# --- Delivery -------------------------------------------------------------------------


class Channel(Protocol):
    def deliver(self, notifications: list[Notification]) -> None: ...


class InAppChannel:
    def __init__(self, store: NotificationStore) -> None:
        self.store = store

    def deliver(self, notifications: list[Notification]) -> None:
        self.store.add(notifications)


class Notifier:
    def __init__(self, channels: list[Channel]) -> None:
        self.channels = channels

    def send(self, notifications: list[Notification]) -> None:
        """Deliver notifications on every channel. Never raises: notifications are a
        side effect and mustn't break the action that triggered them."""
        if not notifications:
            return
        for channel in self.channels:
            try:
                channel.deliver(notifications)
            except (PyMongoError, OSError):
                logger.warning(
                    "Could not deliver %d notification(s)", len(notifications), exc_info=True
                )


def get_notifier() -> Notifier:
    return Notifier([InAppChannel(get_notification_store())])
