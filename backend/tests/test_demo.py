from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.auth import demo_rate_limiter
from app.core.config import settings
from app.models import Team, User
from app.services.demo import (
    choose_demo_tenders,
    delete_expired_demos,
    prepare_demo_summaries,
)
from tests.conftest import (
    NOW,
    FakeLLM,
    InMemoryNotificationStore,
    InMemorySummaryStore,
    TestingSessionLocal,
    add_tender,
    auth_header,
)
from tests.test_summaries import DOC_URL, REQUIREMENTS_TEXT, make_pdf


@pytest.fixture
def demo_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_mode_enabled", True)
    demo_rate_limiter._hits.clear()


def road_tender(db: Session, title: str = "Routine road maintenance", **overrides: Any):
    values = {"title": title, "province": "Limpopo", "closing_at": NOW + timedelta(days=10)}
    return add_tender(db, **{**values, **overrides})


def ready(store: InMemorySummaryStore, tender_id: int) -> None:
    store.docs[tender_id] = {
        "status": "ready",
        "updated_at": NOW,
        "content": {
            "summary": "Road maintenance in Limpopo.",
            "scope": ["Road maintenance"],
            "requirements": {"cidb": [{"class_code": "CE", "min_grade": 6}]},
        },
    }


def start_demo(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/demo")
    assert response.status_code == 201, response.text
    return auth_header(response.json()["access_token"])


# --- Endpoint ---------------------------------------------------------------------------


def test_demo_is_off_by_default(client: TestClient):
    assert client.post("/api/auth/demo").status_code == 404
    assert client.get("/api/health").json()["demo_mode"] is False


def test_try_the_demo_creates_a_full_workspace(
    client: TestClient,
    db: Session,
    demo_enabled: None,
    summary_store: InMemorySummaryStore,
    notification_store: InMemoryNotificationStore,
):
    tenders = [road_tender(db, f"Road resurfacing project {i}") for i in range(4)]
    road_tender(db, "Supply of laboratory chemicals")  # not relevant: not picked
    ready(summary_store, tenders[0].id)

    headers = start_demo(client)

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["full_name"] == "Thabo Mokoena"
    assert me["role"] == "owner"
    assert me["team"]["is_demo"] is True
    assert me["team"]["plan"] == "pro"
    assert client.get("/api/health").json()["demo_mode"] is True

    members = client.get("/api/team/members", headers=headers).json()
    assert [m["full_name"] for m in members] == ["Thabo Mokoena", "Lerato Dlamini", "Sipho Nkosi"]
    assert client.get("/api/company-profile", headers=headers).status_code == 200

    workspace = client.get("/api/workspace", headers=headers).json()
    titles = [i["tender"]["title"] for i in workspace["items"]]
    assert len(titles) == 4
    assert "Supply of laboratory chemicals" not in titles
    assert workspace["items"][0]["match_score"] == 100  # the summarised tender, ranked first
    assert workspace["status_counts"]["preparing"] == 1

    entry = client.get(f"/api/workspace/{workspace['items'][0]['id']}", headers=headers).json()
    assert entry["notes"] and entry["tasks"]
    assert len(entry["status_changes"]) == 2

    inbox = client.get("/api/notifications", headers=headers).json()
    assert inbox["unread_count"] > 0
    assert all("Thabo" not in n["title"] for n in inbox["items"])  # only teammates' actions


def test_each_demo_is_private(client: TestClient, db: Session, demo_enabled: None):
    road_tender(db)
    first, second = start_demo(client), start_demo(client)

    team_a = client.get("/api/auth/me", headers=first).json()["team"]["id"]
    team_b = client.get("/api/auth/me", headers=second).json()["team"]["id"]
    entry = client.get("/api/workspace", headers=first).json()["items"][0]
    client.patch(f"/api/workspace/{entry['id']}", json={"status": "submitted"}, headers=first)

    assert team_a != team_b
    assert client.get(f"/api/workspace/{entry['id']}", headers=second).status_code == 404


def test_demo_works_without_any_matching_tenders(client: TestClient, demo_enabled: None):
    headers = start_demo(client)
    assert client.get("/api/workspace", headers=headers).json()["items"] == []


def test_demo_is_rate_limited(client: TestClient, demo_enabled: None):
    for _ in range(10):
        start_demo(client)
    assert client.post("/api/auth/demo").status_code == 429


# --- Choosing tenders ------------------------------------------------------------------------


def test_choose_prefers_summarised_tenders_and_one_closing_soon(
    db: Session, summary_store: InMemorySummaryStore
):
    now = datetime.now(UTC)
    later = [
        road_tender(db, f"Road construction {i}", closing_at=now + timedelta(days=20))
        for i in range(8)
    ]
    soon = road_tender(db, "Paving repairs", closing_at=now + timedelta(days=2))
    ready(summary_store, later[7].id)

    chosen = choose_demo_tenders(db, summary_store, now)

    assert chosen[0].id == later[7].id
    assert soon in chosen
    assert len(chosen) == 6


def test_choose_ignores_other_provinces_and_closing_today(
    db: Session, summary_store: InMemorySummaryStore
):
    now = datetime.now(UTC)
    road_tender(db, "Road works in the Cape", province="Western Cape")
    road_tender(db, "Road works closing now", closing_at=now + timedelta(hours=2))
    national = road_tender(db, "National road programme", province="National")

    assert choose_demo_tenders(db, summary_store, now) == [national]


# --- Upkeep ------------------------------------------------------------------------------


def test_expired_demo_teams_are_deleted(client: TestClient, db: Session, demo_enabled: None):
    start_demo(client)
    real_team = Team(name="Real customer")
    db.add(real_team)
    db.commit()
    deleted_documents: list[int] = []

    # Not yet expired.
    assert delete_expired_demos(db, timedelta(hours=24), deleted_documents.append) == 0

    later = datetime.now(UTC) + timedelta(hours=25)
    assert delete_expired_demos(db, timedelta(hours=24), deleted_documents.append, now=later) == 1
    assert [t.name for t in db.query(Team).all()] == ["Real customer"]
    assert len(deleted_documents) == 1
    assert db.query(User).filter(User.email.like("%@demo.example.com")).count() == 0


@respx.mock
def test_prepare_demo_summaries_generates_missing_ones(
    db: Session, summary_store: InMemorySummaryStore, llm: FakeLLM
):
    respx.get(DOC_URL).respond(content=make_pdf(REQUIREMENTS_TEXT))
    doc = [{"title": "bid.pdf", "url": DOC_URL, "format": "pdf"}]
    tenders = [road_tender(db, f"Road maintenance {i}", documents=doc) for i in range(4)]
    road_tender(db, "Road with no documents")  # skipped: nothing to summarise
    ready(summary_store, tenders[0].id)

    generated = prepare_demo_summaries(TestingSessionLocal, summary_store, llm, target=3)

    assert generated == 2
    assert sum(d.get("status") == "ready" for d in summary_store.docs.values()) == 3
