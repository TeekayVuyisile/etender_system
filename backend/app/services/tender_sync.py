"""Import tenders from the OCDS API into PostgreSQL and enrich them with portal details."""

import logging
import re
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.reference import PROVINCES
from app.models import Tender
from app.services.etenders_client import iter_ocds_releases, iter_portal_open_tenders

logger = logging.getLogger(__name__)

# South Africa has no daylight saving, so a fixed offset is exact.
SAST = timezone(timedelta(hours=2), "SAST")
NATIONAL = "National"
BATCH_SIZE = 200
EMPTY_VALUES = {"", "-", "n/a", "na", "none", "null", "tbc"}


@dataclass
class SyncResult:
    releases_fetched: int = 0
    releases_skipped: int = 0
    created: int = 0
    updated: int = 0
    enriched: int = 0
    portal_error: str | None = None
    duration_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Parsing helpers ----------------------------------------------------------


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return None if text.lower() in EMPTY_VALUES else text


def clean_delivery(value: Any) -> str | None:
    """The portal joins street-suburb-town-code with dashes, leaving stray ones for blanks."""
    text = clean(value)
    if text is None:
        return None
    parts = [part.strip() for part in text.split("-")]
    return clean(", ".join(p for p in parts if p and p.lower() not in EMPTY_VALUES))


