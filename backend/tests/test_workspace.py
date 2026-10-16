from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import NOW, FakeActivityLogger, add_tender, auth_header, register


@pytest.fixture
def owner(client: TestClient) -> dict[str, str]:
    return auth_header(register(client))


@pytest.fixture
def member(client: TestClient, owner: dict[str, str]) -> dict[str, str]:
    client.post(
        "/api/team/members",
        json={"full_name": "Sipho Member", "email": "sipho@acme.co.za", "password": "memberpass1"},
        headers=owner,
    )
    token = client.post(
        "/api/auth/login", data={"username": "sipho@acme.co.za", "password": "memberpass1"}
    ).json()["access_token"]
    return auth_header(token)


def save(client: TestClient, headers: dict[str, str], tender_id: int) -> dict[str, Any]:
    response = client.post("/api/workspace", json={"tender_id": tender_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def member_id(client: TestClient, headers: dict[str, str]) -> int:
    return client.get("/api/auth/me", headers=headers).json()["id"]


# --- Saving and listing ---------------------------------------------------------


def test_save_tender_to_workspace(
    client: TestClient, db: Session, owner: dict[str, str], activity: FakeActivityLogger
):
    tender = add_tender(db, title="Road maintenance")

    entry = save(client, owner, tender.id)

    assert entry["status"] == "pending"
    assert entry["tender"]["title"] == "Road maintenance"
    assert entry["saved_by"]["full_name"] == "Thandi Owner"
    assert [c["to_status"] for c in entry["status_changes"]] == ["pending"]
    assert entry["ai_summary"] is None and entry["match_score"] is None
    assert activity.events[-1]["event"] == "workspace.tender_saved"


def test_cannot_save_same_tender_twice(client: TestClient, db: Session, owner: dict[str, str]):
    tender = add_tender(db)
    save(client, owner, tender.id)

    response = client.post("/api/workspace", json={"tender_id": tender.id}, headers=owner)

    assert response.status_code == 409


def test_saving_unknown_tender_returns_404(client: TestClient, owner: dict[str, str]):
    response = client.post("/api/workspace", json={"tender_id": 999999}, headers=owner)
    assert response.status_code == 404


def test_team_members_see_the_same_workspace(
    client: TestClient, db: Session, owner: dict[str, str], member: dict[str, str]
):
    tender = add_tender(db)
    save(client, owner, tender.id)

    items = client.get("/api/workspace", headers=member).json()["items"]

    assert [i["tender"]["id"] for i in items] == [tender.id]


def test_other_teams_cannot_see_or_change_entries(
    client: TestClient, db: Session, owner: dict[str, str]
):
    entry = save(client, owner, add_tender(db).id)
    other = auth_header(register(client, email="owner@other.co.za", company_name="Other Co"))

    assert client.get("/api/workspace", headers=other).json()["items"] == []
    assert client.get(f"/api/workspace/{entry['id']}", headers=other).status_code == 404
    patch = client.patch(
        f"/api/workspace/{entry['id']}", json={"status": "submitted"}, headers=other
    )
    assert patch.status_code == 404


def test_workspace_sorted_by_nearest_deadline(
    client: TestClient, db: Session, owner: dict[str, str]
):
    later = add_tender(db, title="Later", closing_at=NOW + timedelta(days=20))
    sooner = add_tender(db, title="Sooner", closing_at=NOW + timedelta(days=2))
    save(client, owner, later.id)
    save(client, owner, sooner.id)

    items = client.get("/api/workspace", headers=owner).json()["items"]

    assert [i["tender"]["title"] for i in items] == ["Sooner", "Later"]


def test_saved_tender_ids(client: TestClient, db: Session, owner: dict[str, str]):
    tender = add_tender(db)
    entry = save(client, owner, tender.id)

    saved = client.get("/api/workspace/saved", headers=owner).json()

    assert saved == [{"tender_id": tender.id, "entry_id": entry["id"], "status": "pending"}]


def test_remove_from_workspace(client: TestClient, db: Session, owner: dict[str, str]):
    entry = save(client, owner, add_tender(db).id)

    response = client.delete(f"/api/workspace/{entry['id']}", headers=owner)

    assert response.status_code == 204
    assert client.get("/api/workspace", headers=owner).json()["items"] == []


# --- Status -------------------------------------------------------------------


def test_status_change_records_who_changed_it(
    client: TestClient, db: Session, owner: dict[str, str], member: dict[str, str]
):
    entry = save(client, owner, add_tender(db).id)

    client.patch(f"/api/workspace/{entry['id']}", json={"status": "interested"}, headers=member)
    updated = client.patch(
        f"/api/workspace/{entry['id']}", json={"status": "submitted"}, headers=owner
    ).json()

    assert updated["status"] == "submitted"
    assert updated["status_changed_by"]["full_name"] == "Thandi Owner"
    history = [
        (c["from_status"], c["to_status"], c["changed_by"]["full_name"])
        for c in updated["status_changes"]
    ]
    assert history == [
        ("interested", "submitted", "Thandi Owner"),
        ("pending", "interested", "Sipho Member"),
        (None, "pending", "Thandi Owner"),
    ]


def test_status_filter_and_counts(client: TestClient, db: Session, owner: dict[str, str]):
    first = save(client, owner, add_tender(db).id)
    save(client, owner, add_tender(db).id)
    client.patch(f"/api/workspace/{first['id']}", json={"status": "not_eligible"}, headers=owner)

    body = client.get("/api/workspace", params={"status": "not_eligible"}, headers=owner).json()

    assert [i["id"] for i in body["items"]] == [first["id"]]
    assert body["status_counts"]["not_eligible"] == 1
    assert body["status_counts"]["pending"] == 1
    assert body["status_counts"]["submitted"] == 0


def test_invalid_status_is_rejected(client: TestClient, db: Session, owner: dict[str, str]):
    entry = save(client, owner, add_tender(db).id)

    response = client.patch(
        f"/api/workspace/{entry['id']}", json={"status": "won-the-lotto"}, headers=owner
    )

    assert response.status_code == 422


# --- Notes --------------------------------------------------------------------


def test_notes_lifecycle(
    client: TestClient, db: Session, owner: dict[str, str], member: dict[str, str]
):
    entry = save(client, owner, add_tender(db).id)
    url = f"/api/workspace/{entry['id']}/notes"

    note = client.post(url, json={"body": "  Check the CIDB requirement  "}, headers=member).json()
    assert note["body"] == "Check the CIDB requirement"
    assert note["author"]["full_name"] == "Sipho Member"

    # Only the author can edit; the owner can delete anyone's note.
    edit_by_owner = client.patch(f"{url}/{note['id']}", json={"body": "x"}, headers=owner)
    edit_by_author = client.patch(f"{url}/{note['id']}", json={"body": "Done"}, headers=member)
    assert edit_by_owner.status_code == 403
    assert edit_by_author.json()["body"] == "Done"

    detail = client.get(f"/api/workspace/{entry['id']}", headers=owner).json()
    assert detail["note_count"] == 1

    assert client.delete(f"{url}/{note['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/workspace/{entry['id']}", headers=owner).json()["notes"] == []


def test_empty_note_is_rejected(client: TestClient, db: Session, owner: dict[str, str]):
    entry = save(client, owner, add_tender(db).id)

    response = client.post(
        f"/api/workspace/{entry['id']}/notes", json={"body": "   "}, headers=owner
    )

    assert response.status_code == 422


# --- Tasks --------------------------------------------------------------------


def test_tasks_lifecycle(
    client: TestClient, db: Session, owner: dict[str, str], member: dict[str, str]
):
    entry = save(client, owner, add_tender(db).id)
    url = f"/api/workspace/{entry['id']}/tasks"
    sipho_id = member_id(client, member)

    task = client.post(
        url,
        json={"title": "Get tax clearance", "assignee_id": sipho_id, "due_date": "2026-11-01"},
        headers=owner,
    ).json()
    assert task["assignee"]["full_name"] == "Sipho Member"
    assert task["is_done"] is False

    my_tasks = client.get("/api/workspace/my-tasks", headers=member).json()
    assert [t["title"] for t in my_tasks] == ["Get tax clearance"]
    assert my_tasks[0]["tender_title"] == "Supply of office furniture"

    done = client.patch(f"{url}/{task['id']}", json={"is_done": True}, headers=member).json()
    assert done["is_done"] is True and done["completed_at"] is not None
    assert client.get("/api/workspace/my-tasks", headers=member).json() == []

    unassigned = client.patch(f"{url}/{task['id']}", json={"assignee_id": None}, headers=owner)
    assert unassigned.json()["assignee"] is None
    assert unassigned.json()["title"] == "Get tax clearance"  # untouched fields stay the same

    assert client.delete(f"{url}/{task['id']}", headers=owner).status_code == 204


def test_open_task_count_in_list(client: TestClient, db: Session, owner: dict[str, str]):
    entry = save(client, owner, add_tender(db).id)
    url = f"/api/workspace/{entry['id']}/tasks"
    first = client.post(url, json={"title": "One"}, headers=owner).json()
    client.post(url, json={"title": "Two"}, headers=owner)
    client.patch(f"{url}/{first['id']}", json={"is_done": True}, headers=owner)
    client.post(f"/api/workspace/{entry['id']}/notes", json={"body": "Hi"}, headers=owner)

    item = client.get("/api/workspace", headers=owner).json()["items"][0]

    assert item["open_task_count"] == 1
    assert item["note_count"] == 1


def test_cannot_assign_task_to_another_team(client: TestClient, db: Session, owner: dict[str, str]):
    entry = save(client, owner, add_tender(db).id)
    outsider = auth_header(register(client, email="owner@other.co.za", company_name="Other"))
    outsider_id = member_id(client, outsider)

    response = client.post(
        f"/api/workspace/{entry['id']}/tasks",
        json={"title": "Sneaky", "assignee_id": outsider_id},
        headers=owner,
    )

    assert response.status_code == 422
