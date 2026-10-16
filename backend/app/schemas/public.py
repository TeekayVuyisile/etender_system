from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.company_profile import ReadinessProfile
from app.schemas.readiness import ReadinessResult, Verdict
from app.schemas.summary import TenderRequirements


class PublicSummary(BaseModel):
    summary: str
    objective: str | None
    scope: list[str]
    eligibility: list[str]
    requirements: TenderRequirements
    contract_duration: str | None
    evaluation: str | None
    generated_at: datetime | None


class Suitability(BaseModel):
    """Readiness against the calling team's company profile."""

    score: int
    verdict: Verdict
    recommendation: str


class EnrichedRelease(BaseModel):
    id: int
    ocid: str
    etenders_id: int
    tender_number: str
    title: str
    buyer: str
    province: str | None
    category: str | None
    procurement_method: str | None
    published_at: datetime | None
    closing_at: datetime | None
    estimated_value: float | None
    briefing_compulsory: bool
    document_count: int
    ai_summary: PublicSummary | None = Field(
        description="Present when an AI summary has been generated and your plan includes it"
    )
    suitability: Suitability | None = Field(
        description="Present when the tender has an AI summary and your plan includes "
        "readiness checks; scored against your team's company profile"
    )


class EnrichedReleasesResponse(BaseModel):
    releases: list[EnrichedRelease]
    total: int
    page: int
    page_size: int
    includes_ai_summaries: bool
    includes_suitability: bool


class BuyerBreakdown(BaseModel):
    name: str
    tenders: int


class BuyerSpend(BaseModel):
    buyer: str
    tenders_advertised: int
    open_tenders: int
    tenders_with_known_value: int
    known_value_total: float
    value_coverage: float = Field(description="Share of tenders whose value is known (0-1)")
    top_provinces: list[BuyerBreakdown]
    top_categories: list[BuyerBreakdown]


class SpendByBuyerResponse(BaseModel):
    since: str
    province: str | None
    generated_at: datetime
    total_tenders: int
    tenders_with_known_value: int
    note: str
    buyers: list[BuyerSpend]
    cached: bool = False


class SummaryExtractResponse(BaseModel):
    filename: str
    pages: int
    summary: str
    word_count: int
    truncated_input: bool = Field(description="True if only key sections of a long file were used")
    model: str


class ReadinessCheckRequest(BaseModel):
    tender_id: int
    company_profile: ReadinessProfile | None = Field(
        default=None, description="Profile to score against; defaults to your team's profile"
    )


class ReadinessCheckResponse(ReadinessResult):
    tender_id: int
    profile_source: str = Field(description='"request" or "team_profile"')
