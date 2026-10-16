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

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tender  # noqa: E402
from app.services.activity import get_activity_logger  # noqa: E402

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
def client(db: Session, activity: FakeActivityLogger) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_activity_logger] = lambda: activity
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(
    client: TestClient,
    email: str = "owner@acme.co.za",
    password: str = "supersecret123",
    company_name: str = "Acme Construction",
) -> str:
    """Register a new team owner and return their access token."""
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
    return response.json()["access_token"]


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
