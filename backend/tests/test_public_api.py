from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.api_keys import RateLimiter, hash_key
from app.services.summarizer import limit_words
from tests.conftest import (
    NOW,
    FakeLLM,
    InMemoryCache,
    InMemorySummaryStore,
    add_tender,
    auth_header,
    register,
)
from tests.test_company_profile import valid_profile
from tests.test_summaries import REQUIREMENTS_TEXT, make_docx, make_pdf


def create_key(client: TestClient, owner: dict[str, str], name: str = "Integration") -> str:
    response = client.post("/api/team/api-keys", json={"name": name}, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()["key"]


@pytest.fixture
def owner(client: TestClient) -> dict[str, str]:
    headers = auth_header(register(client, plan="pro"))
    client.put("/api/company-profile", json=valid_profile(), headers=headers)
    return headers


@pytest.fixture
def api(client: TestClient, owner: dict[str, str]) -> dict[str, str]:
    return {"X-API-Key": create_key(client, owner)}


def ready_summary(store: InMemorySummaryStore, tender_id: int, **requirements: Any) -> None:
    store.docs[tender_id] = {
        "status": "ready",
        "updated_at": NOW,
        "content": {
            "summary": "Road maintenance in Limpopo.",
            "scope": ["Road maintenance"],
            "eligibility": ["CIDB 4CE"],
            "requirements": requirements,
        },
    }


# --- API keys ---------------------------------------------------------------------


def test_create_list_and_revoke_api_key(client: TestClient, db: Session, owner: dict[str, str]):
    created = client.post("/api/team/api-keys", json={"name": "Civic app"}, headers=owner).json()

    assert created["key"].startswith("tih_")
    assert created["prefix"] == created["key"][:12]
    listed = client.get("/api/team/api-keys", headers=owner).json()
    assert [k["name"] for k in listed] == ["Civic app"]
    assert "key" not in listed[0]  # never shown again

    # Only the hash is stored.
    from app.models import ApiKey

    stored = db.query(ApiKey).one()
    assert stored.key_hash == hash_key(created["key"])
    assert created["key"] not in (stored.key_hash, stored.prefix)

    assert client.delete(f"/api/team/api-keys/{created['id']}", headers=owner).status_code == 204
    assert client.get("/api/team/api-keys", headers=owner).json() == []
    revoked = client.get("/api/enriched-releases", headers={"X-API-Key": created["key"]})
    assert revoked.status_code == 401


def test_members_cannot_manage_api_keys(client: TestClient, owner: dict[str, str]):
    client.post(
        "/api/team/members",
        json={"full_name": "Sipho Member", "email": "sipho@acme.co.za", "password": "memberpass1"},
        headers=owner,
    )
    token = client.post(
        "/api/auth/login", data={"username": "sipho@acme.co.za", "password": "memberpass1"}
    ).json()["access_token"]

    response = client.post("/api/team/api-keys", json={"name": "x"}, headers=auth_header(token))

    assert response.status_code == 403


def test_public_api_requires_credentials(client: TestClient):
    response = client.get("/api/enriched-releases")

    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


def test_invalid_api_key_is_rejected(client: TestClient):
    response = client.get("/api/enriched-releases", headers={"X-API-Key": "tih_not-a-real-key"})
    assert response.status_code == 401


def test_bearer_token_also_works(client: TestClient, db: Session, owner: dict[str, str]):
    add_tender(db)
    assert client.get("/api/enriched-releases", headers=owner).status_code == 200


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter(limit=2, window_seconds=60)
    limiter.check(1)
    limiter.check(1)
    with pytest.raises(Exception) as error:
        limiter.check(1)
    assert error.value.status_code == 429
    limiter.check(2)  # other keys are unaffected


# --- GET /api/enriched-releases -------------------------------------------------------


def test_enriched_releases_include_summary_and_live_suitability(
    client: TestClient, db: Session, api: dict[str, str], summary_store: InMemorySummaryStore
):
    summarised = add_tender(db, title="Road maintenance", province="Limpopo")
    plain = add_tender(db, title="Road signage", province="Limpopo")
    ready_summary(summary_store, summarised.id, cidb=[{"class_code": "CE", "min_grade": 4}])

    body = client.get("/api/enriched-releases", params={"q": "road"}, headers=api).json()

    releases = {r["id"]: r for r in body["releases"]}
    assert body["total"] == 2
    assert body["includes_ai_summaries"] and body["includes_suitability"]
    assert releases[summarised.id]["ai_summary"]["summary"] == "Road maintenance in Limpopo."
    assert releases[summarised.id]["suitability"]["score"] == 100  # 5CE profile vs 4CE needed
    assert releases[summarised.id]["ocid"].startswith("ocds-")
    assert releases[plain.id]["ai_summary"] is None
    assert releases[plain.id]["suitability"] is None


def test_enriched_releases_on_free_plan_omit_ai_fields(
    client: TestClient, db: Session, summary_store: InMemorySummaryStore
):
    owner = auth_header(register(client, plan="free"))
    key = create_key(client, owner)
    tender = add_tender(db)
    ready_summary(summary_store, tender.id)

    body = client.get("/api/enriched-releases", headers={"X-API-Key": key}).json()

    assert body["includes_ai_summaries"] is False
    assert body["releases"][0]["ai_summary"] is None
    assert body["releases"][0]["suitability"] is None


def test_enriched_releases_count_towards_free_search_limit(client: TestClient, db: Session):
    owner = auth_header(register(client, plan="free"))
    key = {"X-API-Key": create_key(client, owner)}
    add_tender(db)

    for q in ("a", "b", "c"):
        assert client.get("/api/enriched-releases", params={"q": q}, headers=key).status_code == 200
    blocked = client.get("/api/enriched-releases", params={"q": "d"}, headers=key)

    assert blocked.status_code == 403


# --- GET /api/analytics/spend-by-buyer -----------------------------------------------


def test_spend_by_buyer_aggregates_and_caches(
    client: TestClient, db: Session, api: dict[str, str], analytics_cache: InMemoryCache
):
    add_tender(
        db, buyer_name="ESKOM", estimated_value=1_000_000, province="Gauteng", category="Energy"
    )
    add_tender(
        db, buyer_name="ESKOM", estimated_value=None, province="Mpumalanga", category="Energy"
    )
    add_tender(
        db,
        buyer_name="ESKOM",
        estimated_value=500_000,
        province="Gauteng",
        closing_at=NOW - timedelta(days=1),
    )
    add_tender(db, buyer_name="City of Cape Town", province="Western Cape")
    add_tender(db, buyer_name="Old Buyer", published_at=NOW - timedelta(days=400))

    body = client.get("/api/analytics/spend-by-buyer", headers=api).json()

    assert body["cached"] is False
    assert body["total_tenders"] == 4  # older than 90 days excluded
    eskom = body["buyers"][0]
    assert eskom["buyer"] == "ESKOM"
    assert eskom["tenders_advertised"] == 3
    assert eskom["open_tenders"] == 2
    assert eskom["known_value_total"] == 1_500_000
    assert eskom["value_coverage"] == pytest.approx(0.667, abs=0.001)
    assert eskom["top_provinces"][0] == {"name": "Gauteng", "tenders": 2}
    assert "Award values are not published" in body["note"]

    again = client.get("/api/analytics/spend-by-buyer", headers=api).json()
    assert again["cached"] is True
    assert len(analytics_cache.docs) == 1


def test_spend_by_buyer_province_filter(client: TestClient, db: Session, api: dict[str, str]):
    add_tender(db, buyer_name="ESKOM", province="Gauteng")
    add_tender(db, buyer_name="City of Cape Town", province="Western Cape")

    body = client.get(
        "/api/analytics/spend-by-buyer", params={"province": "Western Cape"}, headers=api
    ).json()

    assert [b["buyer"] for b in body["buyers"]] == ["City of Cape Town"]


# --- POST /api/summary/extract -----------------------------------------------------------


def test_extract_summary_from_pdf(client: TestClient, api: dict[str, str], llm: FakeLLM):
    llm.response = {"summary": "A short summary of the tender."}

    response = client.post(
        "/api/summary/extract",
        files={"file": ("bid.pdf", make_pdf(REQUIREMENTS_TEXT, pages=2), "application/pdf")},
        headers=api,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "filename": "bid.pdf",
        "pages": 2,
        "summary": "A short summary of the tender.",
        "word_count": 6,
        "truncated_input": False,
        "model": "fake-model",
    }
    assert "CIDB grading of 7CE" in llm.prompts[0]


def test_extract_summary_from_docx(client: TestClient, api: dict[str, str], llm: FakeLLM):
    llm.response = {"summary": "Docx summary."}
    docx_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    response = client.post(
        "/api/summary/extract",
        files={"file": ("spec.docx", make_docx(REQUIREMENTS_TEXT), docx_type)},
        headers=api,
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "Docx summary."


def test_extract_rejects_other_file_types(client: TestClient, api: dict[str, str]):
    response = client.post(
        "/api/summary/extract",
        files={"file": ("prices.xlsx", b"x", "application/vnd.ms-excel")},
        headers=api,
    )
    assert response.status_code == 415


def test_extract_reports_scanned_documents(client: TestClient, api: dict[str, str]):
    response = client.post(
        "/api/summary/extract",
        files={"file": ("scan.pdf", make_pdf("", pages=2), "application/pdf")},
        headers=api,
    )
    assert response.status_code == 422
    assert "scanned" in response.json()["detail"]


def test_extract_requires_basic_plan(client: TestClient):
    owner = auth_header(register(client, plan="free"))
    key = create_key(client, owner)

    response = client.post(
        "/api/summary/extract",
        files={"file": ("bid.pdf", make_pdf(REQUIREMENTS_TEXT), "application/pdf")},
        headers={"X-API-Key": key},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["required_plan"] == "basic"


@pytest.mark.parametrize(
    ("words", "expected_max"),
    [(100, 100), (128, 128), (200, 121)],
)
def test_summaries_are_kept_near_120_words(words: int, expected_max: int):
    text = " ".join(["word"] * (words - 1)) + "."
    assert len(limit_words(text).split()) <= expected_max


def test_long_summaries_cut_at_a_sentence_end():
    sentences = "This tender is for road maintenance in several districts. " * 30
    result = limit_words(sentences)
    assert result.endswith("districts.")
    assert len(result.split()) <= 120


# --- POST /api/readiness/check ----------------------------------------------------------


def test_readiness_check_with_supplied_profile(
    client: TestClient, db: Session, api: dict[str, str], summary_store: InMemorySummaryStore
):
    tender = add_tender(db, title="Road maintenance", province="Limpopo")
    ready_summary(summary_store, tender.id, cidb=[{"class_code": "CE", "min_grade": 7}])
    profile = {
        "industry_sector": "Construction and Civil Works",
        "services": ["Road maintenance"],
        "cidb_gradings": [{"class_code": "CE", "grade": 8}],
        "provinces": ["Limpopo"],
        "years_of_experience": 10,
        "bbbee_level": 1,
    }

    body = client.post(
        "/api/readiness/check",
        json={"tender_id": tender.id, "company_profile": profile},
        headers=api,
    ).json()

    assert body["tender_id"] == tender.id
    assert body["profile_source"] == "request"
    assert body["score"] == 100
    assert body["verdict"] == "suitable"
    assert {i["key"] for i in body["checklist"]} >= {"cidb", "province"}


def test_readiness_check_defaults_to_team_profile(
    client: TestClient, db: Session, api: dict[str, str], summary_store: InMemorySummaryStore
):
    tender = add_tender(db)
    ready_summary(summary_store, tender.id, cidb=[{"class_code": "CE", "min_grade": 7}])

    body = client.post("/api/readiness/check", json={"tender_id": tender.id}, headers=api).json()

    assert body["profile_source"] == "team_profile"
    assert body["verdict"] == "not_suitable"  # team profile has 5CE
    assert "CIDB" in body["recommendation"]


def test_readiness_check_needs_a_summary(client: TestClient, db: Session, api: dict[str, str]):
    tender = add_tender(db)
    response = client.post("/api/readiness/check", json={"tender_id": tender.id}, headers=api)
    assert response.status_code == 409


def test_readiness_check_validates_profile(client: TestClient, db: Session, api: dict[str, str]):
    response = client.post(
        "/api/readiness/check",
        json={"tender_id": 1, "company_profile": {"industry_sector": "Space", "provinces": []}},
        headers=api,
    )
    assert response.status_code == 422


def test_public_endpoints_are_documented_in_openapi(client: TestClient):
    schema = client.get("/openapi.json").json()

    for path in (
        "/api/enriched-releases",
        "/api/analytics/spend-by-buyer",
        "/api/summary/extract",
        "/api/readiness/check",
    ):
        assert path in schema["paths"], path
    assert "APIKeyHeader" in schema["components"]["securitySchemes"]


def test_api_key_last_used_is_recorded(client: TestClient, db: Session, api: dict[str, str]):
    from app.models import ApiKey

    add_tender(db)
    client.get("/api/enriched-releases", headers=api)

    db.expire_all()
    last_used = db.query(ApiKey).one().last_used_at
    assert last_used is not None
    assert abs(last_used.replace(tzinfo=UTC) - datetime.now(UTC)) < timedelta(minutes=1)
