from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser
from app.schemas.notification import MarkedRead, NotificationList, NotificationRead
from app.services.notifications import NotificationStore, get_notification_store

router = APIRouter(prefix="/notifications", tags=["notifications"])

Store = Annotated[NotificationStore, Depends(get_notification_store)]


def _read(doc: dict[str, Any]) -> NotificationRead:
    return NotificationRead(id=str(doc["_id"]), **{k: v for k, v in doc.items() if k != "_id"})


@router.get("", response_model=NotificationList)
def list_notifications(
    user: CurrentUser,
    store: Store,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationList:
    """Your latest notifications, newest first, with the number still unread."""
    return NotificationList(
        items=[_read(doc) for doc in store.list(user.id, unread_only, limit)],
        unread_count=store.unread_count(user.id),
    )


@router.post("/read-all", response_model=MarkedRead)
def mark_all_read(user: CurrentUser, store: Store) -> MarkedRead:
    marked = store.mark_read(user.id)
    return MarkedRead(marked=marked, unread_count=0)


@router.post("/{notification_id}/read", response_model=MarkedRead)
def mark_read(notification_id: str, user: CurrentUser, store: Store) -> MarkedRead:
    """Mark one of your notifications as read (other users' notifications are ignored)."""
    marked = store.mark_read(user.id, notification_id)
    return MarkedRead(marked=marked, unread_count=store.unread_count(user.id))
