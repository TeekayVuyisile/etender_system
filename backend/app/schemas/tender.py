from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenderDocument(BaseModel):
    id: str | None = None
    title: str
    url: str
    format: str | None = None


class TenderListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_number: str
    title: str
    buyer_name: str
    province: str | None
    category: str | None
    procurement_category: str | None
    procurement_method: str | None
    published_at: datetime | None
    closing_at: datetime | None
    estimated_value: float | None
    briefing_compulsory: bool
    document_count: int


class TenderDetail(TenderListItem):
    documents: list[TenderDocument]
    ocid: str
    etenders_id: int
    province_source: str | None
    delivery_location: str | None
    briefing_session: bool
    briefing_at: datetime | None
    briefing_venue: str | None
    special_conditions: str | None
    contact_person: str | None
    contact_email: str | None
    contact_phone: str | None
    updated_at: datetime


class TenderSearchResponse(BaseModel):
    items: list[TenderListItem]
    total: int
    page: int
    page_size: int
    province_counts: dict[str, int]


class BuyerOption(BaseModel):
    name: str
    open_tenders: int
