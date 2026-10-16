from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.reference import CIDB_CLASS_NAMES, PROVINCES

SummaryStatus = Literal["none", "processing", "ready", "failed"]


def _short_list(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    return cleaned[:limit]


class CidbRequirement(BaseModel):
    class_code: str
    min_grade: int = Field(ge=1, le=9)


class TenderRequirements(BaseModel):
    """Structured requirements, used by readiness scoring to compare against a profile."""

    cidb: list[CidbRequirement] = []
    bbbee_min_level: int | None = Field(default=None, ge=1, le=8)
    min_years_experience: int | None = Field(default=None, ge=0, le=100)
    certifications: list[str] = []
    provinces: list[str] = []
    compulsory_briefing: bool | None = None

    @field_validator("cidb", mode="before")
    @classmethod
    def valid_cidb(cls, value: Any) -> list[dict[str, Any]]:
        result = []
        for item in value if isinstance(value, list) else []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("class_code", "")).upper().strip()
            try:
                grade = int(item.get("min_grade"))
            except (TypeError, ValueError):
                continue
            if code in CIDB_CLASS_NAMES and 1 <= grade <= 9:
                result.append({"class_code": code, "min_grade": grade})
        return result

    @field_validator("bbbee_min_level", "min_years_experience", mode="before")
    @classmethod
    def optional_int(cls, value: Any) -> int | None:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @field_validator("certifications", mode="before")
    @classmethod
    def certification_list(cls, value: Any) -> list[str]:
        return _short_list(value, 15)

    @field_validator("provinces", mode="before")
    @classmethod
    def known_provinces(cls, value: Any) -> list[str]:
        lookup = {p.lower().replace("-", " "): p for p in PROVINCES}
        names = [lookup.get(v.lower().replace("-", " ")) for v in _short_list(value, 9)]
        return [n for n in dict.fromkeys(names) if n]


class TenderSummaryContent(BaseModel):
    """What the AI produces for a tender. Lenient: bad or missing fields become empty."""

    summary: str = ""
    objective: str | None = None
    scope: list[str] = []
    closing_date: str | None = None
    eligibility: list[str] = []
    requirements: TenderRequirements = TenderRequirements()
    contract_duration: str | None = None
    evaluation: str | None = None
    estimated_value: float | None = None
    other_highlights: list[str] = []

    @field_validator("scope", "eligibility", "other_highlights", mode="before")
    @classmethod
    def bullet_list(cls, value: Any) -> list[str]:
        return _short_list(value, 8)

    @field_validator("estimated_value", mode="before")
    @classmethod
    def positive_number(cls, value: Any) -> float | None:
        try:
            number = float(str(value).replace(",", "").replace(" ", "").lstrip("Rr"))
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @field_validator("requirements", mode="before")
    @classmethod
    def requirements_object(cls, value: Any) -> Any:
        return value if isinstance(value, dict) else {}


class SummaryDocument(BaseModel):
    title: str
    chars: int


class TenderSummaryResponse(BaseModel):
    tender_id: int
    status: SummaryStatus
    content: TenderSummaryContent | None = None
    source: Literal["documents", "details_only"] | None = None
    documents: list[SummaryDocument] = []
    unreadable_documents: list[str] = []
    truncated: bool = False
    model: str | None = None
    error: str | None = None
    updated_at: datetime | None = None
