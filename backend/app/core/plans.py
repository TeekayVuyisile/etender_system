"""SaaS plan definitions: the single source of truth for what each plan allows."""

from dataclasses import dataclass
from typing import Literal

from app.models import Plan

Feature = Literal["ai_summaries", "readiness_checks", "exports"]


@dataclass(frozen=True)
class PlanLimits:
    name: str
    price_label: str
    seats: int | None  # None = unlimited
    weekly_searches: int | None  # None = unlimited
    ai_summaries: bool
    readiness_checks: bool
    exports: bool

    def allows(self, feature: Feature) -> bool:
        return getattr(self, feature)


PLANS: dict[Plan, PlanLimits] = {
    Plan.FREE: PlanLimits(
        name="Free",
        price_label="R0",
        seats=1,
        weekly_searches=3,
        ai_summaries=False,
        readiness_checks=False,
        exports=False,
    ),
    Plan.BASIC: PlanLimits(
        name="Basic",
        price_label="R499 / month",
        seats=3,
        weekly_searches=None,
        ai_summaries=True,
        readiness_checks=True,
        exports=False,
    ),
    Plan.PRO: PlanLimits(
        name="Pro",
        price_label="R1,499 / month",
        seats=None,
        weekly_searches=None,
        ai_summaries=True,
        readiness_checks=True,
        exports=True,
    ),
}

FEATURE_LABELS: dict[Feature, str] = {
    "ai_summaries": "AI summaries",
    "readiness_checks": "Readiness checks (Match This Tender)",
    "exports": "Report exports",
}


def cheapest_plan_with(feature: Feature) -> Plan:
    return next(plan for plan, limits in PLANS.items() if limits.allows(feature))
