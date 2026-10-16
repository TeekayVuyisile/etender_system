from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import FakeActivityLogger, auth_header, register


def valid_profile(**overrides: Any) -> dict[str, Any]:
    profile = {
        "industry_sector": "Construction and Civil Works",
        "services": ["Road construction", "Paving", "Stormwater drainage"],
        "cidb_gradings": [{"class_code": "CE", "grade": 5}, {"class_code": "GB", "grade": 3}],
        "bbbee_level": 1,
        "certifications": ["CSD Registration", "SARS Tax Compliance Status"],
        "provinces": ["Gauteng", "Limpopo"],
        "years_of_experience": 8,
        "contact_name": "Thandi Owner",
        "contact_email": "tenders@acme.co.za",
        "contact_phone": "+27 11 555 0100",
        "website": "https://acme.co.za",
        "physical_address": "12 Main Road, Johannesburg",
    }
    return {**profile, **overrides}


def add_member_and_login(client: TestClient, owner_token: str) -> str:
    client.post(
        "/api/team/members",
        json={"full_name": "Sipho Member", "email": "sipho@acme.co.za", "password": "memberpass1"},
        headers=auth_header(owner_token),
    )
    response = client.post(
        "/api/auth/login", data={"username": "sipho@acme.co.za", "password": "memberpass1"}
    )
    return response.json()["access_token"]


def test_profile_is_missing_for_new_team(client: TestClient):
    token = register(client)

    response = client.get("/api/company-profile", headers=auth_header(token))

    assert response.status_code == 404


def test_owner_can_create_profile(client: TestClient, activity: FakeActivityLogger):
    token = register(client)

    response = client.put("/api/company-profile", json=valid_profile(), headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["industry_sector"] == "Construction and Civil Works"
    assert body["cidb_gradings"] == [
        {"class_code": "CE", "grade": 5},
        {"class_code": "GB", "grade": 3},
    ]
    assert client.get("/api/company-profile", headers=auth_header(token)).json() == body
    assert activity.events[-1]["event"] == "company_profile.created"


def test_owner_can_update_profile(client: TestClient, activity: FakeActivityLogger):
    token = register(client)
    first = client.put("/api/company-profile", json=valid_profile(), headers=auth_header(token))

    response = client.put(
        "/api/company-profile",
        json=valid_profile(provinces=["Western Cape"], bbbee_level=None),
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == first.json()["id"]
    assert response.json()["provinces"] == ["Western Cape"]
    assert response.json()["bbbee_level"] is None
    assert activity.events[-1]["event"] == "company_profile.updated"


def test_member_can_view_but_not_edit_profile(client: TestClient):
    owner_token = register(client)
    client.put("/api/company-profile", json=valid_profile(), headers=auth_header(owner_token))
    member_token = add_member_and_login(client, owner_token)

    view = client.get("/api/company-profile", headers=auth_header(member_token))
    edit = client.put(
        "/api/company-profile", json=valid_profile(), headers=auth_header(member_token)
    )

    assert view.status_code == 200
    assert edit.status_code == 403


def test_teams_only_see_their_own_profile(client: TestClient):
    acme = register(client, email="owner@acme.co.za", company_name="Acme")
    other = register(client, email="owner@other.co.za", company_name="Other Co")
    client.put("/api/company-profile", json=valid_profile(), headers=auth_header(acme))

    response = client.get("/api/company-profile", headers=auth_header(other))

    assert response.status_code == 404


def test_duplicate_tags_and_provinces_are_removed(client: TestClient):
    token = register(client)

    response = client.put(
        "/api/company-profile",
        json=valid_profile(
            services=["Paving", "paving ", "Road construction"],
            provinces=["Gauteng", "Gauteng"],
            website="   ",
        ),
        headers=auth_header(token),
    )

    body = response.json()
    assert body["services"] == ["Paving", "Road construction"]
    assert body["provinces"] == ["Gauteng"]
    assert body["website"] is None


def test_profile_validation_errors(client: TestClient):
    token = register(client)
    invalid_profiles = [
        valid_profile(provinces=["Atlantis"]),
        valid_profile(provinces=[]),
        valid_profile(industry_sector="Space Tourism"),
        valid_profile(services=[]),
        valid_profile(cidb_gradings=[{"class_code": "CE", "grade": 10}]),
        valid_profile(cidb_gradings=[{"class_code": "XX", "grade": 3}]),
        valid_profile(
            cidb_gradings=[{"class_code": "CE", "grade": 3}, {"class_code": "CE", "grade": 5}]
        ),
        valid_profile(bbbee_level=9),
        valid_profile(years_of_experience=-1),
        valid_profile(contact_phone="call me maybe"),
        valid_profile(contact_email="not-an-email"),
    ]

    for profile in invalid_profiles:
        response = client.put("/api/company-profile", json=profile, headers=auth_header(token))
        assert response.status_code == 422, profile


def test_profile_options_are_public(client: TestClient):
    response = client.get("/api/company-profile/options")

    assert response.status_code == 200
    body = response.json()
    assert len(body["provinces"]) == 9
    assert {"value": "CE", "label": "CE: Civil Engineering"} in body["cidb_classes"]
    assert body["bbbee_levels"] == [1, 2, 3, 4, 5, 6, 7, 8]
