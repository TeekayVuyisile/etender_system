from datetime import date

from pydantic import BaseModel

from app.models import Plan


class PlanDetails(BaseModel):
    plan: Plan
    name: str
    price_label: str
    seats: int | None
    weekly_searches: int | None
    ai_summaries: bool
    readiness_checks: bool
    exports: bool


class PlanUsage(BaseModel):
    seats_used: int
    seats_limit: int | None
    searches_used: int | None
    searches_limit: int | None
    searches_reset_on: date


class TeamPlanResponse(BaseModel):
    current: PlanDetails
    usage: PlanUsage
    available: list[PlanDetails]


class PlanChange(BaseModel):
    plan: Plan
