from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.company_profile import CompanyProfileBase
from app.schemas.summary import TenderRequirements
from app.services.readiness import TenderFacts, score_readiness
from tests.conftest import (
    InMemoryMatchStore,
    InMemorySummaryStore,
    add_tender,
    auth_header,
    register,
)
from tests.test_company_profile import valid_profile

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def profile(**overrides: Any) -> CompanyProfileBase:
    """Acme: road construction, 5CE + 3GB, B-BBEE level 1, Gauteng & Limpopo, 8 years."""
    return CompanyProfileBase.model_validate(valid_profile(**overrides))


def facts(**requirements: Any) -> TenderFacts:
    extra = {
        k: requirements.pop(k) for k in list(requirements) if k in TenderFacts.__dataclass_fields__
    }
    return TenderFacts(
        requirements=TenderRequirements.model_validate(requirements),
        title=extra.pop("title", "Road construction and paving in Polokwane"),
        **extra,
    )


def checklist(result) -> dict[str, str]:
    return {item.key: item.status for item in result.checklist}


# --- Individual checks ----------------------------------------------------------


def test_cidb_met_when_grade_is_high_enough():
    result = score_readiness(facts(cidb=[{"class_code": "CE", "min_grade": 4}]), profile(), NOW)
    assert checklist(result)["cidb"] == "met"


def test_cidb_not_met_is_a_blocker():
    result = score_readiness(facts(cidb=[{"class_code": "CE", "min_grade": 7}]), profile(), NOW)

    cidb = next(i for i in result.checklist if i.key == "cidb")
    assert cidb.status == "not_met"
    assert cidb.label == "Has required CIDB grading (7CE)"
    assert "you have 5CE, 3GB" in cidb.detail
    assert result.verdict == "not_suitable"
    assert "CIDB" in result.recommendation


def test_cidb_check_skipped_when_not_required():
    assert "cidb" not in checklist(score_readiness(facts(), profile(), NOW))


@pytest.mark.parametrize(
    ("provinces", "expected"),
    [(["Limpopo"], "met"), (["Limpopo", "Free State"], "partial"), (["Western Cape"], "not_met")],
)
def test_province_coverage(provinces: list[str], expected: str):
    result = score_readiness(facts(provinces=provinces), profile(), NOW)
    assert checklist(result)["province"] == expected


def test_province_falls_back_to_tender_province():
    result = score_readiness(facts(province="Western Cape"), profile(), NOW)
    assert checklist(result)["province"] == "not_met"


def test_national_tenders_skip_province_check():
    assert "province" not in checklist(score_readiness(facts(province="National"), profile(), NOW))


def test_mandatory_bbbee_level():
    met = score_readiness(facts(bbbee_min_level=2), profile(bbbee_level=1), NOW)
    failed = score_readiness(facts(bbbee_min_level=2), profile(bbbee_level=4), NOW)

    assert checklist(met)["bbbee"] == "met"
    assert checklist(failed)["bbbee"] == "not_met"
    assert failed.verdict == "not_suitable"


def test_optional_bbbee_only_affects_preference_points():
    result = score_readiness(facts(), profile(bbbee_level=None), NOW)

    bbbee = next(i for i in result.checklist if i.key == "bbbee")
    assert bbbee.weight == 5
    assert bbbee.status == "not_met"
    assert not result.blockers


def test_experience():
    assert (
        checklist(score_readiness(facts(min_years_experience=5), profile(), NOW))["experience"]
        == "met"
    )
    assert (
        checklist(score_readiness(facts(min_years_experience=10), profile(), NOW))["experience"]
        == "not_met"
    )


def test_certifications_match_despite_different_wording():
    result = score_readiness(
        facts(
            certifications=["Central Supplier Database registration", "Tax clearance certificate"]
        ),
        profile(certifications=["CSD Registration", "SARS Tax Compliance Status"]),
        NOW,
    )
    assert checklist(result)["certifications"] == "met"


def test_missing_and_unrecognised_certifications():
    result = score_readiness(
        facts(certifications=["CSD", "PSIRA Registration", "Fire safety certificate"]),
        profile(certifications=["CSD Registration"]),
        NOW,
    )

    item = next(i for i in result.checklist if i.key == "certifications")
    assert item.status == "partial"
    assert item.detail == "Missing PSIRA Registration; confirm you have Fire safety certificate"


