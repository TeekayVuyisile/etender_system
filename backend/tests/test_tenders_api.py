from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import NOW, add_tender, auth_header, register


@pytest.fixture
def token(client: TestClient) -> str:
    return register(client)


def search(client: TestClient, token: str, **params: Any) -> dict[str, Any]:
    response = client.get("/api/tenders", params=params, headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()


def titles(body: dict[str, Any]) -> list[str]:
    return [item["title"] for item in body["items"]]


def test_search_requires_login(client: TestClient):
    assert client.get("/api/tenders").status_code == 401


def test_keyword_search_matches_title_and_buyer(client: TestClient, db: Session, token: str):
    add_tender(db, title="Road construction in Ward 5")
    add_tender(db, title="Security services", buyer_name="Road Accident Fund")
    add_tender(db, title="Catering services")

    body = search(client, token, q="road")

    assert sorted(titles(body)) == ["Road construction in Ward 5", "Security services"]
    assert body["total"] == 2


def test_all_keywords_must_match(client: TestClient, db: Session, token: str):
    add_tender(db, title="Road construction")
    add_tender(db, title="Building construction")

    assert titles(search(client, token, q="road construction")) == ["Road construction"]


def test_only_open_tenders_by_default(client: TestClient, db: Session, token: str):
    add_tender(db, title="Open tender")
    add_tender(db, title="Closed tender", closing_at=NOW - timedelta(days=1))

    assert titles(search(client, token)) == ["Open tender"]
    assert titles(search(client, token, status="closed")) == ["Closed tender"]
    assert search(client, token, status="all")["total"] == 2


def test_province_filter_and_counts(client: TestClient, db: Session, token: str):
    add_tender(db, title="A", province="Gauteng")
    add_tender(db, title="B", province="Limpopo")
    add_tender(db, title="C", province="Limpopo")
    add_tender(db, title="D", province=None)

    body = search(client, token, province=["Limpopo"])

    assert sorted(titles(body)) == ["B", "C"]
    # Counts ignore the province filter so the UI can show what each option would return.
    assert body["province_counts"] == {"Gauteng": 1, "Limpopo": 2, "Unknown": 1}


def test_multiple_provinces(client: TestClient, db: Session, token: str):
    add_tender(db, title="A", province="Gauteng")
    add_tender(db, title="B", province="Limpopo")
    add_tender(db, title="C", province="Western Cape")

    body = search(client, token, province=["Gauteng", "Western Cape"])

    assert sorted(titles(body)) == ["A", "C"]


def test_closing_date_window(client: TestClient, db: Session, token: str):
    add_tender(db, title="Soon", closing_at=NOW + timedelta(days=2))
    add_tender(db, title="Later", closing_at=NOW + timedelta(days=40))

    window_end = (NOW + timedelta(days=7)).date().isoformat()
    assert titles(search(client, token, closing_to=window_end)) == ["Soon"]


def test_buyer_filter(client: TestClient, db: Session, token: str):
    add_tender(db, title="A", buyer_name="City of Cape Town")
    add_tender(db, title="B", buyer_name="ESKOM")

    assert titles(search(client, token, buyer=["ESKOM"])) == ["B"]


def test_budget_filter_only_matches_known_values(client: TestClient, db: Session, token: str):
    add_tender(db, title="Small", estimated_value=50_000)
    add_tender(db, title="Large", estimated_value=5_000_000)
    add_tender(db, title="Unknown value", estimated_value=None)

    assert titles(search(client, token, min_value=1_000_000)) == ["Large"]
    assert titles(search(client, token, max_value=100_000)) == ["Small"]


def test_sort_by_closing_soon_and_pagination(client: TestClient, db: Session, token: str):
    for days in (30, 5, 15):
        add_tender(db, title=f"Closes in {days} days", closing_at=NOW + timedelta(days=days))

    page1 = search(client, token, sort="closing_soon", page_size=2)
    page2 = search(client, token, sort="closing_soon", page_size=2, page=2)

    assert titles(page1) == ["Closes in 5 days", "Closes in 15 days"]
    assert titles(page2) == ["Closes in 30 days"]
    assert page1["total"] == 3


def test_invalid_province_is_rejected(client: TestClient, token: str):
    response = client.get(
        "/api/tenders", params={"province": "Atlantis"}, headers=auth_header(token)
    )
    assert response.status_code == 422


def test_tender_detail(client: TestClient, db: Session, token: str):
    tender = add_tender(db, contact_person="Ms Jane Doe", documents=[{"title": "Doc", "url": "u"}])

    response = client.get(f"/api/tenders/{tender.id}", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["contact_person"] == "Ms Jane Doe"
    assert body["document_count"] == 1
    assert client.get("/api/tenders/999999", headers=auth_header(token)).status_code == 404


def test_buyers_endpoint(client: TestClient, db: Session, token: str):
    add_tender(db, buyer_name="ESKOM")
    add_tender(db, buyer_name="ESKOM")
    add_tender(db, buyer_name="City of Cape Town")
    add_tender(db, buyer_name="Closed Buyer", closing_at=NOW - timedelta(days=1))

    response = client.get("/api/tenders/buyers", headers=auth_header(token))
    filtered = client.get("/api/tenders/buyers", params={"q": "cape"}, headers=auth_header(token))

    assert response.json() == [
        {"name": "ESKOM", "open_tenders": 2},
        {"name": "City of Cape Town", "open_tenders": 1},
    ]
    assert [b["name"] for b in filtered.json()] == ["City of Cape Town"]
