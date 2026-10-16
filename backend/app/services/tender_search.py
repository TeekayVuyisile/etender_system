"""Keyword search and filtering over the tenders table."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import ColumnElement, Select, and_, func, literal_column, select
from sqlalchemy.orm import Session, load_only

from app.models import Tender
from app.services.tender_sync import SAST

TenderStatus = Literal["open", "closed", "all"]
TenderSort = Literal["relevance", "closing_soon", "newest"]

LIST_COLUMNS = (
    Tender.id,
    Tender.tender_number,
    Tender.title,
    Tender.buyer_name,
    Tender.province,
    Tender.category,
    Tender.procurement_category,
    Tender.procurement_method,
    Tender.published_at,
    Tender.closing_at,
    Tender.estimated_value,
    Tender.briefing_compulsory,
    Tender.document_count,
)


@dataclass
class TenderFilters:
    q: str | None = None
    provinces: list[str] = field(default_factory=list)
    buyers: list[str] = field(default_factory=list)
    closing_from: date | None = None
    closing_to: date | None = None
    min_value: float | None = None
    max_value: float | None = None
    status: TenderStatus = "open"
    sort: TenderSort = "relevance"


@dataclass
class SearchResult:
    tenders: list[Tender]
    total: int
    province_counts: dict[str, int]


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=SAST)


def _keyword_condition(
    db: Session, q: str
) -> tuple[ColumnElement[bool], ColumnElement[float] | None]:
    """Full-text search on PostgreSQL (ranked); simple substring matching elsewhere (tests)."""
    if db.get_bind().dialect.name == "postgresql":
        # Must match the expression index in the migration exactly to be able to use it.
        vector = func.to_tsvector(literal_column("'english'::regconfig"), Tender.search_text)
        query = func.websearch_to_tsquery(literal_column("'english'::regconfig"), q)
        return vector.op("@@")(query), func.ts_rank(vector, query)

    return and_(*[Tender.search_text.contains(term) for term in q.lower().split()]), None


def _base_conditions(db: Session, filters: TenderFilters) -> tuple[list, ColumnElement | None]:
    conditions: list = []
    rank = None
    now = datetime.now(UTC)

    if filters.status == "open":
        conditions.append(Tender.closing_at >= now)
    elif filters.status == "closed":
        conditions.append(Tender.closing_at < now)

    if filters.q and filters.q.strip():
        keyword, rank = _keyword_condition(db, filters.q.strip())
        conditions.append(keyword)
    if filters.buyers:
        conditions.append(Tender.buyer_name.in_(filters.buyers))
    if filters.closing_from:
        conditions.append(Tender.closing_at >= _start_of_day(filters.closing_from))
    if filters.closing_to:
        conditions.append(Tender.closing_at < _start_of_day(filters.closing_to + timedelta(days=1)))
    if filters.min_value is not None:
        conditions.append(Tender.estimated_value >= filters.min_value)
    if filters.max_value is not None:
        conditions.append(Tender.estimated_value <= filters.max_value)
    return conditions, rank


def _apply_sort(stmt: Select, filters: TenderFilters, rank: ColumnElement | None) -> Select:
    if filters.sort == "newest":
        return stmt.order_by(Tender.published_at.desc().nulls_last(), Tender.id.desc())
    if filters.sort == "relevance" and rank is not None:
        return stmt.order_by(rank.desc(), Tender.closing_at.asc().nulls_last(), Tender.id)
    return stmt.order_by(Tender.closing_at.asc().nulls_last(), Tender.id)


def search_tenders(db: Session, filters: TenderFilters, page: int, page_size: int) -> SearchResult:
    conditions, rank = _base_conditions(db, filters)

    # Province counts ignore the province filter, so users can see what each choice would give.
    province_rows = db.execute(
        select(Tender.province, func.count()).where(*conditions).group_by(Tender.province)
    ).all()
    province_counts = {(province or "Unknown"): count for province, count in province_rows}

    if filters.provinces:
        conditions.append(Tender.province.in_(filters.provinces))

    total = db.scalar(select(func.count()).select_from(Tender).where(*conditions)) or 0
    # Only load what the result list shows: the database is far away (in development), and
    # skipping large columns like the document links makes each page much smaller.
    stmt = select(Tender).options(load_only(*LIST_COLUMNS)).where(*conditions)
    stmt = _apply_sort(stmt, filters, rank)
    tenders = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return SearchResult(tenders=tenders, total=total, province_counts=province_counts)


def search_buyers(db: Session, q: str | None, limit: int = 20) -> list[tuple[str, int]]:
    """Buyers with open tenders, optionally filtered by name, most active first."""
    stmt = (
        select(Tender.buyer_name, func.count())
        .where(Tender.closing_at >= datetime.now(UTC))
        .group_by(Tender.buyer_name)
        .order_by(func.count().desc(), Tender.buyer_name)
        .limit(limit)
    )
    if q and q.strip():
        stmt = stmt.where(Tender.buyer_name.ilike(f"%{q.strip()}%"))
    return [(name, count) for name, count in db.execute(stmt).all()]
