import csv
import io
from datetime import UTC, datetime

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.plans import search_key, week_start
from app.services.tender_sync import SAST
from tests.conftest import (
    InMemoryMatchStore,
    InMemorySummaryStore,
    add_tender,
    auth_header,
    register,
)


def headers_for(client: TestClient, plan: str, email: str = "owner@acme.co.za") -> dict[str, str]:
    return auth_header(register(client, email=email, plan=plan))


def add_member(client: TestClient, headers: dict[str, str], email: str):
    return client.post(
        "/api/team/members",
        json={"full_name": "New Member", "email": email, "password": "memberpass1"},
        headers=headers,
    )


def search(client: TestClient, headers: dict[str, str], **params):
    return client.get("/api/tenders", params=params, headers=headers)


# --- Plan info and switching ---------------------------------------------------------


def test_new_teams_start_on_free(client: TestClient):
    headers = headers_for(client, "free")

    body = client.get("/api/team/plan", headers=headers).json()

    assert body["current"]["plan"] == "free"
    assert body["current"]["seats"] == 1
    assert body["usage"] == {
        "seats_used": 1,
        "seats_limit": 1,
        "searches_used": 0,
        "searches_limit": 3,
        "searches_reset_on": body["usage"]["searches_reset_on"],
    }
    assert [p["plan"] for p in body["available"]] == ["free", "basic", "pro"]


def test_only_owner_can_change_plan(client: TestClient):
    owner = headers_for(client, "basic")
    add_member(client, owner, "member@acme.co.za")
    member_token = client.post(
        "/api/auth/login", data={"username": "member@acme.co.za", "password": "memberpass1"}
    ).json()["access_token"]

    response = client.put("/api/team/plan", json={"plan": "pro"}, headers=auth_header(member_token))

    assert response.status_code == 403


def test_cannot_downgrade_with_too_many_members(client: TestClient):
    owner = headers_for(client, "basic")
    add_member(client, owner, "member@acme.co.za")

    response = client.put("/api/team/plan", json={"plan": "free"}, headers=owner)

    assert response.status_code == 409
    assert "Remove members" in response.json()["detail"]


# --- Seats ----------------------------------------------------------------------


@pytest.mark.parametrize(("plan", "allowed_members"), [("free", 0), ("basic", 2)])
def test_seat_limits(client: TestClient, plan: str, allowed_members: int):
    owner = headers_for(client, plan)

    for i in range(allowed_members):
        assert add_member(client, owner, f"m{i}@acme.co.za").status_code == 201
    blocked = add_member(client, owner, "one-too-many@acme.co.za")

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "upgrade_required"


def test_pro_has_unlimited_seats(client: TestClient):
    owner = headers_for(client, "pro")
    for i in range(5):
        assert add_member(client, owner, f"m{i}@acme.co.za").status_code == 201


# --- Weekly searches -------------------------------------------------------------


def test_free_plan_allows_three_distinct_searches_per_week(client: TestClient, db: Session):
    add_tender(db)
    headers = headers_for(client, "free")

    for q in ("roads", "security", "cleaning"):
        assert search(client, headers, q=q).status_code == 200
    blocked = search(client, headers, q="catering")

    assert blocked.status_code == 403
    detail = blocked.json()["detail"]
    assert detail["code"] == "upgrade_required"
    assert detail["required_plan"] == "basic"
    assert "reset on Monday" in detail["message"]


def test_paging_and_sorting_the_same_search_is_free(client: TestClient, db: Session):
    add_tender(db)
    headers = headers_for(client, "free")

    for params in (
        {"q": "Roads"},
        {"q": "roads", "page": 2},
        {"q": "  roads ", "sort": "newest"},
        {"q": "roads", "province": ["Gauteng"]},  # a new filter is a new search
    ):
        assert search(client, headers, **params).status_code == 200

    usage = client.get("/api/team/plan", headers=headers).json()["usage"]
    assert usage["searches_used"] == 2


def test_repeating_a_counted_search_still_works_at_the_limit(client: TestClient, db: Session):
    add_tender(db)
    headers = headers_for(client, "free")
    for q in ("a", "b", "c"):
        search(client, headers, q=q)

    assert search(client, headers, q="a").status_code == 200


def test_paid_plans_have_unlimited_searches(client: TestClient, db: Session):
    add_tender(db)
    headers = headers_for(client, "basic")
    for i in range(6):
        assert search(client, headers, q=f"query {i}").status_code == 200


