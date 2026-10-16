import os

# Must be set before the app is imported, so tests never touch real databases.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MONGODB_URL"] = "mongodb://localhost:27017"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"

from collections.abc import Iterator  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.routes.tenders import require_llm  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import (
    get_db,  # noqa: E402
    get_session_factory,  # noqa: E402
)
from app.main import app  # noqa: E402
from app.models import Tender  # noqa: E402
from app.services.activity import get_activity_logger  # noqa: E402
from app.services.llm import LLMResponse  # noqa: E402
from app.services.match_store import get_match_store  # noqa: E402
from app.services.summary_store import get_summary_store  # noqa: E402

# StaticPool keeps a single connection, so the in-memory database survives between sessions.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class FakeActivityLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log(
        self, event: str, *, user_id: int, team_id: int, details: dict[str, Any] | None = None
    ) -> None:
        self.events.append(
            {"event": event, "user_id": user_id, "team_id": team_id, "details": details or {}}
        )


class InMemorySummaryStore:
    """Stands in for the MongoDB summary store in tests."""

    def __init__(self) -> None:
        self.docs: dict[int, dict[str, Any]] = {}

    def get(self, tender_id: int) -> dict[str, Any] | None:
        return self.docs.get(tender_id)

    def get_many(self, tender_ids: list[int]) -> dict[int, dict[str, Any]]:
        return {i: self.docs[i] for i in tender_ids if i in self.docs}

    def try_start(self, tender_id: int, user_id: int, team_id: int) -> bool:
        if self.docs.get(tender_id, {}).get("status") == "processing":
            return False
        self.docs[tender_id] = {**self.docs.get(tender_id, {}), "status": "processing"}
        return True

    def save_ready(self, tender_id: int, result: dict[str, Any]) -> None:
        self.docs[tender_id] = {**result, "status": "ready", "error": None}

    def save_failed(self, tender_id: int, error: str) -> None:
        self.docs[tender_id] = {**self.docs.get(tender_id, {}), "status": "failed", "error": error}


class InMemoryMatchStore:
    """Stands in for the MongoDB match store in tests."""

    def __init__(self) -> None:
        self.docs: dict[tuple[int, int], dict[str, Any]] = {}

    def get(self, team_id: int, tender_id: int) -> dict[str, Any] | None:
        return self.docs.get((team_id, tender_id))

    def get_many(self, team_id: int, tender_ids: list[int]) -> dict[int, dict[str, Any]]:
        return {t: self.docs[(team_id, t)] for t in tender_ids if (team_id, t) in self.docs}

    def save(self, team_id: int, tender_id: int, result: dict[str, Any]) -> dict[str, Any]:
        doc = {**result, "team_id": team_id, "tender_id": tender_id, "checked_at": NOW}
        self.docs[(team_id, tender_id)] = doc
        return doc


class FakeLLM:
    """Returns a canned JSON response and records the prompts it received."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.response: dict[str, Any] = {
            "summary": "The municipality needs a contractor to maintain roads in Limpopo.",
            "objective": "Maintain municipal roads.",
            "scope": ["Pothole repairs", "Road marking"],
            "closing_date": "2026-11-11 10:00",
            "eligibility": ["CIDB 7CE or higher", "CSD registration"],
            "requirements": {
                "cidb": [
                    {"class_code": "ce", "min_grade": "7"},
                    {"class_code": "XX", "min_grade": 3},
                ],
                "bbbee_min_level": None,
                "min_years_experience": "5",
                "certifications": ["CSD Registration"],
                "provinces": ["limpopo", "Atlantis"],
                "compulsory_briefing": True,
            },
            "contract_duration": "36 months",
            "evaluation": "80/20",
            "estimated_value": "R 2,500,000",
            "other_highlights": ["Site visit required"],
        }

    def chat_json(self, system: str, user: str, max_tokens: int = 2000) -> LLMResponse:
        self.prompts.append(user)
        return LLMResponse(data=self.response, model="fake-model", total_tokens=123)


@pytest.fixture
def db() -> Iterator[Session]:
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def activity() -> FakeActivityLogger:
    return FakeActivityLogger()


@pytest.fixture
def summary_store() -> InMemorySummaryStore:
    return InMemorySummaryStore()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def match_store() -> InMemoryMatchStore:
    return InMemoryMatchStore()


@pytest.fixture
def client(
    db: Session,
    activity: FakeActivityLogger,
    summary_store: InMemorySummaryStore,
    llm: FakeLLM,
    match_store: InMemoryMatchStore,
) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_activity_logger] = lambda: activity
    app.dependency_overrides[get_summary_store] = lambda: summary_store
    app.dependency_overrides[require_llm] = lambda: llm
    app.dependency_overrides[get_match_store] = lambda: match_store
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(
    client: TestClient,
    email: str = "owner@acme.co.za",
    password: str = "supersecret123",
    company_name: str = "Acme Construction",
    plan: str = "pro",
) -> str:
    """Register a new team owner and return their access token.

    Teams start on the Free plan; tests default to Pro so plan limits only apply in the
    tests written for them.
    """
    response = client.post(
        "/api/auth/register",
        json={
            "company_name": company_name,
            "full_name": "Thandi Owner",
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    if plan != "free":
        upgrade = client.put("/api/team/plan", json={"plan": plan}, headers=auth_header(token))
        assert upgrade.status_code == 200, upgrade.text
    return token


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


NOW = datetime.now(UTC)
_next_id = iter(range(1, 10_000))


def add_tender(db: Session, **overrides: Any) -> Tender:
    etenders_id = next(_next_id)
    values: dict[str, Any] = {
        "ocid": f"ocds-test-{etenders_id}",
        "etenders_id": etenders_id,
        "tender_number": f"T{etenders_id}/2026",
        "title": "Supply of office furniture",
        "buyer_name": "Department of Public Works",
        "province": "Gauteng",
        "published_at": NOW - timedelta(days=5),
        "closing_at": NOW + timedelta(days=10),
        "documents": [],
        **overrides,
    }
    tender = Tender(**values)
    tender.document_count = len(tender.documents)
    tender.refresh_search_text()
    db.add(tender)
    db.commit()
    return tender
