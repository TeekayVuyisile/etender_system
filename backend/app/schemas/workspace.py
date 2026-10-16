from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import WorkspaceStatus
from app.schemas.tender import TenderListItem

NoteBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
TaskTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str


class WorkspaceEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: WorkspaceStatus
    tender: TenderListItem
    saved_by: UserSummary | None
    status_changed_by: UserSummary | None
    status_changed_at: datetime
    created_at: datetime
    note_count: int = 0
    open_task_count: int = 0
    # Filled in by the AI summary and readiness scoring milestones.
    ai_summary: str | None = None
    match_score: float | None = None


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceEntryRead]
    status_counts: dict[WorkspaceStatus, int]


class StatusChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: WorkspaceStatus | None
    to_status: WorkspaceStatus
    changed_by: UserSummary | None
    created_at: datetime


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    author: UserSummary | None
    created_at: datetime
    updated_at: datetime


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_id: int
    title: str
    assignee: UserSummary | None
    due_date: date | None
    is_done: bool
    completed_at: datetime | None
    created_by: UserSummary | None
    created_at: datetime


class WorkspaceEntryDetail(WorkspaceEntryRead):
    status_changes: list[StatusChangeRead]
    notes: list[NoteRead]
    tasks: list[TaskRead]


class SavedTenderRef(BaseModel):
    tender_id: int
    entry_id: int
    status: WorkspaceStatus


class MyTaskRead(TaskRead):
    tender_title: str
    tender_closing_at: datetime | None


class WorkspaceCreate(BaseModel):
    tender_id: int


class WorkspaceUpdate(BaseModel):
    status: WorkspaceStatus


class NoteCreate(BaseModel):
    body: NoteBody


class TaskCreate(BaseModel):
    title: TaskTitle
    assignee_id: int | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    """Partial update: only fields that are sent are changed (send null to unassign)."""

    title: TaskTitle | None = None
    assignee_id: int | None = None
    due_date: date | None = None
    is_done: bool | None = Field(default=None)
