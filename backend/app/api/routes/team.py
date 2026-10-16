from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import Activity, CurrentUser, DbSession, TeamOwner
from app.core.plans import PLANS
from app.core.security import hash_password
from app.models import Plan, User, UserRole
from app.schemas.plan import PlanChange, PlanDetails, PlanUsage, TeamPlanResponse
from app.schemas.user import MemberCreate, UserRead
from app.services.plans import ensure_seat_available, plan_usage, seats_used

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
    """Add a member to the owner's team, within the plan's seat limit."""
    ensure_seat_available(db, owner.team)
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


def _plan_details(plan: Plan) -> PlanDetails:
    limits = PLANS[plan]
    return PlanDetails(
        plan=plan,
        name=limits.name,
        price_label=limits.price_label,
        seats=limits.seats,
        weekly_searches=limits.weekly_searches,
        ai_summaries=limits.ai_summaries,
        readiness_checks=limits.readiness_checks,
        exports=limits.exports,
    )


def _team_plan(db: DbSession, user: User) -> TeamPlanResponse:
    return TeamPlanResponse(
        current=_plan_details(user.team.plan),
        usage=PlanUsage(**plan_usage(db, user.team)),
        available=[_plan_details(plan) for plan in PLANS],
    )


@router.get("/plan", response_model=TeamPlanResponse)
def get_team_plan(user: CurrentUser, db: DbSession) -> TeamPlanResponse:
    """The team's plan, what it allows, and current usage."""
    return _team_plan(db, user)


@router.put("/plan", response_model=TeamPlanResponse)
def change_team_plan(
    data: PlanChange,
    owner: TeamOwner,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> TeamPlanResponse:
    """Switch plans (simulated billing: takes effect immediately, no payment)."""
    team = owner.team
    seat_limit = PLANS[data.plan].seats
    members = seats_used(db, team.id)
    if seat_limit is not None and members > seat_limit:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Your team has {members} members but the {PLANS[data.plan].name} plan "
            f"allows {seat_limit}. Remove members before switching",
        )
    old_plan = team.plan
    team.plan = data.plan
    db.commit()
    if old_plan != data.plan:
        background_tasks.add_task(
            activity.log,
            "team.plan_changed",
            user_id=owner.id,
            team_id=team.id,
            details={"from": old_plan, "to": data.plan},
        )
    return _team_plan(db, owner)
