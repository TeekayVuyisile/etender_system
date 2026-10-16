from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Plan(StrEnum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[Plan] = mapped_column(
        Enum(Plan, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=Plan.FREE,
    )
    # Demo teams are created by "Try the demo" and deleted automatically after a while.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["User"]] = relationship(back_populates="team")