def parse_sast(value: str | None) -> datetime | None:
    """Parse an eTenders timestamp.

    Both sources give South African local times; the OCDS API wrongly labels them as UTC
    ("14:00:00Z" for a tender the portal shows closing at 14:00), so any offset is ignored.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None
    if parsed.year < 1900:  # placeholder dates like 0001-01-01
        return None
    return parsed.replace(tzinfo=SAST)


def parse_amount(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount > 0 else None


_PROVINCE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (province, re.compile(pattern, re.IGNORECASE))
    for province, pattern in [
        ("Eastern Cape", r"\beastern cape\b|\bnelson mandela bay\b|\bgqeberha\b|\bbuffalo city\b"),
        ("Free State", r"\bfree state\b|\bmangaung\b|\bbloemfontein\b"),
        ("Gauteng", r"\bgauteng\b|\bjohannesburg\b|\btshwane\b|\bpretoria\b|\bekurhuleni\b"),
        ("KwaZulu-Natal", r"\bkwa-?zulu[- ]?natal\b|\bkzn\b|\bethekwini\b|\bdurban\b"),
        ("Limpopo", r"\blimpopo\b|\bpolokwane\b"),
        ("Mpumalanga", r"\bmpumalanga\b|\bmbombela\b|\bnelspruit\b"),
        ("Northern Cape", r"\bnorthern cape\b|\bkimberley\b"),
        ("North West", r"\bnorth[- ]west\b|\bmahikeng\b|\brustenburg\b"),
        ("Western Cape", r"\bwestern cape\b|\bcape town\b|\bstellenbosch\b"),
    ]
]


def infer_province(*texts: str | None) -> str | None:
    """Guess the province from place names in the text; None if absent or ambiguous."""
    text = " ".join(t for t in texts if t)
    matches = {province for province, pattern in _PROVINCE_PATTERNS if pattern.search(text)}
    return matches.pop() if len(matches) == 1 else None


def parse_release(release: dict[str, Any]) -> dict[str, Any]:
    """Map an OCDS release to Tender column values."""
    tender = release.get("tender") or {}
    buyer = release.get("buyer") or tender.get("procuringEntity") or {}
    period = tender.get("tenderPeriod") or {}
    tender_number = clean(tender.get("title")) or str(tender.get("id"))

    return {
        "ocid": release["ocid"],
        "etenders_id": int(tender["id"]),
        "tender_number": tender_number,
        "title": clean(tender.get("description")) or tender_number,
        "buyer_id": clean(buyer.get("id")),
        "buyer_name": clean(buyer.get("name")) or "Unknown buyer",
        "procurement_category": clean(tender.get("mainProcurementCategory")),
        "procurement_method": clean(tender.get("procurementMethodDetails")),
        "published_at": parse_sast(period.get("startDate")),
        "closing_at": parse_sast(period.get("endDate")),
        "estimated_value": parse_amount((tender.get("value") or {}).get("amount")),
        "documents": [
            {
                "id": doc.get("id"),
                "title": clean(doc.get("title")) or "Document",
                "url": doc.get("url"),
                "format": (clean(doc.get("format")) or "").lower() or None,
            }
            for doc in tender.get("documents") or []
            if doc.get("url")
        ],
    }


def apply_release(tender: Tender, values: dict[str, Any]) -> None:
    for field, value in values.items():
        setattr(tender, field, value)
    tender.document_count = len(tender.documents or [])
    # Never overwrite an official portal province with a guess.
    if tender.province_source != "portal":
        tender.province = infer_province(tender.title, tender.buyer_name)
        tender.province_source = "inferred" if tender.province else None
    tender.refresh_search_text()


def apply_portal_record(tender: Tender, record: dict[str, Any]) -> None:
    province = clean(record.get("province"))
    if province in PROVINCES or province == NATIONAL:
        tender.province = province
        tender.province_source = "portal"

    tender.category = clean(record.get("category")) or tender.category
    tender.delivery_location = clean_delivery(record.get("delivery"))
    tender.briefing_session = bool(record.get("briefingSession"))
    tender.briefing_compulsory = bool(record.get("briefingCompulsory"))
    tender.briefing_at = parse_sast(record.get("compulsory_briefing_session"))
    tender.briefing_venue = clean(record.get("briefingVenue"))
    tender.special_conditions = clean(record.get("conditions"))
    tender.contact_person = clean(record.get("contactPerson"))
    tender.contact_email = clean(record.get("email"))
    tender.contact_phone = clean(record.get("telephone"))
    tender.enriched_at = datetime.now(UTC)
    tender.refresh_search_text()


# --- Sync ---------------------------------------------------------------------


def _batches(items: list[Any], size: int = BATCH_SIZE) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


_BULK_FIELDS = [c.key for c in Tender.__table__.columns if c.key not in ("id", "created_at")]


def _bulk_update(db: Session, tenders: list[Tender]) -> None:
    """Write changed tenders in one batched UPDATE.

    Flushing objects one by one would send a separate UPDATE per row, each waiting a full
    network round trip to the database; a bulk update sends them together.
    """
    now = datetime.now(UTC)
    rows = [
        {"id": t.id, **{f: getattr(t, f) for f in _BULK_FIELDS}, "updated_at": now} for t in tenders
    ]
    for tender in tenders:
        db.expunge(tender)  # stop the session from also flushing these objects
    if rows:
        db.execute(update(Tender), rows)


def upsert_releases(db: Session, releases: Iterable[dict[str, Any]], result: SyncResult) -> None:
    # The same tender can appear in several releases; keep the latest one.
    latest: dict[str, dict[str, Any]] = {}
    for release in releases:
        result.releases_fetched += 1
        if not (release.get("ocid") and (release.get("tender") or {}).get("id")):
            continue
        current = latest.get(release["ocid"])
        if current is None or release.get("date", "") >= current.get("date", ""):
            latest[release["ocid"]] = release

    for batch in _batches(list(latest.values())):
        ocids = [r["ocid"] for r in batch]
        existing = {t.ocid: t for t in db.scalars(select(Tender).where(Tender.ocid.in_(ocids)))}
        new_tenders: list[Tender] = []
        for release in batch:
            tender = existing.get(release["ocid"])
            if tender is None:
                tender = Tender()
                new_tenders.append(tender)
            apply_release(tender, parse_release(release))
        _bulk_update(db, list(existing.values()))
        db.add_all(new_tenders)  # new rows are inserted in batches automatically
        db.commit()
        result.created += len(new_tenders)
        result.updated += len(existing)


def enrich_from_portal(db: Session, records: Iterable[dict[str, Any]], result: SyncResult) -> None:
    by_id = {int(r["id"]): r for r in records if r.get("id")}
    for batch in _batches(list(by_id)):
        tenders = list(db.scalars(select(Tender).where(Tender.etenders_id.in_(batch))))
        for tender in tenders:
            apply_portal_record(tender, by_id[tender.etenders_id])
        _bulk_update(db, tenders)
        db.commit()
        result.enriched += len(tenders)


def sync_tenders(
    db: Session, client: httpx.Client, days: int = 30, enrich: bool = True
) -> SyncResult:
    """Import the last `days` days of OCDS releases, then enrich open tenders from the portal."""
    started = time.monotonic()
    result = SyncResult()
    today = datetime.now(SAST).date()

    skipped: list[int] = []
    releases = iter_ocds_releases(client, today - timedelta(days=days), today, skipped)
    upsert_releases(db, releases, result)
    result.releases_skipped = len(skipped)
    logger.info(
        "OCDS: %d releases (%d skipped due to API errors), %d new, %d updated",
        result.releases_fetched,
        result.releases_skipped,
        result.created,
        result.updated,
    )

    if enrich:
        try:
            enrich_from_portal(db, iter_portal_open_tenders(client), result)
            logger.info("Portal: enriched %d tenders", result.enriched)
        except httpx.HTTPError as error:
            # The portal is an extra; a failure here must not lose the OCDS import.
            db.rollback()
            result.portal_error = str(error)
            logger.warning("Portal enrichment failed: %s", error)

    result.duration_seconds = round(time.monotonic() - started, 1)
    return result


def default_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True)