def test_search_key_ignores_case_order_and_blanks():
    assert search_key({"q": "Road  Works", "province": ["Limpopo", "Gauteng"], "buyer": []}) == (
        search_key({"q": "road works", "province": ["Gauteng", "Limpopo"]})
    )
    assert search_key({"q": "roads"}) != search_key({"q": "roads", "province": ["Gauteng"]})


def test_week_starts_on_monday_in_south_africa():
    # Sunday 23:30 UTC is already Monday 01:30 in South Africa.
    sunday_night_utc = datetime(2026, 10, 18, 23, 30, tzinfo=UTC)
    assert week_start(sunday_night_utc).isoformat() == "2026-10-19"
    assert week_start(datetime(2026, 10, 21, 12, 0, tzinfo=SAST)).isoformat() == "2026-10-19"


# --- Feature gates -----------------------------------------------------------------


def test_free_plan_cannot_use_ai_summaries_or_matching(client: TestClient, db: Session):
    tender = add_tender(db)
    headers = headers_for(client, "free")

    for method, url in [
        ("GET", f"/api/tenders/{tender.id}/summary"),
        ("POST", f"/api/tenders/{tender.id}/summary"),
        ("GET", f"/api/tenders/{tender.id}/match"),
        ("POST", f"/api/tenders/{tender.id}/match"),
    ]:
        response = client.request(method, url, headers=headers)
        assert response.status_code == 403, url
        assert response.json()["detail"]["required_plan"] == "basic"


def test_free_workspace_hides_summaries_and_scores(
    client: TestClient,
    db: Session,
    summary_store: InMemorySummaryStore,
    match_store: InMemoryMatchStore,
):
    tender = add_tender(db)
    headers = headers_for(client, "free")
    client.post("/api/workspace", json={"tender_id": tender.id}, headers=headers)
    # A summary generated by another (paying) team, and a leftover score from before a downgrade.
    summary_store.docs[tender.id] = {"status": "ready", "content": {"summary": "Secret"}}
    team_id = client.get("/api/auth/me", headers=headers).json()["team"]["id"]
    match_store.docs[(team_id, tender.id)] = {"score": 90}

    item = client.get("/api/workspace", headers=headers).json()["items"][0]

    assert item["ai_summary"] is None
    assert item["match_score"] is None


def test_exports_are_pro_only(client: TestClient):
    headers = headers_for(client, "basic")

    response = client.get("/api/workspace/export", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"]["required_plan"] == "pro"


# --- Exports ------------------------------------------------------------------------


@pytest.fixture
def pro_workspace(
    client: TestClient,
    db: Session,
    summary_store: InMemorySummaryStore,
    match_store: InMemoryMatchStore,
) -> dict[str, str]:
    headers = headers_for(client, "pro")
    team_id = client.get("/api/auth/me", headers=headers).json()["team"]["id"]
    strong = add_tender(db, title="Road maintenance – Limpopo", tender_number="R1")
    weak = add_tender(db, title="Office furniture", tender_number="F1")
    for tender in (strong, weak):
        client.post("/api/workspace", json={"tender_id": tender.id}, headers=headers)
    summary_store.docs[strong.id] = {"status": "ready", "content": {"summary": "Fix roads."}}
    match_store.docs[(team_id, strong.id)] = {"score": 91, "verdict": "suitable"}
    match_store.docs[(team_id, weak.id)] = {"score": 30, "verdict": "not_suitable"}
    return headers


def test_csv_export(client: TestClient, pro_workspace: dict[str, str]):
    response = client.get("/api/workspace/export?format=csv", headers=pro_workspace)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert [r["Tender number"] for r in rows] == ["R1", "F1"]  # ranked by score
    assert rows[0]["Title"] == "Road maintenance – Limpopo"
    assert rows[0]["Match score"] == "91"
    assert rows[0]["Verdict"] == "Suitable"
    assert rows[0]["AI summary"] == "Fix roads."


def test_pdf_export(client: TestClient, pro_workspace: dict[str, str]):
    response = client.get("/api/workspace/export?format=pdf", headers=pro_workspace)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    with pymupdf.open(stream=response.content, filetype="pdf") as pdf:
        text = "".join(page.get_text() for page in pdf)
    assert "Acme Construction: workspace report" in text
    assert "Road maintenance" in text
    assert "91/100" in text
