"""Builds notifications for things that happen in the app, and the reminder job."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Tender, User, WorkspaceStatus, WorkspaceTender
from app.services.notifications import Notification, Notifier
from app.services.tender_sync import SAST

logger = logging.getLogger(__name__)

DEADLINE_WINDOW = timedelta(days=3)
BRIEFING_WINDOW = timedelta(days=2)
STATUS_LABELS = {
    WorkspaceStatus.PENDING: "Pending",
    WorkspaceStatus.INTERESTED: "Interested",
    WorkspaceStatus.PREPARING: "Preparing bid",
    WorkspaceStatus.SUBMITTED: "Submitted",
    WorkspaceStatus.NOT_ELIGIBLE: "Not eligible",
}


def short(title: str, limit: int = 80) -> str:
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def team_user_ids(db: Session, team_id: int, exclude: int | None = None) -> list[int]:
    ids = db.scalars(select(User.id).where(User.team_id == team_id, User.is_active.is_(True)))
    return [i for i in ids if i != exclude]


# --- Events -------------------------------------------------------------------------


def task_assigned(
    entry_id: int, tender_title: str, task_title: str, assignee_id: int, actor: User
) -> list[Notification]:
    if assignee_id == actor.id:
        return []  # no need to tell people about tasks they gave themselves
    return [
        Notification(
            user_id=assignee_id,
            team_id=actor.team_id,
            type="task_assigned",
            title=f"{actor.full_name} assigned you a task: {task_title}",
            body=short(tender_title),
            link=f"/workspace/{entry_id}",
            actor_name=actor.full_name,
        )
    ]


def status_changed(
    db: Session, entry_id: int, tender_title: str, new_status: WorkspaceStatus, actor: User
) -> list[Notification]:
    return [
        Notification(
            user_id=user_id,
            team_id=actor.team_id,
            type="status_changed",
            title=f"{actor.full_name} changed a tender to {STATUS_LABELS[new_status]}",
            body=short(tender_title),
            link=f"/workspace/{entry_id}",
            actor_name=actor.full_name,
        )
        for user_id in team_user_ids(db, actor.team_id, exclude=actor.id)
    ]


def note_added(
    db: Session, entry_id: int, tender_title: str, note_body: str, actor: User
) -> list[Notification]:
    return [
        Notification(
            user_id=user_id,
            team_id=actor.team_id,
            type="note_added",
            title=f"{actor.full_name} added a note: “{short(note_body, 70)}”",
            body=short(tender_title),
            link=f"/workspace/{entry_id}",
            actor_name=actor.full_name,
        )
        for user_id in team_user_ids(db, actor.team_id, exclude=actor.id)
    ]


def summary_ready(user_id: int, team_id: int, tender: Tender) -> list[Notification]:
    return [
        Notification(
            user_id=user_id,
            team_id=team_id,
            type="summary_ready",
            title="Your AI summary is ready",
            body=short(tender.title),
            link=f"/tenders/{tender.id}",
        )
    ]


# --- Reminders (run periodically) ----------------------------------------------------------


def _when(value: datetime) -> str:
    local = (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(SAST)
    return f"{local:%a %d %b, %H:%M}"


def due_reminders(db: Session, now: datetime | None = None) -> list[Notification]:
    """Deadline and compulsory-briefing reminders for tenders saved in workspaces.

    Each reminder has a dedupe key, so running this repeatedly never sends one twice.
    """
    now = now or datetime.now(UTC)
    active = (WorkspaceStatus.SUBMITTED, WorkspaceStatus.NOT_ELIGIBLE)
    entries = db.scalars(
        select(WorkspaceTender)
        .join(WorkspaceTender.tender)
        .where(WorkspaceTender.status.not_in(active), Tender.closing_at > now)
        .options(joinedload(WorkspaceTender.tender))
    ).all()

    members: dict[int, list[int]] = {}
    notifications = []
    for entry in entries:
        tender = entry.tender
        recipients = members.setdefault(entry.team_id, team_user_ids(db, entry.team_id))
        reminders = []
        closing = tender.closing_at
        if (
            closing
            and (closing if closing.tzinfo else closing.replace(tzinfo=UTC))
            <= now + DEADLINE_WINDOW
        ):
            reminders.append(
                (
                    "deadline_reminder",
                    f"Closes {_when(closing)}",
                    f"deadline:{entry.id}:{closing:%Y%m%d%H%M}",
                )
            )
        briefing = tender.briefing_at
        if tender.briefing_compulsory and briefing:
            at = briefing if briefing.tzinfo else briefing.replace(tzinfo=UTC)
            if now < at <= now + BRIEFING_WINDOW:
                reminders.append(
                    (
                        "briefing_reminder",
                        f"Compulsory briefing {_when(briefing)}",
                        f"briefing:{entry.id}:{briefing:%Y%m%d%H%M}",
                    )
                )
        for kind, title, key in reminders:
            notifications.extend(
                Notification(
                    user_id=user_id,
                    team_id=entry.team_id,
                    type=kind,
                    title=title,
                    body=short(tender.title),
                    link=f"/workspace/{entry.id}",
                    dedupe_key=key,
                )
                for user_id in recipients
            )
    return notifications


def run_reminders(session_factory: Callable[[], Session], notifier: Notifier) -> int:
    with session_factory() as db:
        notifications = due_reminders(db)
    notifier.send(notifications)
    if notifications:
        logger.info("Checked %d workspace reminder(s)", len(notifications))
    return len(notifications)
