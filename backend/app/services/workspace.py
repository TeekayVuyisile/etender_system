"""Queries for the team workspace. Every query is scoped to the caller's team."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, load_only, selectinload

from app.models import (
    User,
    WorkspaceNote,
    WorkspaceStatus,
    WorkspaceStatusChange,
    WorkspaceTask,
    WorkspaceTender,
)
from app.models.tender import Tender
from app.schemas.workspace import WorkspaceEntryRead
from app.services.tender_search import LIST_COLUMNS

_TENDER_SUMMARY = joinedload(WorkspaceTender.tender).load_only(*LIST_COLUMNS)
_USERS = (joinedload(WorkspaceTender.saved_by), joinedload(WorkspaceTender.status_changed_by))


def list_entries(
    db: Session, team_id: int, status_filter: WorkspaceStatus | None
) -> list[WorkspaceEntryRead]:
    note_counts = (
        select(WorkspaceNote.entry_id, func.count().label("n"))
        .group_by(WorkspaceNote.entry_id)
        .subquery()
    )
    task_counts = (
        select(WorkspaceTask.entry_id, func.count().label("n"))
        .where(WorkspaceTask.is_done.is_(False))
        .group_by(WorkspaceTask.entry_id)
        .subquery()
    )
    stmt = (
        select(
            WorkspaceTender,
            func.coalesce(note_counts.c.n, 0),
            func.coalesce(task_counts.c.n, 0),
        )
        .join(WorkspaceTender.tender)
        .outerjoin(note_counts, note_counts.c.entry_id == WorkspaceTender.id)
        .outerjoin(task_counts, task_counts.c.entry_id == WorkspaceTender.id)
        .where(WorkspaceTender.team_id == team_id)
        .options(_TENDER_SUMMARY, *_USERS)
        # Most relevant first: by match score once scoring exists, then by nearest deadline.
        .order_by(Tender.closing_at.asc().nulls_last(), WorkspaceTender.id)
    )
    if status_filter:
        stmt = stmt.where(WorkspaceTender.status == status_filter)

    entries = []
    for entry, note_count, open_task_count in db.execute(stmt).unique():
        item = WorkspaceEntryRead.model_validate(entry)
        item.note_count, item.open_task_count = note_count, open_task_count
        entries.append(item)
    return entries


def status_counts(db: Session, team_id: int) -> dict[WorkspaceStatus, int]:
    rows = db.execute(
        select(WorkspaceTender.status, func.count())
        .where(WorkspaceTender.team_id == team_id)
        .group_by(WorkspaceTender.status)
    ).all()
    counts = dict.fromkeys(WorkspaceStatus, 0)
    counts.update({WorkspaceStatus(s): n for s, n in rows})
    return counts


def get_entry(db: Session, entry_id: int, team_id: int, detail: bool = False) -> WorkspaceTender:
    options = [_TENDER_SUMMARY, *_USERS]
    if detail:
        options += [
            selectinload(WorkspaceTender.status_changes).joinedload(
                WorkspaceStatusChange.changed_by
            ),
            selectinload(WorkspaceTender.notes).joinedload(WorkspaceNote.author),
            selectinload(WorkspaceTender.tasks).options(
                joinedload(WorkspaceTask.assignee), joinedload(WorkspaceTask.created_by)
            ),
        ]
    entry = db.scalar(
        select(WorkspaceTender)
        .where(WorkspaceTender.id == entry_id, WorkspaceTender.team_id == team_id)
        .options(*options)
        # Always reload from the database, even if this session already holds the entry.
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Workspace entry not found")
    return entry


def change_status(db: Session, entry: WorkspaceTender, new_status: WorkspaceStatus, user: User):
    db.add(
        WorkspaceStatusChange(
            entry_id=entry.id,
            from_status=entry.status,
            to_status=new_status,
            changed_by_id=user.id,
        )
    )
    entry.status = new_status
    entry.status_changed_by_id = user.id
    entry.status_changed_at = datetime.now(UTC)


def team_member(db: Session, user_id: int, team_id: int) -> User:
    member = db.scalar(select(User).where(User.id == user_id, User.team_id == team_id))
    if member is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Assignee must be a member of your team"
        )
    return member


def get_task(db: Session, entry_id: int, task_id: int, team_id: int) -> WorkspaceTask:
    task = db.scalar(
        select(WorkspaceTask)
        .join(WorkspaceTask.entry)
        .where(
            WorkspaceTask.id == task_id,
            WorkspaceTask.entry_id == entry_id,
            WorkspaceTender.team_id == team_id,
        )
        .options(joinedload(WorkspaceTask.assignee), joinedload(WorkspaceTask.created_by))
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def get_note(db: Session, entry_id: int, note_id: int, team_id: int) -> WorkspaceNote:
    note = db.scalar(
        select(WorkspaceNote)
        .join(WorkspaceNote.entry)
        .where(
            WorkspaceNote.id == note_id,
            WorkspaceNote.entry_id == entry_id,
            WorkspaceTender.team_id == team_id,
        )
        .options(joinedload(WorkspaceNote.author))
    )
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def my_open_tasks(db: Session, user: User) -> list[tuple[WorkspaceTask, Tender]]:
    rows = db.execute(
        select(WorkspaceTask, Tender)
        .join(WorkspaceTask.entry)
        .join(WorkspaceTender.tender)
        .where(
            WorkspaceTask.assignee_id == user.id,
            WorkspaceTask.is_done.is_(False),
            WorkspaceTender.team_id == user.team_id,
        )
        .options(
            joinedload(WorkspaceTask.assignee),
            joinedload(WorkspaceTask.created_by),
            load_only(Tender.id, Tender.title, Tender.closing_at),
        )
        .order_by(WorkspaceTask.due_date.asc().nulls_last(), Tender.closing_at.asc().nulls_last())
    ).all()
    return [(task, tender) for task, tender in rows]


def summary_text(doc: dict | None) -> str | None:
    """The plain-language summary from a stored AI summary document, if it's ready."""
    if doc and doc.get("status") == "ready":
        return (doc.get("content") or {}).get("summary") or None
    return None
