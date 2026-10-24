"""Buyer analytics for the public API, cached in Redis (or MongoDB without Redis).

Neither eTenders source publishes awarded contract values, so "spend" here means what buyers
advertise: how many tenders they put out, and the total of the values that are known
(published, or extracted from documents by the AI summary). Every result says how much of it
is covered by known values.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from pymongo.collection import Collection
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.mongo import get_mongo_db
from app.models import Tender
from app.services.cache import Cache, get_cache
from app.services.tender_sync import SAST

CACHE_TTL = timedelta(hours=1)


class AnalyticsCache(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any]) -> None: ...


class MongoAnalyticsCache:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def get(self, key: str) -> dict[str, Any] | None:
        doc = self.collection.find_one({"_id": key})
        if doc is None or doc["expires_at"] < datetime.now(UTC):
            return None
        return doc["value"]

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.collection.replace_one(
            {"_id": key},
            {"_id": key, "value": value, "expires_at": datetime.now(UTC) + CACHE_TTL},
            upsert=True,
        )


class RedisAnalyticsCache:
    """Keys are tied to the tenders version, so a sync also refreshes the analytics."""

    def __init__(self, cache: Cache) -> None:
        self.cache = cache

    def _key(self, key: str) -> str:
        return f"analytics:v{self.cache.tenders_version()}:{key}"

    def get(self, key: str) -> dict[str, Any] | None:
        return self.cache.get_json(self._key(key))

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.cache.set_json(self._key(key), value, int(CACHE_TTL.total_seconds()))


def get_analytics_cache() -> AnalyticsCache:
    cache = get_cache()
    if cache.enabled:
        return RedisAnalyticsCache(cache)
    return MongoAnalyticsCache(get_mongo_db()["analytics_cache"])


def cache_key(name: str, params: dict[str, Any]) -> str:
    raw = json.dumps({"name": name, **params}, sort_keys=True, default=str)
    return f"{name}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def spend_by_buyer(
    db: Session, since: date, province: str | None, limit: int, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    start = datetime.combine(since, datetime.min.time(), tzinfo=SAST)
    conditions = [Tender.published_at >= start]
    if province:
        conditions.append(Tender.province == province)

    tender_count = func.count(Tender.id)
    rows = db.execute(
        select(
            Tender.buyer_name,
            tender_count,
            func.sum(case((Tender.closing_at >= now, 1), else_=0)),
            func.count(Tender.estimated_value),
            func.coalesce(func.sum(Tender.estimated_value), 0),
        )
        .where(*conditions)
        .group_by(Tender.buyer_name)
        .order_by(tender_count.desc(), Tender.buyer_name)
        .limit(limit)
    ).all()

    buyers = [row[0] for row in rows]
    breakdown: dict[str, dict[str, dict[str, int]]] = {
        b: {"provinces": {}, "categories": {}} for b in buyers
    }
    if buyers:
        for column, key in ((Tender.province, "provinces"), (Tender.category, "categories")):
            for buyer, value, count in db.execute(
                select(Tender.buyer_name, column, func.count())
                .where(*conditions, Tender.buyer_name.in_(buyers))
                .group_by(Tender.buyer_name, column)
            ):
                breakdown[buyer][key][value or "Unknown"] = count

    totals = db.execute(
        select(func.count(Tender.id), func.count(Tender.estimated_value)).where(*conditions)
    ).one()

    def top(counts: dict[str, int], n: int = 3) -> list[dict[str, Any]]:
        return [
            {"name": name, "tenders": count}
            for name, count in sorted(counts.items(), key=lambda item: -item[1])[:n]
        ]

    return {
        "since": since.isoformat(),
        "province": province,
        "generated_at": now.isoformat(),
        "total_tenders": totals[0],
        "tenders_with_known_value": totals[1],
        "note": (
            "Award values are not published by the eTenders sources, so values are the "
            "advertised or AI-extracted values of tenders where known. See value_coverage."
        ),
        "buyers": [
            {
                "buyer": buyer,
                "tenders_advertised": count,
                "open_tenders": int(open_count or 0),
                "tenders_with_known_value": known,
                "known_value_total": float(value_total or 0),
                "value_coverage": round(known / count, 3) if count else 0.0,
                "top_provinces": top(breakdown[buyer]["provinces"]),
                "top_categories": top(breakdown[buyer]["categories"]),
            }
            for buyer, count, open_count, known, value_total in rows
        ],
    }
