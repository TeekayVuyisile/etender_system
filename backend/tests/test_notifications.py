from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.notification_events import due_reminders, run_reminders
from app.services.notifications import InAppChannel, Notification, Notifier
from tests.conftest import (
    InMemoryNotificationStore,
    TestingSessionLocal,
    add_tender,
    auth_header,
    register,
)
from tests.test_summaries import DOC_URL, REQUIREMENTS_TEXT, make_pdf


@pytest.fixture
def team(client: TestClient) -> dict[str, Any]:
    """An owner (Thandi) and a member (Sipho), each with headers and user ID."""
    owner = auth_header(register(client))
    client.post(
        "/api/team/members",
        json={"full_name": "Sipho Member", "email": "sipho@acme.co.za", "password": "memberpass1"},
        headers=owner,
    )
    member = auth_header(
        client.post(
            "/api/auth/login", data={"username": "sipho@acme.co.za", "password": "memberpass1"}
        ).json()["access_token"]
    )
    me = lambda h: client.get("/api/auth/me", headers=h).json()["id"]  # noqa: E731
    return {"owner": owner, "member": member, "owner_id": me(owner), "member_id": me(member)}


def notifications(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    return client.get("/api/notifications", headers=headers).json()


def save(client: TestClient, headers: dict[str, str], tender_id: int) -> int:
    return client.post("/api/workspace", json={"tender_id": tender_id}, headers=headers).json()[
        "id"
    ]


# --- Events -----------------------------------------------------------------------------


def test_assigning_a_task_notifies_the_assignee(
    client: TestClient, db: Session, team: dict[str, Any]
):
    entry_id = save(client, team["owner"], add_tender(db, title="Road maintenance").id)

    client.post(
        f"/api/workspace/{entry_id}/tasks",
        json={"title": "Get tax clearance", "assignee_id": team["member_id"]},
        headers=team["owner"],
    )

    member = notifications(client, team["member"])
    assert member["unread_count"] == 1
    [item] = member["items"]
    assert item["type"] == "task_assigned"
    assert item["title"] == "Thandi Owner assigned you a task: Get tax clearance"
    assert item["body"] == "Road maintenance"
    assert item["link"] == f"/workspace/{entry_id}"
    assert notifications(client, team["owner"])["unread_count"] == 0


def test_assigning_yourself_a_task_sends_nothing(
    client: TestClient, db: Session, team: dict[str, Any]
):
    entry_id = save(client, team["owner"], add_tender(db).id)

    client.post(
        f"/api/workspace/{entry_id}/tasks",
        json={"title": "Read the bid", "assignee_id": team["owner_id"]},
        headers=team["owner"],
    )

    assert notifications(client, team["owner"])["unread_count"] == 0


def test_reassigning_a_task_notifies_the_new_assignee_once(
    client: TestClient, db: Session, team: dict[str, Any]
):
    entry_id = save(client, team["owner"], add_tender(db).id)
    task = client.post(
        f"/api/workspace/{entry_id}/tasks", json={"title": "Site visit"}, headers=team["owner"]
    ).json()
    url = f"/api/workspace/{entry_id}/tasks/{task['id']}"

    client.patch(url, json={"assignee_id": team["member_id"]}, headers=team["owner"])
    client.patch(url, json={"assignee_id": team["member_id"]}, headers=team["owner"])  # no change
    client.patch(url, json={"is_done": True}, headers=team["owner"])

    assert notifications(client, team["member"])["unread_count"] == 1


def test_status_change_notifies_the_rest_of_the_team(
    client: TestClient, db: Session, team: dict[str, Any]
):
    entry_id = save(client, team["owner"], add_tender(db).id)

    client.patch(f"/api/workspace/{entry_id}", json={"status": "submitted"}, headers=team["member"])

    owner = notifications(client, team["owner"])
    assert owner["items"][0]["title"] == "Sipho Member changed a tender to Submitted"
    assert notifications(client, team["member"])["unread_count"] == 0  # not the person who did it


def test_note_notifies_the_rest_of_the_team(client: TestClient, db: Session, team: dict[str, Any]):
    entry_id = save(client, team["owner"], add_tender(db, title="Office cleaning").id)

    client.post(
        f"/api/workspace/{entry_id}/notes",
        json={"body": "We meet the CIDB requirement."},
        headers=team["owner"],
    )

    [item] = notifications(client, team["member"])["items"]
    assert item["type"] == "note_added"
    assert item["title"] == "Thandi Owner added a note: “We meet the CIDB requirement.”"
    assert item["body"] == "Office cleaning"


def test_other_teams_are_never_notified(client: TestClient, db: Session, team: dict[str, Any]):
    other = auth_header(register(client, email="owner@other.co.za", company_name="Other Co"))
    entry_id = save(client, team["owner"], add_tender(db).id)

    client.patch(f"/api/workspace/{entry_id}", json={"status": "interested"}, headers=team["owner"])

    assert notifications(client, other)["unread_count"] == 0


@respx.mock
def test_summary_ready_notifies_the_requester(
    client: TestClient, db: Session, team: dict[str, Any]
):
    respx.get(DOC_URL).respond(content=make_pdf(REQUIREMENTS_TEXT))
    tender = add_tender(
        db,
        title="Road maintenance",
        documents=[{"title": "bid.pdf", "url": DOC_URL, "format": "pdf"}],
    )

    client.post(f"/api/tenders/{tender.id}/summary", headers=team["member"])

    [item] = notifications(client, team["member"])["items"]
    assert item["type"] == "summary_ready"
    assert item["link"] == f"/tenders/{tender.id}"
    assert notifications(client, team["owner"])["unread_count"] == 0


# --- Reading ------------------------------------------------------------------------------


def test_mark_one_and_all_as_read(client: TestClient, db: Session, team: dict[str, Any]):
    entry_id = save(client, team["owner"], add_tender(db).id)
    for status in ("interested", "preparing", "submitted"):
        client.patch(f"/api/workspace/{entry_id}", json={"status": status}, headers=team["owner"])
    items = notifications(client, team["member"])["items"]

    one = client.post(f"/api/notifications/{items[0]['id']}/read", headers=team["member"]).json()
    assert one == {"marked": 1, "unread_count": 2}

    everything = client.post("/api/notifications/read-all", headers=team["member"]).json()
    assert everything["marked"] == 2
    assert notifications(client, team["member"])["unread_count"] == 0


def test_cannot_mark_someone_elses_notification(
    client: TestClient, db: Session, team: dict[str, Any]
):
    entry_id = save(client, team["owner"], add_tender(db).id)
    client.patch(f"/api/workspace/{entry_id}", json={"status": "interested"}, headers=team["owner"])
    item = notifications(client, team["member"])["items"][0]

    response = client.post(f"/api/notifications/{item['id']}/read", headers=team["owner"])

    assert response.json()["marked"] == 0
    assert notifications(client, team["member"])["unread_count"] == 1


def test_notifications_require_login(client: TestClient):
    assert client.get("/api/notifications").status_code == 401


def test_notifier_failures_never_break_the_request():
    class BrokenChannel:
        def deliver(self, notifications):
            raise OSError("mail server down")

    store = InMemoryNotificationStore()
    notifier = Notifier([BrokenChannel(), InAppChannel(store)])

    notifier.send([Notification(user_id=1, team_id=1, type="test", title="Hello")])

    assert len(store.docs) == 1  # other channels still deliver


# --- Reminders -----------------------------------------------------------------------------


def reminder_titles(db: Session, now: datetime | None = None) -> list[tuple[int, str]]:
    return [(n.user_id, n.type) for n in due_reminders(db, now)]


def test_deadline_reminder_for_tenders_closing_soon(
    client: TestClient, db: Session, team: dict[str, Any]
):
    now = datetime.now(UTC)
    soon = add_tender(db, title="Closing soon", closing_at=now + timedelta(days=2))
    later = add_tender(db, title="Closing later", closing_at=now + timedelta(days=10))
    save(client, team["owner"], soon.id)
    save(client, team["owner"], later.id)

    reminders = due_reminders(db, now)

    assert {(n.user_id, n.type, n.body) for n in reminders} == {
        (team["owner_id"], "deadline_reminder", "Closing soon"),
        (team["member_id"], "deadline_reminder", "Closing soon"),
    }
    assert reminders[0].title.startswith("Closes ")


def test_no_deadline_reminders_for_submitted_or_ineligible_tenders(
    client: TestClient, db: Session, team: dict[str, Any]
):
    now = datetime.now(UTC)
    for status in ("submitted", "not_eligible"):
        entry_id = save(
            client, team["owner"], add_tender(db, closing_at=now + timedelta(days=1)).id
        )
        client.patch(f"/api/workspace/{entry_id}", json={"status": status}, headers=team["owner"])

    assert due_reminders(db, now) == []


def test_compulsory_briefing_reminder(client: TestClient, db: Session, team: dict[str, Any]):
    now = datetime.now(UTC)
    tender = add_tender(
        db,
        closing_at=now + timedelta(days=20),
        briefing_compulsory=True,
        briefing_at=now + timedelta(days=1),
    )
    save(client, team["owner"], tender.id)

    types = {n.type for n in due_reminders(db, now)}

    assert types == {"briefing_reminder"}


def test_reminders_are_only_sent_once(
    client: TestClient,
    db: Session,
    team: dict[str, Any],
    notification_store: InMemoryNotificationStore,
):
    tender = add_tender(db, closing_at=datetime.now(UTC) + timedelta(days=1))
    save(client, team["owner"], tender.id)
    notifier = Notifier([InAppChannel(notification_store)])

    run_reminders(TestingSessionLocal, notifier)
    run_reminders(TestingSessionLocal, notifier)  # the hourly job runs again

    assert notifications(client, team["owner"])["unread_count"] == 1
    assert notifications(client, team["member"])["unread_count"] == 1
