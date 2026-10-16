from datetime import date, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tender
from app.services.etenders_client import (
    OCDS_PAGE_SIZE,
    OCDS_RELEASES_URL,
    PORTAL_TENDERS_URL,
    iter_ocds_releases,
)
from app.services.tender_sync import (
    SAST,
    apply_portal_record,
    clean_delivery,
    infer_province,
    parse_release,
    sync_tenders,
)


def make_release(etenders_id: int, **tender_overrides: Any) -> dict[str, Any]:
    tender = {
        "id": str(etenders_id),
        "title": f"REF-{etenders_id}/2026",
        "description": "Construction of a new access road",
        "mainProcurementCategory": "works",
        "procurementMethodDetails": "Request for Bid(Open-Tender)",
        "value": {"amount": "0", "currency": "ZAR"},
        "tenderPeriod": {
            "startDate": "2026-10-01T00:00:00Z",
            "endDate": "2026-10-30T14:00:00Z",
        },
        "documents": [
            {
                "id": "doc-1",
                "title": "Bid document.pdf",
                "url": "https://x/doc.pdf",
                "format": "pdf",
            }
        ],
        **tender_overrides,
    }
    return {
        "ocid": f"ocds-9t57fa-{etenders_id}",
        "date": "2026-10-01T00:00:00Z",
        "buyer": {"id": "89", "name": "Dawid Kruiper Local Municipality"},
        "tender": tender,
    }


def make_portal_record(etenders_id: int, **overrides: Any) -> dict[str, Any]:
    return {
        "id": etenders_id,
        "province": "Northern Cape",
        "category": "Civil engineering",
        "delivery": "1 Main Street-Upington-8800",
        "briefingSession": True,
        "briefingCompulsory": True,
        "compulsory_briefing_session": "2026-10-20T10:00:00",
        "briefingVenue": "Municipal offices",
        "conditions": "N/A",
        "contactPerson": "Ms Jane Doe",
        "email": "jane@example.gov.za",
        "telephone": "054-000-0000",
        **overrides,
    }


# --- Parsing ------------------------------------------------------------------


def test_parse_release_maps_fields():
    values = parse_release(make_release(174000))

    assert values["etenders_id"] == 174000
    assert values["tender_number"] == "REF-174000/2026"
    assert values["title"] == "Construction of a new access road"
    assert values["buyer_name"] == "Dawid Kruiper Local Municipality"
    assert values["estimated_value"] is None  # the API reports 0 when the value is unknown
    assert values["documents"][0]["format"] == "pdf"


def test_parse_release_treats_times_as_south_african():
    values = parse_release(make_release(1))

    # "14:00:00Z" from the API is really 14:00 in South Africa.
    assert values["closing_at"] == datetime(2026, 10, 30, 14, 0, tzinfo=SAST)


def test_parse_release_keeps_positive_amounts():
    values = parse_release(make_release(1, value={"amount": "1500000.50"}))

    assert float(values["estimated_value"]) == 1500000.50


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "Hartebeestfontein Office Park, Bapsfontein Road-Kaalfontein-Kempton Park-",
            "Hartebeestfontein Office Park, Bapsfontein Road, Kaalfontein, Kempton Park",
        ),
        ("N/A-N/A--", None),
        (None, None),
    ],
)
def test_clean_delivery(value: str | None, expected: str | None):
    assert clean_delivery(value) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Paving in Polokwane", "Limpopo"),
        ("SASSA Kwa-Zulu Natal medical assessments", "KwaZulu-Natal"),
        ("City of Cape Town", "Western Cape"),
        ("Supply of laptops", None),
        ("Gauteng and Western Cape offices", None),  # ambiguous
    ],
)
def test_infer_province(text: str, expected: str | None):
    assert infer_province(text) == expected


def test_portal_record_overrides_inferred_province():
    tender = Tender(title="Road in Cape Town", tender_number="X", buyer_name="Buyer")
    tender.province, tender.province_source = "Western Cape", "inferred"

    apply_portal_record(tender, make_portal_record(1))

    assert tender.province == "Northern Cape"
    assert tender.province_source == "portal"
    assert tender.special_conditions is None  # "N/A" is treated as empty
    assert tender.briefing_at == datetime(2026, 10, 20, 10, 0, tzinfo=SAST)
    assert "civil engineering" in tender.search_text
    assert tender.delivery_location == "1 Main Street, Upington, 8800"


# --- OCDS client ----------------------------------------------------------------


@respx.mock
def test_ocds_client_follows_pages():
    first = [make_release(i) for i in range(OCDS_PAGE_SIZE)]
    respx.get(OCDS_RELEASES_URL, params={"PageNumber": "1"}).respond(json={"releases": first})
    respx.get(OCDS_RELEASES_URL, params={"PageNumber": "2"}).respond(
        json={"releases": [make_release(999)]}
    )

    with httpx.Client() as client:
        releases = list(iter_ocds_releases(client, date(2026, 10, 1), date(2026, 10, 16)))

    assert len(releases) == OCDS_PAGE_SIZE + 1


@respx.mock
def test_ocds_client_skips_records_that_crash_the_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.etenders_client.time.sleep", lambda _: None)
    bad_position = 37
    records = [make_release(i) for i in range(50)]

    def fake_api(request: httpx.Request) -> httpx.Response:
        size = int(request.url.params["PageSize"])
        offset = (int(request.url.params["PageNumber"]) - 1) * size
        if offset <= bad_position < offset + size:
            return httpx.Response(500)
        return httpx.Response(200, json={"releases": records[offset : offset + size]})

    respx.get(OCDS_RELEASES_URL).mock(side_effect=fake_api)
    skipped: list[int] = []

    with httpx.Client() as client:
        releases = list(iter_ocds_releases(client, date(2026, 10, 1), date(2026, 10, 2), skipped))

    assert len(releases) == 49
    assert skipped == [bad_position]


# --- Full sync ----------------------------------------------------------------


@respx.mock
def test_sync_creates_updates_and_enriches(db: Session):
    respx.get(OCDS_RELEASES_URL).respond(json={"releases": [make_release(1), make_release(2)]})
    respx.get(PORTAL_TENDERS_URL).respond(json={"recordsTotal": 1, "data": [make_portal_record(2)]})

    with httpx.Client() as client:
        first = sync_tenders(db, client, days=7)
        updated_release = make_release(1, description="Updated description")
        respx.get(OCDS_RELEASES_URL).respond(json={"releases": [updated_release]})
        second = sync_tenders(db, client, days=7)

    assert (first.created, first.updated, first.enriched) == (2, 0, 1)
    assert (second.created, second.updated) == (0, 1)
    tenders = {t.etenders_id: t for t in db.scalars(select(Tender))}
    assert tenders[1].title == "Updated description"
    assert tenders[2].province == "Northern Cape"
    assert tenders[2].contact_person == "Ms Jane Doe"


@respx.mock
def test_sync_keeps_ocds_data_when_portal_fails(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.etenders_client.time.sleep", lambda _: None)
    respx.get(OCDS_RELEASES_URL).respond(json={"releases": [make_release(1)]})
    respx.get(PORTAL_TENDERS_URL).respond(status_code=503)

    with httpx.Client() as client:
        result = sync_tenders(db, client, days=7)

    assert result.created == 1
    assert result.portal_error is not None
    assert db.scalar(select(Tender).where(Tender.etenders_id == 1)) is not None


def test_sast_is_two_hours_ahead_of_utc():
    assert SAST.utcoffset(None) == timedelta(hours=2)
