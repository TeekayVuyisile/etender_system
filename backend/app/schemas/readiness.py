from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["met", "partial", "not_met", "unknown"]
Verdict = Literal["suitable", "possibly_suitable", "not_suitable"]
Competition = Literal["low", "moderate", "high"]


class ChecklistItem(BaseModel):
    key: str
    label: str
    status: CheckStatus
    detail: str
    weight: int
    points: float


class ReadinessResult(BaseModel):
    score: int
    verdict: Verdict
    competition: Competition
    recommendation: str
    checklist: list[ChecklistItem]
    blockers: list[str]


class MatchResultResponse(ReadinessResult):
    tender_id: int
    checked_at: datetime
    checked_by: str | None = None
    # True if the company profile or AI summary changed after this check was run.
    outdated: bool = False
