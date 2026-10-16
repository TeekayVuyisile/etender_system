from fastapi.testclient import TestClient

from tests.conftest import FakeActivityLogger, auth_header, register


def test_register_creates_team_owner(client: TestClient, activity: FakeActivityLogger):
    token = register(client)

    response = client.get("/api/auth/me", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@acme.co.za"
    assert body["role"] == "owner"
    assert body["team"]["name"] == "Acme Construction"
    assert body["team"]["plan"] == "free"
    assert "hashed_password" not in body
    assert activity.events[0]["event"] == "user.registered"


def test_register_rejects_duplicate_email_case_insensitively(client: TestClient):
    register(client, email="owner@acme.co.za")

    response = client.post(
        "/api/auth/register",
        json={
            "company_name": "Other Co",
            "full_name": "Someone Else",
            "email": "OWNER@acme.co.za",
            "password": "anotherpassword",
        },
    )

    assert response.status_code == 409


def test_register_validates_input(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={"company_name": "A", "full_name": "B", "email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422


def test_login_with_correct_credentials(client: TestClient, activity: FakeActivityLogger):
    register(client, email="owner@acme.co.za", password="supersecret123")

    response = client.post(
        "/api/auth/login", data={"username": "owner@acme.co.za", "password": "supersecret123"}
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert activity.events[-1]["event"] == "user.login"


def test_login_with_wrong_password(client: TestClient):
    register(client, email="owner@acme.co.za", password="supersecret123")

    response = client.post(
        "/api/auth/login", data={"username": "owner@acme.co.za", "password": "wrongpassword"}
    )

    assert response.status_code == 401


def test_login_with_unknown_email(client: TestClient):
    response = client.post(
        "/api/auth/login", data={"username": "nobody@acme.co.za", "password": "whatever123"}
    )

    assert response.status_code == 401


def test_me_requires_token(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_invalid_token(client: TestClient):
    response = client.get("/api/auth/me", headers=auth_header("not-a-real-token"))

    assert response.status_code == 401
