from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SearchUsage(Base):
    """One row per distinct tender search a team runs in a week (for plan search limits)."""

    __tablename__ = "search_usage"
    __table_args__ = (
        UniqueConstraint("team_id", "week_start", "query_key", name="uq_search_usage_query"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    # Hash of the normalised keywords + filters, so repeating a search doesn't count twice.
    query_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
