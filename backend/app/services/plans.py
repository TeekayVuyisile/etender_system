"""Plan enforcement: feature checks, seat limits and weekly search limits."""

import hashlib
import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.plans import FEATURE_LABELS, PLANS, Feature, PlanLimits, cheapest_plan_with
from app.models import Plan, SearchUsage, Team, User
from app.services.tender_sync import SAST


def limits_for(team: Team) -> PlanLimits:
    return PLANS[team.plan]


def upgrade_required(message: str, required_plan: Plan) -> HTTPException:
    """403 with a machine-readable body, so the frontend can show an upgrade prompt."""
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": "upgrade_required",
            "message": message,
            "required_plan": required_plan.value,
        },
    )


def ensure_feature(team: Team, feature: Feature) -> None:
    if not limits_for(team).allows(feature):
        plan = cheapest_plan_with(feature)
        raise upgrade_required(
            f"{FEATURE_LABELS[feature]} are available on the {PLANS[plan].name} plan and above",
            plan,
        )


# --- Seats --------------------------------------------------------------------


def seats_used(db: Session, team_id: int) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.team_id == team_id)) or 0


def ensure_seat_available(db: Session, team: Team) -> None:
    limit = limits_for(team).seats
    if limit is not None and seats_used(db, team.id) >= limit:
        next_plan = Plan.BASIC if team.plan == Plan.FREE else Plan.PRO
        raise upgrade_required(
            f"Your {limits_for(team).name} plan allows {limit} team member"
            f"{'' if limit == 1 else 's'}. Upgrade to add more",
            next_plan,
        )


# --- Weekly searches ------------------------------------------------------------


def week_start(now: datetime | None = None) -> date:
    """Monday of the current week, in South African time."""
    today = (now or datetime.now(SAST)).astimezone(SAST).date()
    return today - timedelta(days=today.weekday())


def search_key(params: dict[str, Any]) -> str:
    """Stable hash of a search's keywords and filters (not page or sort order)."""
    normalised = {
        key: sorted(value) if isinstance(value, list) else value
        for key, value in params.items()
        if value not in (None, "", [])
    }
    if isinstance(normalised.get("q"), str):
        normalised["q"] = " ".join(normalised["q"].lower().split())
    return hashlib.sha256(json.dumps(normalised, sort_keys=True, default=str).encode()).hexdigest()


def searches_used(db: Session, team_id: int, week: date | None = None) -> int:
    week = week or week_start()
    stmt = select(func.count()).where(
        SearchUsage.team_id == team_id, SearchUsage.week_start == week
    )
    return db.scalar(stmt) or 0


def record_search(db: Session, team: Team, params: dict[str, Any]) -> None:
    """Count a search against the team's weekly limit, or refuse it if the limit is reached.

    Repeating a search already counted this week (e.g. paging through results) is free.
    """
    limit = limits_for(team).weekly_searches
    if limit is None:
        return
    week, key = week_start(), search_key(params)
    already_counted = db.scalar(
        select(SearchUsage.id).where(
            SearchUsage.team_id == team.id,
            SearchUsage.week_start == week,
            SearchUsage.query_key == key,
        )
    )
    if already_counted:
        return
    if searches_used(db, team.id, week) >= limit:
        resets = week + timedelta(days=7)
        raise upgrade_required(
            f"You've used all {limit} searches for this week on the Free plan. "
            f"They reset on Monday {resets:%d %B}, or upgrade for unlimited searches",
            Plan.BASIC,
        )
    db.add(SearchUsage(team_id=team.id, week_start=week, query_key=key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # the same search was recorded concurrently; that's fine


def plan_usage(db: Session, team: Team) -> dict[str, Any]:
    limits = limits_for(team)
    week = week_start()
    return {
        "seats_used": seats_used(db, team.id),
        "seats_limit": limits.seats,
        "searches_used": searches_used(db, team.id, week) if limits.weekly_searches else None,
        "searches_limit": limits.weekly_searches,
        "searches_reset_on": week + timedelta(days=7),
    }
