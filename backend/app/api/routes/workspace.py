from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import Activity, CurrentUser, DbSession, require_feature
from app.models import (
    Tender,
    User,
    UserRole,
    WorkspaceNote,
    WorkspaceStatus,
    WorkspaceStatusChange,
    WorkspaceTask,
    WorkspaceTender,
)
from app.schemas.workspace import (
    MyTaskRead,
    NoteCreate,
    NoteRead,
    SavedTenderRef,
    TaskCreate,
    TaskRead,
    TaskUpdate,
    WorkspaceCreate,
    WorkspaceEntryDetail,
    WorkspaceListResponse,
    WorkspaceUpdate,
)
from app.services import exports
from app.services import workspace as service
from app.services.match_store import MatchStore, get_match_store
from app.services.plans import limits_for
from app.services.summary_store import SummaryStore, get_summary_store

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _detail(entry: WorkspaceTender) -> WorkspaceEntryDetail:
    detail = WorkspaceEntryDetail.model_validate(entry)
    detail.note_count = len(entry.notes)
    detail.open_task_count = sum(not task.is_done for task in entry.tasks)
    return detail


# --- Saved tenders ------------------------------------------------------------


@router.get("", response_model=WorkspaceListResponse)
def list_workspace(
    user: CurrentUser,
    db: DbSession,
    store: Annotated[SummaryStore, Depends(get_summary_store)],
    matches: Annotated[MatchStore, Depends(get_match_store)],
    status_filter: Annotated[WorkspaceStatus | None, Query(alias="status")] = None,
) -> WorkspaceListResponse:
    """The team's saved tenders, most relevant first, with counts per status."""
    items = service.list_entries(db, user.team_id, status_filter)
    tender_ids = [item.tender.id for item in items]
    limits = limits_for(user.team)
    summaries = store.get_many(tender_ids) if limits.ai_summaries else {}
    scores = matches.get_many(user.team_id, tender_ids) if limits.readiness_checks else {}
    for item in items:
        item.ai_summary = service.summary_text(summaries.get(item.tender.id))
        item.match_score = (scores.get(item.tender.id) or {}).get("score")
    # Highest match score first; unscored tenders last (already ordered by nearest deadline).
    items.sort(key=lambda item: (item.match_score is None, -(item.match_score or 0)))
    return WorkspaceListResponse(items=items, status_counts=service.status_counts(db, user.team_id))


@router.get("/saved", response_model=list[SavedTenderRef])
def list_saved_tender_ids(user: CurrentUser, db: DbSession) -> list[SavedTenderRef]:
    """Lightweight list of saved tender IDs, used to mark tenders as saved in search results."""
    rows = db.execute(
        select(WorkspaceTender.tender_id, WorkspaceTender.id, WorkspaceTender.status).where(
            WorkspaceTender.team_id == user.team_id
        )
    ).all()
    return [SavedTenderRef(tender_id=t, entry_id=e, status=s) for t, e, s in rows]


@router.get("/my-tasks", response_model=list[MyTaskRead])
def list_my_tasks(user: CurrentUser, db: DbSession) -> list[MyTaskRead]:
    """Open tasks assigned to the current user."""
    return [
        MyTaskRead(
            **TaskRead.model_validate(task).model_dump(),
            tender_title=tender.title,
            tender_closing_at=tender.closing_at,
        )
        for task, tender in service.my_open_tasks(db, user)
    ]


