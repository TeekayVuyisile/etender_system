from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.core.reference import PROVINCES
from app.models import Tender
from app.schemas.tender import BuyerOption, TenderDetail, TenderSearchResponse
from app.services.tender_search import (
    TenderFilters,
    TenderSort,
    TenderStatus,
    search_buyers,
    search_tenders,
)
from app.services.tender_sync import NATIONAL

router = APIRouter(prefix="/tenders", tags=["tenders"])

PROVINCE_FILTER_VALUES = {*PROVINCES, NATIONAL}


@router.get("", response_model=TenderSearchResponse)
def list_tenders(
    _user: CurrentUser,
    db: DbSession,
    q: Annotated[
        str | None, Query(max_length=200, description="Keywords, e.g. road construction")
    ] = None,
    province: Annotated[list[str], Query(description="Repeat to select several provinces")] = [],  # noqa: B006
    buyer: Annotated[list[str], Query(description="Exact buyer (organ of state) names")] = [],  # noqa: B006
    closing_from: date | None = None,
    closing_to: date | None = None,
    min_value: Annotated[float | None, Query(ge=0)] = None,
    max_value: Annotated[float | None, Query(ge=0)] = None,
    tender_status: Annotated[TenderStatus, Query(alias="status")] = "open",
    sort: TenderSort = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TenderSearchResponse:
    """Search tenders by keyword, then narrow down with filters."""
    unknown = set(province) - PROVINCE_FILTER_VALUES
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown province(s): {', '.join(sorted(unknown))}",
        )
    if closing_from and closing_to and closing_from > closing_to:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="closing_from must be before closing_to"
        )

    filters = TenderFilters(
        q=q,
        provinces=province,
        buyers=buyer,
        closing_from=closing_from,
        closing_to=closing_to,
        min_value=min_value,
        max_value=max_value,
        status=tender_status,
        sort=sort,
    )
    result = search_tenders(db, filters, page=page, page_size=page_size)
    return TenderSearchResponse(
        items=result.tenders,
        total=result.total,
        page=page,
        page_size=page_size,
        province_counts=result.province_counts,
    )


@router.get("/buyers", response_model=list[BuyerOption])
def list_buyers(
    _user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[BuyerOption]:
    """Buyers (organs of state) with open tenders, for the buyer filter."""
    return [BuyerOption(name=name, open_tenders=count) for name, count in search_buyers(db, q)]


@router.get("/{tender_id}", response_model=TenderDetail)
def get_tender(tender_id: int, _user: CurrentUser, db: DbSession) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    return tender
