from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class JobLock(Base):
    """Makes sure only one copy of a background job runs at a time, across processes.

    A job holds the lock until `locked_until`; if it crashes, the lock simply expires.
    """

    __tablename__ = "job_locks"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(100))
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
