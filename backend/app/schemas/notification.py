from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: str
    type: str
    title: str
    body: str
    link: str | None
    actor_name: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    items: list[NotificationRead]
    unread_count: int


class MarkedRead(BaseModel):
    marked: int
    unread_count: int
