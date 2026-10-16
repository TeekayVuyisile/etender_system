from fastapi.testclient import TestClient

from tests.conftest import auth_header, register

NEW_MEMBER = {"full_name": "Sipho Member", "email": "sipho@acme.co.za", "password": "memberpass123"}


def test_owner_can_add_member(client: TestClient):
    owner_token = register(client)

    response = client.post("/api/team/members", json=NEW_MEMBER, headers=auth_header(owner_token))

    assert response.status_code == 201
    assert response.json()["role"] == "member"

    members = client.get("/api/team/members", headers=auth_header(owner_token)).json()
    assert [m["email"] for m in members] == ["owner@acme.co.za", "sipho@acme.co.za"]


def test_added_member_can_log_in_and_sees_same_team(client: TestClient):
    owner_token = register(client)
    client.post("/api/team/members", json=NEW_MEMBER, headers=auth_header(owner_token))

    login = client.post(
        "/api/auth/login", data={"username": NEW_MEMBER["email"], "password": "memberpass123"}
    )
    member_token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(member_token)).json()

    assert me["team"]["name"] == "Acme Construction"


def test_member_cannot_add_members(client: TestClient):
    owner_token = register(client)
    client.post("/api/team/members", json=NEW_MEMBER, headers=auth_header(owner_token))
    member_token = client.post(
        "/api/auth/login", data={"username": NEW_MEMBER["email"], "password": "memberpass123"}
    ).json()["access_token"]

    response = client.post(
        "/api/team/members",
        json={"full_name": "Another Person", "email": "x@acme.co.za", "password": "password123"},
        headers=auth_header(member_token),
    )

    assert response.status_code == 403


def test_teams_cannot_see_each_others_members(client: TestClient):
    acme_token = register(client, email="owner@acme.co.za", company_name="Acme")
    other_token = register(client, email="owner@other.co.za", company_name="Other Co")

    acme_members = client.get("/api/team/members", headers=auth_header(acme_token)).json()
    other_members = client.get("/api/team/members", headers=auth_header(other_token)).json()

    assert [m["email"] for m in acme_members] == ["owner@acme.co.za"]
    assert [m["email"] for m in other_members] == ["owner@other.co.za"]
