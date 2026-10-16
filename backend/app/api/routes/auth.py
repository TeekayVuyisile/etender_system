from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import Activity, CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import Team, User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse
from app.schemas.user import CurrentUserRead
from app.services.api_keys import RateLimiter
from app.services.demo import DemoStores, create_demo_team
from app.services.match_store import MatchStore, get_match_store
from app.services.notifications import NotificationStore, get_notification_store
from app.services.summary_store import SummaryStore, get_summary_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest, db: DbSession, activity: Activity, background_tasks: BackgroundTasks
) -> TokenResponse:
    """Create a new team and its owner account, then log the owner in."""
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")

    team = Team(name=data.company_name.strip())
    user = User(
        email=email,
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=UserRole.OWNER,
        team=team,
    )
    db.add_all([team, user])
    db.commit()

    # Background tasks run after the response is sent, so logging never slows the user down.
    background_tasks.add_task(activity.log, "user.registered", user_id=user.id, team_id=team.id)
    return TokenResponse(access_token=create_access_token(user.id, team.id))


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> TokenResponse:
    """Log in with email (sent as the OAuth2 "username" field) and password."""
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    hashed = user.hashed_password if user else DUMMY_PASSWORD_HASH
    if not verify_password(form.password, hashed) or user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    background_tasks.add_task(activity.log, "user.login", user_id=user.id, team_id=user.team_id)
    return TokenResponse(access_token=create_access_token(user.id, user.team_id))


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(user: CurrentUser) -> User:
    return user


demo_rate_limiter = RateLimiter(limit=10, window_seconds=3600)


@router.post("/demo", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def start_demo(
    request: Request,
    db: DbSession,
    summaries: Annotated[SummaryStore, Depends(get_summary_store)],
    matches: Annotated[MatchStore, Depends(get_match_store)],
    notifications: Annotated[NotificationStore, Depends(get_notification_store)],
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> TokenResponse:
    """Try the demo: create a private demo team with sample data and log in as its owner.

    Only available when demo mode is enabled. Demo teams are deleted after a day.
    """
    if not settings.demo_mode_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Demo mode is not enabled")
    demo_rate_limiter.check(request.client.host if request.client else "unknown")

    owner = create_demo_team(db, DemoStores(summaries, matches, notifications))
    background_tasks.add_task(
        activity.log, "user.demo_started", user_id=owner.id, team_id=owner.team_id
    )
    return TokenResponse(access_token=create_access_token(owner.id, owner.team_id))