@router.get("/export")
def export_workspace(
    user: Annotated[User, Depends(require_feature("exports"))],
    db: DbSession,
    store: Annotated[SummaryStore, Depends(get_summary_store)],
    matches: Annotated[MatchStore, Depends(get_match_store)],
    activity: Activity,
    background_tasks: BackgroundTasks,
    export_format: Annotated[Literal["csv", "pdf"], Query(alias="format")] = "csv",
) -> Response:
    """Download the workspace as a CSV spreadsheet or PDF report (Pro plan)."""
    items = service.list_entries(db, user.team_id, None)
    tender_ids = [item.tender.id for item in items]
    summaries = store.get_many(tender_ids)
    results = matches.get_many(user.team_id, tender_ids)
    rows = []
    for item in items:
        item.ai_summary = service.summary_text(summaries.get(item.tender.id))
        result = results.get(item.tender.id) or {}
        item.match_score = result.get("score")
        rows.append(exports.ReportRow(entry=item, verdict=result.get("verdict")))
    rows.sort(key=lambda r: (r.entry.match_score is None, -(r.entry.match_score or 0)))

    now = datetime.now(UTC)
    stamp = f"{now:%Y%m%d}"
    if export_format == "pdf":
        content = exports.build_pdf(user.team.name, rows, now)
        media_type, filename = "application/pdf", f"workspace-report-{stamp}.pdf"
    else:
        content = exports.build_csv(rows)
        media_type, filename = "text/csv; charset=utf-8", f"workspace-{stamp}.csv"

    background_tasks.add_task(
        activity.log,
        "workspace.exported",
        user_id=user.id,
        team_id=user.team_id,
        details={"format": export_format, "entries": len(rows)},
    )
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=WorkspaceEntryDetail, status_code=status.HTTP_201_CREATED)
def save_tender(
    data: WorkspaceCreate,
    user: CurrentUser,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> WorkspaceEntryDetail:
    if db.get(Tender, data.tender_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tender not found")
    existing = db.scalar(
        select(WorkspaceTender.id).where(
            WorkspaceTender.team_id == user.team_id, WorkspaceTender.tender_id == data.tender_id
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Tender is already in your workspace")

    entry = WorkspaceTender(
        team_id=user.team_id,
        tender_id=data.tender_id,
        status=WorkspaceStatus.PENDING,
        saved_by_id=user.id,
        status_changed_by_id=user.id,
    )
    entry.status_changes.append(
        WorkspaceStatusChange(to_status=WorkspaceStatus.PENDING, changed_by_id=user.id)
    )
    db.add(entry)
    db.commit()

    background_tasks.add_task(
        activity.log,
        "workspace.tender_saved",
        user_id=user.id,
        team_id=user.team_id,
        details={"tender_id": data.tender_id, "entry_id": entry.id},
    )
    return _detail(service.get_entry(db, entry.id, user.team_id, detail=True))


@router.get("/{entry_id}", response_model=WorkspaceEntryDetail)
def get_workspace_entry(
    entry_id: int,
    user: CurrentUser,
    db: DbSession,
    store: Annotated[SummaryStore, Depends(get_summary_store)],
    matches: Annotated[MatchStore, Depends(get_match_store)],
) -> WorkspaceEntryDetail:
    detail = _detail(service.get_entry(db, entry_id, user.team_id, detail=True))
    limits = limits_for(user.team)
    if limits.ai_summaries:
        detail.ai_summary = service.summary_text(store.get(detail.tender.id))
    if limits.readiness_checks:
        detail.match_score = (matches.get(user.team_id, detail.tender.id) or {}).get("score")
    return detail


@router.patch("/{entry_id}", response_model=WorkspaceEntryDetail)
def update_status(
    entry_id: int,
    data: WorkspaceUpdate,
    user: CurrentUser,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> WorkspaceEntryDetail:
    entry = service.get_entry(db, entry_id, user.team_id)
    old_status = entry.status
    if data.status != old_status:
        service.change_status(db, entry, data.status, user)
        db.commit()
        background_tasks.add_task(
            activity.log,
            "workspace.status_changed",
            user_id=user.id,
            team_id=user.team_id,
            details={"entry_id": entry_id, "from": old_status, "to": data.status},
        )
    db.expire_all()
    return _detail(service.get_entry(db, entry_id, user.team_id, detail=True))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_workspace(
    entry_id: int,
    user: CurrentUser,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> Response:
    entry = service.get_entry(db, entry_id, user.team_id)
    tender_id = entry.tender_id
    db.delete(entry)
    db.commit()
    background_tasks.add_task(
        activity.log,
        "workspace.tender_removed",
        user_id=user.id,
        team_id=user.team_id,
        details={"tender_id": tender_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Notes --------------------------------------------------------------------


@router.post("/{entry_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def add_note(
    entry_id: int,
    data: NoteCreate,
    user: CurrentUser,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> WorkspaceNote:
    service.get_entry(db, entry_id, user.team_id)
    note = WorkspaceNote(entry_id=entry_id, author_id=user.id, body=data.body)
    db.add(note)
    db.commit()
    background_tasks.add_task(
        activity.log,
        "workspace.note_added",
        user_id=user.id,
        team_id=user.team_id,
        details={"entry_id": entry_id, "note_id": note.id},
    )
    return service.get_note(db, entry_id, note.id, user.team_id)


@router.patch("/{entry_id}/notes/{note_id}", response_model=NoteRead)
def edit_note(
    entry_id: int, note_id: int, data: NoteCreate, user: CurrentUser, db: DbSession
) -> WorkspaceNote:
    note = service.get_note(db, entry_id, note_id, user.team_id)
    if note.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can only edit your own notes")
    note.body = data.body
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{entry_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(entry_id: int, note_id: int, user: CurrentUser, db: DbSession) -> Response:
    note = service.get_note(db, entry_id, note_id, user.team_id)
    if note.author_id != user.id and user.role != UserRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can only delete your own notes")
    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Tasks --------------------------------------------------------------------


@router.post("/{entry_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def add_task(
    entry_id: int,
    data: TaskCreate,
    user: CurrentUser,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> WorkspaceTask:
    service.get_entry(db, entry_id, user.team_id)
    if data.assignee_id is not None:
        service.team_member(db, data.assignee_id, user.team_id)
    task = WorkspaceTask(
        entry_id=entry_id,
        title=data.title,
        assignee_id=data.assignee_id,
        due_date=data.due_date,
        created_by_id=user.id,
    )
    db.add(task)
    db.commit()
    background_tasks.add_task(
        activity.log,
        "workspace.task_added",
        user_id=user.id,
        team_id=user.team_id,
        details={"entry_id": entry_id, "task_id": task.id, "assignee_id": data.assignee_id},
    )
    return service.get_task(db, entry_id, task.id, user.team_id)


@router.patch("/{entry_id}/tasks/{task_id}", response_model=TaskRead)
def update_task(
    entry_id: int, task_id: int, data: TaskUpdate, user: CurrentUser, db: DbSession
) -> WorkspaceTask:
    task = service.get_task(db, entry_id, task_id, user.team_id)
    changes = data.model_dump(exclude_unset=True)

    if changes.get("assignee_id") is not None:
        service.team_member(db, changes["assignee_id"], user.team_id)
    if "title" in changes and changes["title"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Title cannot be empty")
    if "is_done" in changes:
        if changes["is_done"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="is_done is required")
        task.completed_at = datetime.now(UTC) if changes["is_done"] else None

    for field, value in changes.items():
        setattr(task, field, value)
    db.commit()
    db.expire_all()
    return service.get_task(db, entry_id, task_id, user.team_id)


@router.delete("/{entry_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(entry_id: int, task_id: int, user: CurrentUser, db: DbSession) -> Response:
    task = service.get_task(db, entry_id, task_id, user.team_id)
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
