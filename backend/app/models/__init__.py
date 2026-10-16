# Import every model here so SQLAlchemy (and Alembic) know about all tables.
from app.models.company_profile import CompanyProfile
from app.models.team import Plan, Team
from app.models.tender import Tender
from app.models.usage import SearchUsage
from app.models.user import User, UserRole
from app.models.workspace import (
    WorkspaceNote,
    WorkspaceStatus,
    WorkspaceStatusChange,
    WorkspaceTask,
    WorkspaceTender,
)

__all__ = [
    "CompanyProfile",
    "Plan",
    "SearchUsage",
    "Team",
    "Tender",
    "User",
    "UserRole",
    "WorkspaceNote",
    "WorkspaceStatus",
    "WorkspaceStatusChange",
    "WorkspaceTask",
    "WorkspaceTender",
]
