from dataclasses import asdict
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import Activity, CurrentUser, DbSession, require_feature
from app.core.config import settings
from app.core.reference import PROVINCES
from app.db.session import get_session_factory
from app.models import CompanyProfile, Tender, User
from app.schemas.readiness import MatchResultResponse
from app.schemas.summary import TenderSummaryResponse
from app.schemas.sync import SyncRunInfo, SyncStatusResponse
from app.schemas.tender import BuyerOption, TenderDetail, TenderSearchResponse
from app.services import matching, sync_job
from app.services import notification_events as events
from app.services.cache import Cache, get_cache, mark_response
from app.services.llm import LLMClient, LLMError, get_llm_client
from app.services.match_store import MatchStore, get_match_store
from app.services.notifications import Notifier, get_notifier
from app.services.plans import record_search
from app.services.summarizer import run_summary_job
from app.services.summary_store import SummaryStore, get_summary_store, to_response
from app.services.sync_runs import SyncRunStore, get_sync_run_store
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

# How long cached tender data may be served. The sync invalidates it anyway; the TTLs bound how
# long a tender that just closed can still show as open.
SEARCH_CACHE_SECONDS = 5 * 60
BUYERS_CACHE_SECONDS = 10 * 60
DETAIL_CACHE_SECONDS = 60 * 60
SYNC_STATUS_CACHE_SECONDS = 60

RedisCache = Annotated[Cache, Depends(get_cache)]


