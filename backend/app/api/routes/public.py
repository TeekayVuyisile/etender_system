"""Public API for third-party systems and civic-tech apps.

Authenticate with an API key in the X-API-Key header (create one on the API access page), or
with a normal Bearer token. Plan limits apply to the key's team.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.api.deps import Activity, Caller, DbSession
from app.api.routes.tenders import LLM, PROVINCE_FILTER_VALUES
from app.models import CompanyProfile, Tender
from app.schemas.company_profile import ReadinessProfile
from app.schemas.public import (
    EnrichedRelease,
    EnrichedReleasesResponse,
    PublicSummary,
    ReadinessCheckRequest,
    ReadinessCheckResponse,
    SpendByBuyerResponse,
    Suitability,
    SummaryExtractResponse,
)
from app.schemas.summary import TenderSummaryContent
from app.services import analytics
from app.services.analytics import AnalyticsCache, get_analytics_cache
from app.services.documents import DocumentError, extract, guess_format
from app.services.llm import LLMError
from app.services.matching import ready_summary, tender_facts
from app.services.plans import limits_for, record_search
from app.services.readiness import score_readiness
from app.services.summarizer import summarize_document
from app.services.summary_store import SummaryStore, get_summary_store
from app.services.tender_search import TenderFilters, TenderStatus, search_tenders

router = APIRouter(tags=["public API"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
Summaries = Annotated[SummaryStore, Depends(get_summary_store)]


def _team_profile(db: DbSession, team_id: int) -> ReadinessProfile | None:
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.team_id == team_id))
    return ReadinessProfile.model_validate(profile, from_attributes=True) if profile else None


def _enrich(
    tender: Tender,
    summary_doc: dict[str, Any] | None,
    profile: ReadinessProfile | None,
    include_summary: bool,
    include_suitability: bool,
) -> EnrichedRelease:
    ai_summary = suitability = None
    if summary_doc and summary_doc.get("status") == "ready" and summary_doc.get("content"):
        content = TenderSummaryContent.model_validate(summary_doc["content"])
        if include_summary:
            ai_summary = PublicSummary(
                **content.model_dump(
                    include={
                        "summary",
                        "objective",
                        "scope",
                        "eligibility",
                        "requirements",
                        "contract_duration",
                        "evaluation",
                    }
                ),
                generated_at=summary_doc.get("updated_at"),
            )
        if include_suitability and profile:
            result = score_readiness(tender_facts(tender, content), profile)
            suitability = Suitability(
                score=result.score, verdict=result.verdict, recommendation=result.recommendation
            )
    return EnrichedRelease(
        id=tender.id,
        ocid=tender.ocid,
        etenders_id=tender.etenders_id,
        tender_number=tender.tender_number,
        title=tender.title,
        buyer=tender.buyer_name,
        province=tender.province,
        category=tender.category,
        procurement_method=tender.procurement_method,
        published_at=tender.published_at,
        closing_at=tender.closing_at,
        estimated_value=float(tender.estimated_value) if tender.estimated_value else None,
        briefing_compulsory=tender.briefing_compulsory,
        document_count=tender.document_count,
        ai_summary=ai_summary,
        suitability=suitability,
    )


@router.get("/enriched-releases", response_model=EnrichedReleasesResponse)
def enriched_releases(
    caller: Caller,
    db: DbSession,
    summaries: Summaries,
    q: Annotated[str | None, Query(max_length=200)] = None,
    province: Annotated[list[str], Query()] = [],  # noqa: B006
    buyer: Annotated[list[str], Query()] = [],  # noqa: B006
    closing_from: date | None = None,
    closing_to: date | None = None,
    tender_status: Annotated[TenderStatus, Query(alias="status")] = "open",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EnrichedReleasesResponse:
    """Filtered tenders with their metadata, AI summary and suitability score.

    The suitability score compares each summarised tender with your team's company profile.
    AI fields are included on the Basic and Pro plans.
    """
    if set(province) - PROVINCE_FILTER_VALUES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown province")
    record_search(
        db,
        caller.team,
        {
            "q": q,
            "province": province,
            "buyer": buyer,
            "closing_from": closing_from,
            "closing_to": closing_to,
            "status": tender_status,
        },
    )
    result = search_tenders(
        db,
        TenderFilters(
            q=q,
            provinces=province,
            buyers=buyer,
            closing_from=closing_from,
            closing_to=closing_to,
            status=tender_status,
            sort="relevance",
        ),
        page=page,
        page_size=page_size,
        full_rows=True,
    )

    limits = limits_for(caller.team)
    include_summary, include_suitability = limits.ai_summaries, limits.readiness_checks
    docs = (
        summaries.get_many([t.id for t in result.tenders])
        if include_summary or include_suitability
        else {}
    )
    profile = _team_profile(db, caller.team.id) if include_suitability else None
    return EnrichedReleasesResponse(
        releases=[
            _enrich(t, docs.get(t.id), profile, include_summary, include_suitability)
            for t in result.tenders
        ],
        total=result.total,
        page=page,
        page_size=page_size,
        includes_ai_summaries=include_summary,
        includes_suitability=include_suitability,
    )


@router.get("/analytics/spend-by-buyer", response_model=SpendByBuyerResponse)
def spend_by_buyer(
    _caller: Caller,
    db: DbSession,
    cache: Annotated[AnalyticsCache, Depends(get_analytics_cache)],
    since: date | None = None,
    province: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> SpendByBuyerResponse:
    """Tenders advertised and known values per buyer (organ of state). Cached for an hour.

    The eTenders sources don't publish award values, so totals cover tenders whose value is
    published or was extracted from their documents; `value_coverage` shows how complete
    that is. Defaults to the last 90 days.
    """
    if province and province not in PROVINCE_FILTER_VALUES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown province")
    since = since or date.today() - timedelta(days=90)
    key = analytics.cache_key(
        "spend_by_buyer", {"since": since, "province": province, "limit": limit}
    )
    if cached := cache.get(key):
        return SpendByBuyerResponse(**cached, cached=True)
    data = analytics.spend_by_buyer(db, since, province, limit)
    cache.set(key, data)
    return SpendByBuyerResponse(**data)


@router.post("/summary/extract", response_model=SummaryExtractResponse)
def extract_summary(
    caller: Caller,
    llm: LLM,
    activity: Activity,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(description="A PDF or DOCX tender document (max 15 MB)")],
) -> SummaryExtractResponse:
    """Upload a PDF or DOCX document and get a plain-language summary of about 120 words."""
    caller.require("ai_summaries")
    filename = file.filename or "document"
    file_format = guess_format(filename)
    if file_format not in ("pdf", "docx"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload a PDF or DOCX file"
        )
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="File is larger than 15 MB")

    try:
        documents = extract(data, filename, file_format)
        result = summarize_document(documents, llm)
    except DocumentError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except LLMError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error

    background_tasks.add_task(
        activity.log,
        "api.summary_extracted",
        user_id=caller.actor_id,
        team_id=caller.team.id,
        details={"filename": filename, "words": result["word_count"]},
    )
    return SummaryExtractResponse(
        filename=filename, pages=sum(len(d.pages) for d in documents), **result
    )


@router.post("/readiness/check", response_model=ReadinessCheckResponse)
def readiness_check(
    data: ReadinessCheckRequest,
    caller: Caller,
    db: DbSession,
    summaries: Summaries,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> ReadinessCheckResponse:
    """Score a tender against a company profile: suitability score, checklist and
    recommendation. Uses your team's profile if `company_profile` isn't given.

    The tender needs an AI summary (its requirements come from there).
    """
    caller.require("readiness_checks")
    tender = db.get(Tender, data.tender_id)
    if tender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    summary, _ = ready_summary(summaries, tender.id)

    profile, source = data.company_profile, "request"
    if profile is None:
        profile, source = _team_profile(db, caller.team.id), "team_profile"
        if profile is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Send a company_profile or create one for your team",
            )

    result = score_readiness(tender_facts(tender, summary), profile)
    background_tasks.add_task(
        activity.log,
        "api.readiness_checked",
        user_id=caller.actor_id,
        team_id=caller.team.id,
        details={"tender_id": tender.id, "score": result.score, "profile_source": source},
    )
    return ReadinessCheckResponse(**result.model_dump(), tender_id=tender.id, profile_source=source)
