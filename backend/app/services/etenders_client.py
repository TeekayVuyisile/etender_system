"""HTTP clients for the two eTenders data sources.

- OCDS API (documented, the primary source): https://ocds-api.etenders.gov.za/swagger
- eTenders portal listing (used by etenders.gov.za itself): adds province, category,
  briefing session and contact details that the OCDS releases don't include.
"""

import logging
import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OCDS_RELEASES_URL = "https://ocds-api.etenders.gov.za/api/OCDSReleases"
PORTAL_TENDERS_URL = "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"
PORTAL_STATUS_PUBLISHED = 1

# The OCDS API returns an empty response for very large pages, so keep pages modest.
OCDS_PAGE_SIZE = 100
PORTAL_PAGE_SIZE = 200


def get_json(client: httpx.Client, url: str, params: dict[str, Any], attempts: int = 3) -> Any:
    """GET a JSON response, retrying transient failures with a short backoff."""
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            if attempt == attempts:
                raise
            logger.warning(
                "Request to %s failed (%s), retrying (%d/%d)", url, error, attempt, attempts
            )
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def _is_server_error(error: httpx.HTTPError) -> bool:
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500


def _get_ocds_page(
    client: httpx.Client, filters: dict[str, str], offset: int, size: int, attempts: int
) -> list[dict[str, Any]]:
    params = {**filters, "PageNumber": offset // size + 1, "PageSize": size}
    return get_json(client, OCDS_RELEASES_URL, params, attempts=attempts).get("releases") or []


def _split_failed_page(
    client: httpx.Client, filters: dict[str, str], offset: int, size: int, skipped: list[int]
) -> Iterator[dict[str, Any]]:
    """Refetch a failing page in 10x smaller pages, down to single records.

    Some individual records make the OCDS API itself crash (HTTP 500), which fails any page
    that contains them. Narrowing down lets us skip just those records.
    """
    smaller = size // 10
    for sub_offset in range(offset, offset + size, smaller):
        try:
            releases = _get_ocds_page(client, filters, sub_offset, smaller, attempts=1)
        except httpx.HTTPError as error:
            if not _is_server_error(error):
                raise
            if smaller == 1:
                logger.warning("Skipping OCDS record at position %d (API error)", sub_offset)
                skipped.append(sub_offset)
            else:
                yield from _split_failed_page(client, filters, sub_offset, smaller, skipped)
            continue
        yield from releases
        if len(releases) < smaller:
            return


def iter_ocds_releases(
    client: httpx.Client, date_from: date, date_to: date, skipped: list[int] | None = None
) -> Iterator[dict[str, Any]]:
    """Yield every OCDS release published between the two dates (inclusive).

    Positions of records the API fails to return are appended to `skipped`.
    """
    skipped = skipped if skipped is not None else []
    filters = {"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()}
    offset = 0
    while True:
        try:
            releases = _get_ocds_page(client, filters, offset, OCDS_PAGE_SIZE, attempts=2)
        except httpx.HTTPError as error:
            if not _is_server_error(error):
                raise
            # Can't tell whether this was the last page, so continue until an empty page.
            yield from _split_failed_page(client, filters, offset, OCDS_PAGE_SIZE, skipped)
        else:
            yield from releases
            if len(releases) < OCDS_PAGE_SIZE:
                return
        offset += OCDS_PAGE_SIZE


def iter_portal_open_tenders(client: httpx.Client) -> Iterator[dict[str, Any]]:
    """Yield every currently published (open) tender from the eTenders portal listing."""
    start = 0
    while True:
        data = get_json(
            client,
            PORTAL_TENDERS_URL,
            {
                "draw": 1,
                "start": start,
                "length": PORTAL_PAGE_SIZE,
                "status": PORTAL_STATUS_PUBLISHED,
            },
        )
        records = data.get("data") or []
        yield from records
        start += len(records)
        if not records or start >= data.get("recordsTotal", 0):
            return
