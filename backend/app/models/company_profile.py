from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.team import Team

# JSONB on PostgreSQL (indexable, queryable); plain JSON elsewhere (SQLite in tests).
JsonList = JSON().with_variant(JSONB(), "postgresql")


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), unique=True, index=True
    )

    industry_sector: Mapped[str] = mapped_column(String(100))
    services: Mapped[list[str]] = mapped_column(JsonList, default=list)
    # e.g. [{"class_code": "CE", "grade": 5}]
    cidb_gradings: Mapped[list[dict[str, Any]]] = mapped_column(JsonList, default=list)
    bbbee_level: Mapped[int | None] = mapped_column(Integer)
    certifications: Mapped[list[str]] = mapped_column(JsonList, default=list)
    provinces: Mapped[list[str]] = mapped_column(JsonList, default=list)
    years_of_experience: Mapped[int] = mapped_column(Integer)

    contact_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(320))
    contact_phone: Mapped[str] = mapped_column(String(30))
    website: Mapped[str | None] = mapped_column(String(300))
    physical_address: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped[Team] = relationship()