def test_generic_company_documents_are_not_flagged():
    result = score_readiness(
        facts(certifications=["Company Registration Certificate", "VAT Registration"]),
        profile(certifications=[]),
        NOW,
    )
    assert "certifications" not in checklist(result)


def test_services_match_tender_text():
    matched = score_readiness(facts(title="Road construction in Ward 5"), profile(), NOW)
    unrelated = score_readiness(
        facts(title="Supply of laboratory chemicals"),
        profile(industry_sector="Security Services", services=["Guarding"]),
        NOW,
    )
    assert checklist(matched)["services"] == "met"
    assert checklist(unrelated)["services"] == "not_met"


def test_missed_compulsory_briefing_is_a_blocker():
    past = score_readiness(
        facts(briefing_compulsory=True, briefing_at=NOW - timedelta(days=1)), profile(), NOW
    )
    upcoming = score_readiness(
        facts(briefing_compulsory=True, briefing_at=NOW + timedelta(days=3)), profile(), NOW
    )
    assert checklist(past)["briefing"] == "not_met"
    assert "briefing" in past.recommendation
    assert checklist(upcoming)["briefing"] == "met"


# --- Overall score and recommendation ---------------------------------------------


def test_perfect_match_scores_100_and_is_suitable():
    result = score_readiness(
        facts(
            cidb=[{"class_code": "CE", "min_grade": 5}],
            provinces=["Limpopo"],
            bbbee_min_level=2,
            min_years_experience=5,
            certifications=["CSD Registration"],
        ),
        profile(),
        NOW,
    )
    assert result.score == 100
    assert result.verdict == "suitable"
    assert result.recommendation.startswith("Suitable.")


def test_score_is_weighted_by_applicable_checks():
    # Applicable: province 20 (not met), bbbee 5 (met), services 10 (met) -> 15/35 = 43
    result = score_readiness(facts(provinces=["Western Cape"]), profile(), NOW)

    assert result.score == 43
    assert result.verdict == "not_suitable"
    assert not result.blockers  # low score, but no hard blocker


def test_partial_match_is_possibly_suitable():
    result = score_readiness(
        facts(provinces=["Limpopo", "Free State"], min_years_experience=10), profile(), NOW
    )
    # province 10/20, bbbee 5/5, experience 0/15, services 10/10 -> 25/50 = 50
    assert result.score == 50
    assert result.verdict == "possibly_suitable"


@pytest.mark.parametrize(
    ("requirements", "method", "expected"),
    [
        ({"cidb": [{"class_code": "CE", "min_grade": 8}]}, "Request for Bid", "low"),
        ({}, "Request for Quotation", "high"),
        ({"cidb": [{"class_code": "CE", "min_grade": 4}]}, "Request for Bid", "moderate"),
    ],
)
def test_competition_estimate(requirements: dict, method: str, expected: str):
    result = score_readiness(facts(procurement_method=method, **requirements), profile(), NOW)
    assert result.competition == expected


# --- API ------------------------------------------------------------------------


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = register(client)
    client.put("/api/company-profile", json=valid_profile(), headers=auth_header(token))
    return auth_header(token)


def ready_summary(store: InMemorySummaryStore, tender_id: int, **requirements: Any) -> None:
    store.docs[tender_id] = {
        "status": "ready",
        "updated_at": datetime.now(UTC) - timedelta(hours=1),
        "content": {"summary": "A tender", "scope": [], "requirements": requirements},
    }


def test_match_requires_a_summary(client: TestClient, db: Session, headers: dict[str, str]):
    tender = add_tender(db)

    response = client.post(f"/api/tenders/{tender.id}/match", headers=headers)

    assert response.status_code == 409
    assert "summary" in response.json()["detail"]


def test_match_tender_and_read_result(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    summary_store: InMemorySummaryStore,
):
    tender = add_tender(db, title="Road construction", province="Limpopo")
    ready_summary(summary_store, tender.id, cidb=[{"class_code": "CE", "min_grade": 4}])

    result = client.post(f"/api/tenders/{tender.id}/match", headers=headers).json()
    fetched = client.get(f"/api/tenders/{tender.id}/match", headers=headers).json()

    assert result["score"] == 100
    assert result["verdict"] == "suitable"
    assert result["checked_by"] == "Thandi Owner"
    assert result["outdated"] is False
    assert {i["key"] for i in result["checklist"]} == {"cidb", "province", "bbbee", "services"}
    assert fetched["score"] == 100


