from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import Activity, CurrentUser, DbSession, TeamOwner
from app.core.security import hash_password
from app.models import User, UserRole
from app.schemas.user import MemberCreate, UserRead

router = APIRouter(prefix="/team", tags=["team"])


@router.get("/members", response_model=list[UserRead])
def list_members(user: CurrentUser, db: DbSession) -> list[User]:
    members = db.scalars(
        select(User).where(User.team_id == user.team_id).order_by(User.created_at, User.id)
    )
    return list(members)


@router.post("/members", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def add_member(
    data: MemberCreate,
    owner: TeamOwner,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> User:
    """Add a member to the owner's team (seat limits per plan are enforced later)."""
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")

    member = User(
        email=email,
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=UserRole.MEMBER,
        team_id=owner.team_id,
    )
    db.add(member)
    db.commit()

    background_tasks.add_task(
        activity.log,
        "team.member_added",
        user_id=owner.id,
        team_id=owner.team_id,
        details={"member_id": member.id, "member_email": member.email},
    )
    return member