@router.get("", response_model=TenderSearchResponse)
def list_tenders(
    user: CurrentUser,
    db: DbSession,
    cache: RedisCache,
    response: Response,
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
    """Search tenders by keyword, then narrow down with filters.

    On the Free plan each distinct search counts towards a weekly limit.
    """
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

    record_search(
        db,
        user.team,
        {
            "q": q,
            "province": province,
            "buyer": buyer,
            "closing_from": closing_from,
            "closing_to": closing_to,
            "min_value": min_value,
            "max_value": max_value,
            "status": tender_status,
        },
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

    def search() -> dict:
        result = search_tenders(db, filters, page=page, page_size=page_size)
        return TenderSearchResponse(
            items=result.tenders,
            total=result.total,
            page=page,
            page_size=page_size,
            province_counts=result.province_counts,
        ).model_dump(mode="json")

    # The search still counts towards the plan limit above; the cache only saves the queries.
    key = cache.tender_key("search", {**asdict(filters), "page": page, "page_size": page_size})
    data, hit = cache.get_or_load(key, SEARCH_CACHE_SECONDS, search)
    mark_response(response, cache, hit)
    return TenderSearchResponse.model_validate(data)


@router.get("/sync-status", response_model=SyncStatusResponse)
def get_sync_status(
    _user: CurrentUser,
    runs: Annotated[SyncRunStore, Depends(get_sync_run_store)],
    cache: RedisCache,
    response: Response,
) -> SyncStatusResponse:
    """When tender data was last refreshed from the eTenders APIs, and when it will be next."""
    data, hit = cache.get_or_load(
        sync_job.SYNC_STATUS_CACHE_KEY,
        SYNC_STATUS_CACHE_SECONDS,
        lambda: _sync_status(runs).model_dump(mode="json"),
    )
    mark_response(response, cache, hit)
    return SyncStatusResponse.model_validate(data)


def _sync_status(runs: SyncRunStore) -> SyncStatusResponse:
    latest, success = runs.latest(), runs.latest_success()
    last_success_at = (success.get("finished_at") or success.get("started_at")) if success else None
    running = sync_job.scheduler
    if running and running.next_run_at:
        next_run_at = running.next_run_at
    elif settings.sync_schedule_enabled and last_success_at:
        next_run_at = last_success_at + timedelta(hours=settings.sync_interval_hours)
    else:
        next_run_at = None
    return SyncStatusResponse(
        last_run=SyncRunInfo(**{"status": "success", **latest}) if latest else None,
        last_success_at=last_success_at,
        schedule_enabled=settings.sync_schedule_enabled,
        interval_hours=settings.sync_interval_hours,
        next_run_at=next_run_at,
    )


@router.get("/buyers", response_model=list[BuyerOption])
def list_buyers(
    _user: CurrentUser,
    db: DbSession,
    cache: RedisCache,
    response: Response,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[BuyerOption]:
    """Buyers (organs of state) with open tenders, for the buyer filter."""
    data, hit = cache.get_or_load(
        cache.tender_key("buyers", {"q": (q or "").strip().lower()}),
        BUYERS_CACHE_SECONDS,
        lambda: [{"name": name, "open_tenders": count} for name, count in search_buyers(db, q)],
    )
    mark_response(response, cache, hit)
    return [BuyerOption.model_validate(item) for item in data]


@router.get("/{tender_id}", response_model=TenderDetail)
def get_tender(
    tender_id: int, _user: CurrentUser, db: DbSession, cache: RedisCache, response: Response
) -> TenderDetail:
    def load() -> dict | None:
        tender = db.get(Tender, tender_id)
        return TenderDetail.model_validate(tender).model_dump(mode="json") if tender else None

    key = cache.tender_key("tender", {"id": tender_id})
    data, hit = cache.get_or_load(key, DETAIL_CACHE_SECONDS, load)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    mark_response(response, cache, hit)
    return TenderDetail.model_validate(data)


def require_llm() -> LLMClient:
    try:
        return get_llm_client()
    except LLMError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


LLM = Annotated[LLMClient, Depends(require_llm)]


@router.get("/{tender_id}/summary", response_model=TenderSummaryResponse)
def get_tender_summary(
    tender_id: int,
    _user: Annotated[User, Depends(require_feature("ai_summaries"))],
    store: Annotated[SummaryStore, Depends(get_summary_store)],
) -> TenderSummaryResponse:
    """The AI summary for a tender, or its status if it's still being generated."""
    return to_response(tender_id, store.get(tender_id))


@router.post(
    "/{tender_id}/summary",
    response_model=TenderSummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_tender_summary(
    tender_id: int,
    user: Annotated[User, Depends(require_feature("ai_summaries"))],
    db: DbSession,
    background_tasks: BackgroundTasks,
    activity: Activity,
    store: Annotated[SummaryStore, Depends(get_summary_store)],
    llm: LLM,
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    notifier: Annotated[Notifier, Depends(get_notifier)],
    refresh: bool = False,
) -> TenderSummaryResponse:
    """Start generating the AI summary in the background. Poll GET .../summary for the result.

    An existing summary is returned as-is unless `refresh=true`.
    """
    if db.get(Tender, tender_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")

    existing = store.get(tender_id)
    if existing and existing.get("status") == "ready" and not refresh:
        return to_response(tender_id, existing)
    if store.try_start(tender_id, user.id, user.team_id):

        def notify_requester(tender: Tender) -> None:
            notifier.send(events.summary_ready(user.id, user.team_id, tender))

        background_tasks.add_task(
            run_summary_job,
            tender_id,
            session_factory=session_factory,
            store=store,
            llm=llm,
            on_ready=notify_requester,
        )
        background_tasks.add_task(
            activity.log,
            "tender.summary_requested",
            user_id=user.id,
            team_id=user.team_id,
            details={"tender_id": tender_id, "refresh": refresh},
        )
    return to_response(tender_id, store.get(tender_id))


Summaries = Annotated[SummaryStore, Depends(get_summary_store)]
Matches = Annotated[MatchStore, Depends(get_match_store)]


@router.get("/{tender_id}/match", response_model=MatchResultResponse)
def get_tender_match(
    tender_id: int,
    user: Annotated[User, Depends(require_feature("readiness_checks"))],
    db: DbSession,
    summaries: Summaries,
    matches: Matches,
) -> MatchResultResponse:
    """Your team's latest readiness check for this tender."""
    doc = matches.get(user.team_id, tender_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This tender hasn't been matched yet")
    summary = summaries.get(tender_id) or {}
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.team_id == user.team_id))
    return matching.to_response(doc, profile, summary.get("updated_at"))


@router.post("/{tender_id}/match", response_model=MatchResultResponse)
def match_tender(
    tender_id: int,
    user: Annotated[User, Depends(require_feature("readiness_checks"))],
    db: DbSession,
    summaries: Summaries,
    matches: Matches,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> MatchResultResponse:
    """Match This Tender: score the tender's requirements against your company profile."""
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    result = matching.run_match(db, tender, user, summaries, matches)
    background_tasks.add_task(
        activity.log,
        "tender.match_checked",
        user_id=user.id,
        team_id=user.team_id,
        details={"tender_id": tender_id, "score": result.score, "verdict": result.verdict},
    )
    return result
