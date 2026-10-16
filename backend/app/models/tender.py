from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    literal_column,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.company_profile import JsonList


class Tender(Base):
    """A public tender from the OCDS eTenders API, enriched with eTenders portal details."""

    __tablename__ = "tenders"
    __table_args__ = (
        # Full-text search index, PostgreSQL only (SQLite in tests uses substring search).
        Index(
            "ix_tenders_search_text_fts",
            func.to_tsvector(literal_column("'english'::regconfig"), text("search_text")),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ocid: Mapped[str] = mapped_column(String(100), unique=True)
    # The eTenders tender ID: shared by the OCDS API and the eTenders portal.
    etenders_id: Mapped[int] = mapped_column(Integer, unique=True)

    tender_number: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    buyer_id: Mapped[str | None] = mapped_column(String(50))
    buyer_name: Mapped[str] = mapped_column(String(300), index=True)
    procurement_category: Mapped[str | None] = mapped_column(String(50))  # goods/services/works
    procurement_method: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(300))  # industry category (portal)

    province: Mapped[str | None] = mapped_column(String(50), index=True)
    province_source: Mapped[str | None] = mapped_column(String(20))  # "portal" or "inferred"
    delivery_location: Mapped[str | None] = mapped_column(String(500))

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    briefing_session: Mapped[bool] = mapped_column(Boolean, default=False)
    briefing_compulsory: Mapped[bool] = mapped_column(Boolean, default=False)
    briefing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    briefing_venue: Mapped[str | None] = mapped_column(Text)
    special_conditions: Mapped[str | None] = mapped_column(Text)

    contact_person: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(50))

    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    # e.g. [{"id": "...", "title": "...", "url": "...", "format": "pdf"}]
    documents: Mapped[list[dict[str, Any]]] = mapped_column(JsonList, default=list)
    document_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Lower-cased text used for keyword search (full-text indexed on PostgreSQL).
    search_text: Mapped[str] = mapped_column(Text, default="")

    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def refresh_search_text(self) -> None:
        parts = [self.title, self.tender_number, self.buyer_name, self.category or ""]
        self.search_text = " ".join(p for p in parts if p).lower()
