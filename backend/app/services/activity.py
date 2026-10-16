import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.db.mongo import get_mongo_db

logger = logging.getLogger(__name__)


class ActivityLogger(Protocol):
    def log(
        self, event: str, *, user_id: int, team_id: int, details: dict[str, Any] | None = None
    ) -> None: ...


class MongoActivityLogger:
    """Writes user activity events (logins, sign-ups, status changes...) to MongoDB."""

    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def log(
        self, event: str, *, user_id: int, team_id: int, details: dict[str, Any] | None = None
    ) -> None:
        try:
            self.collection.insert_one(
                {
                    "event": event,
                    "user_id": user_id,
                    "team_id": team_id,
                    "details": details or {},
                    "created_at": datetime.now(UTC),
                }
            )
        except PyMongoError:
            # Activity logging must never break the user's request.
            logger.warning("Failed to write activity log event %r", event, exc_info=True)


def get_activity_logger() -> ActivityLogger:
    return MongoActivityLogger(get_mongo_db()["activity_logs"])
