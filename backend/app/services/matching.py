"""Runs readiness checks for a team and turns stored results into API responses."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CompanyProfile, Tender, User
from app.schemas.company_profile import CompanyProfileBase
from app.schemas.readiness import MatchResultResponse
from app.schemas.summary import TenderSummaryContent
from app.services.match_store import MatchStore
from app.services.readiness import TenderFacts, as_utc, score_readiness
from app.services.summary_store import SummaryStore


def tender_facts(tender: Tender, summary: TenderSummaryContent) -> TenderFacts:
    return TenderFacts(
        requirements=summary.requirements,
        title=tender.title,
        province=tender.province,
        category=tender.category,
        procurement_method=tender.procurement_method,
        closing_at=tender.closing_at,
        briefing_compulsory=tender.briefing_compulsory,
        briefing_at=tender.briefing_at,
        scope=summary.scope,
    )


def ready_summary(store: SummaryStore, tender_id: int) -> tuple[TenderSummaryContent, Any]:
    doc = store.get(tender_id)
    if not doc or doc.get("status") != "ready" or not doc.get("content"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Generate the AI summary first: matching uses the requirements it extracts",
        )
    return TenderSummaryContent.model_validate(doc["content"]), doc.get("updated_at")


def team_profile(db: Session, team_id: int) -> CompanyProfile:
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.team_id == team_id))
    if profile is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Create a company profile first")
    return profile


def run_match(
    db: Session,
    tender: Tender,
    user: User,
    summaries: SummaryStore,
    matches: MatchStore,
) -> MatchResultResponse:
    summary, summary_updated_at = ready_summary(summaries, tender.id)
    profile = team_profile(db, user.team_id)

    result = score_readiness(
        tender_facts(tender, summary),
        CompanyProfileBase.model_validate(profile, from_attributes=True),
    )
    doc = matches.save(
        user.team_id,
        tender.id,
        {
            **result.model_dump(),
            "checked_by": user.full_name,
            "profile_updated_at": profile.updated_at,
            "summary_updated_at": summary_updated_at,
        },
    )
    return to_response(doc, profile, summary_updated_at)


def _later(a: datetime | None, b: datetime | None) -> bool:
    """True if `a` is meaningfully later than `b`. MongoDB stores milliseconds while
    PostgreSQL stores microseconds, so tiny differences are ignored."""
    return bool(a and b and as_utc(a) - as_utc(b) > timedelta(seconds=1))


def to_response(
    doc: dict[str, Any], profile: CompanyProfile | None, summary_updated_at: datetime | None
) -> MatchResultResponse:
    outdated = _later(profile.updated_at if profile else None, doc.get("profile_updated_at")) or (
        _later(summary_updated_at, doc.get("summary_updated_at"))
    )
    return MatchResultResponse(**{k: v for k, v in doc.items() if k != "_id"}, outdated=outdated)
