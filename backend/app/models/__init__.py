# Import every model here so SQLAlchemy (and Alembic) know about all tables.
from app.models.company_profile import CompanyProfile
from app.models.team import Plan, Team
from app.models.user import User, UserRole

__all__ = ["CompanyProfile", "Plan", "Team", "User", "UserRole"]