def test_unmatched_tender_returns_404(client: TestClient, db: Session, headers: dict[str, str]):
    tender = add_tender(db)
    assert client.get(f"/api/tenders/{tender.id}/match", headers=headers).status_code == 404


def test_results_are_per_team(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    summary_store: InMemorySummaryStore,
):
    tender = add_tender(db)
    ready_summary(summary_store, tender.id)
    client.post(f"/api/tenders/{tender.id}/match", headers=headers)
    other = auth_header(register(client, email="owner@other.co.za", company_name="Other"))

    assert client.get(f"/api/tenders/{tender.id}/match", headers=other).status_code == 404


def test_result_is_outdated_after_profile_change(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    summary_store: InMemorySummaryStore,
    match_store: InMemoryMatchStore,
):
    tender = add_tender(db)
    ready_summary(summary_store, tender.id)
    client.post(f"/api/tenders/{tender.id}/match", headers=headers)
    # Pretend the check happened before the profile was last updated.
    for doc in match_store.docs.values():
        doc["profile_updated_at"] = datetime(2020, 1, 1, tzinfo=UTC)

    fetched = client.get(f"/api/tenders/{tender.id}/match", headers=headers).json()

    assert fetched["outdated"] is True


def test_workspace_ranked_by_match_score(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    summary_store: InMemorySummaryStore,
):
    weak = add_tender(db, title="Laboratory chemicals", province="Western Cape")
    strong = add_tender(db, title="Road construction", province="Limpopo")
    unscored = add_tender(
        db, title="Office furniture", closing_at=datetime.now(UTC) + timedelta(days=1)
    )
    for tender in (weak, strong, unscored):
        client.post("/api/workspace", json={"tender_id": tender.id}, headers=headers)
    for tender in (weak, strong):
        ready_summary(summary_store, tender.id)
        client.post(f"/api/tenders/{tender.id}/match", headers=headers)

    items = client.get("/api/workspace", headers=headers).json()["items"]

    assert [i["tender"]["title"] for i in items] == [
        "Road construction",
        "Laboratory chemicals",
        "Office furniture",
    ]
    assert items[0]["match_score"] > items[1]["match_score"]
    assert items[2]["match_score"] is None


def test_broad_category_only_counts_as_same_sector():
    # The portal category mentions cleaning, but the tender itself is for security.
    result = score_readiness(
        facts(
            title="Integrated security services for ERWAT",
            category="Services: Functional (Including Cleaning and Security Services)",
        ),
        profile(industry_sector="Cleaning and Hygiene", services=["Office cleaning"]),
        NOW,
    )
    assert checklist(result)["services"] == "partial"


def test_briefing_time_shown_in_south_african_time():
    briefing = datetime(2026, 10, 14, 8, 30, tzinfo=UTC)  # 10:30 SAST
    result = score_readiness(facts(briefing_compulsory=True, briefing_at=briefing), profile(), NOW)

    assert (
        next(i for i in result.checklist if i.key == "briefing").detail
        == "It was on 14 Oct 2026 10:30"
    )


def test_briefing_conflict_between_portal_and_documents_is_not_a_blocker():
    result = score_readiness(
        facts(
            briefing_compulsory=True,  # portal says compulsory
            briefing_at=NOW - timedelta(days=5),
            compulsory_briefing=False,  # documents say optional
        ),
        profile(),
        NOW,
    )

    briefing = next(i for i in result.checklist if i.key == "briefing")
    assert briefing.status == "unknown"
    assert "Confirm with the buyer" in briefing.detail
    assert not result.blockers


def test_millisecond_rounding_does_not_mark_result_outdated(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    summary_store: InMemorySummaryStore,
    match_store: InMemoryMatchStore,
):
    tender = add_tender(db)
    ready_summary(summary_store, tender.id)
    client.post(f"/api/tenders/{tender.id}/match", headers=headers)
    # MongoDB keeps milliseconds only, so the stored copy is slightly earlier.
    for doc in match_store.docs.values():
        stored = doc["profile_updated_at"]
        doc["profile_updated_at"] = stored.replace(microsecond=stored.microsecond // 1000 * 1000)
        doc["profile_updated_at"] -= timedelta(microseconds=999)

    fetched = client.get(f"/api/tenders/{tender.id}/match", headers=headers).json()

    assert fetched["outdated"] is False
