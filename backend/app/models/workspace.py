from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.tender import Tender
from app.models.user import User


class WorkspaceStatus(StrEnum):
    PENDING = "pending"
    INTERESTED = "interested"
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    NOT_ELIGIBLE = "not_eligible"


def _status_enum(name: str) -> Enum:
    return Enum(
        WorkspaceStatus,
        name=name,
        native_enum=False,
        length=20,
        values_callable=lambda e: [m.value for m in e],
    )


class WorkspaceTender(Base):
    """A tender a team has saved to its workspace."""

    __tablename__ = "workspace_tenders"
    __table_args__ = (UniqueConstraint("team_id", "tender_id", name="uq_workspace_team_tender"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"))
    status: Mapped[WorkspaceStatus] = mapped_column(
        _status_enum("workspacestatus"), default=WorkspaceStatus.PENDING
    )
    saved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status_changed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tender: Mapped[Tender] = relationship()
    saved_by: Mapped[User | None] = relationship(foreign_keys=[saved_by_id])
    status_changed_by: Mapped[User | None] = relationship(foreign_keys=[status_changed_by_id])
    status_changes: Mapped[list["WorkspaceStatusChange"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="(WorkspaceStatusChange.created_at.desc(), WorkspaceStatusChange.id.desc())",
    )
    notes: Mapped[list["WorkspaceNote"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="(WorkspaceNote.created_at, WorkspaceNote.id)",
    )
    tasks: Mapped[list["WorkspaceTask"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="(WorkspaceTask.created_at, WorkspaceTask.id)",
    )


class WorkspaceStatusChange(Base):
    """History of status changes, so the team can see who changed what and when."""

    __tablename__ = "workspace_status_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_tenders.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[WorkspaceStatus | None] = mapped_column(_status_enum("fromstatus"))
    to_status: Mapped[WorkspaceStatus] = mapped_column(_status_enum("tostatus"))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry: Mapped[WorkspaceTender] = relationship(back_populates="status_changes")
    changed_by: Mapped[User | None] = relationship()


class WorkspaceNote(Base):
    __tablename__ = "workspace_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_tenders.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entry: Mapped[WorkspaceTender] = relationship(back_populates="notes")
    author: Mapped[User | None] = relationship()


class WorkspaceTask(Base):
    __tablename__ = "workspace_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_tenders.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry: Mapped[WorkspaceTender] = relationship(back_populates="tasks")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
