from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.core.plans import Feature
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import ApiKey, Team, User, UserRole
from app.services.activity import ActivityLogger, get_activity_logger
from app.services.api_keys import rate_limiter, verify_key
from app.services.plans import ensure_feature

# tokenUrl tells Swagger UI where to send the login form for its "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DbSession = Annotated[Session, Depends(get_db)]
Activity = Annotated[ActivityLogger, Depends(get_activity_logger)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    # Load the team in the same query: most endpoints need it, and it saves a round trip.
    user = db.get(User, user_id, options=[joinedload(User.team)])
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_owner(user: CurrentUser) -> User:
    if user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the team owner can do this"
        )
    return user


TeamOwner = Annotated[User, Depends(require_owner)]


def require_feature(feature: Feature):
    """Dependency factory: only allow the request if the team's plan includes `feature`."""

    def dependency(user: CurrentUser) -> User:
        ensure_feature(user.team, feature)
        return user

    return dependency


# --- Public API authentication -------------------------------------------------------

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key created on the API access page (starts with tih_)",
)
optional_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


@dataclass
class ApiCaller:
    """Who is calling the public API: a team, via an API key or a logged-in user."""

    team: Team
    user: User | None = None
    api_key: ApiKey | None = None

    @property
    def actor_id(self) -> int:
        """User ID for activity logs (the key's creator for API-key calls)."""
        if self.user:
            return self.user.id
        return (self.api_key.created_by_id if self.api_key else None) or 0

    def require(self, feature: Feature) -> None:
        ensure_feature(self.team, feature)


def get_api_caller(
    db: DbSession,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
    token: Annotated[str | None, Depends(optional_bearer)] = None,
) -> ApiCaller:
    """Accept either an X-API-Key header (third-party systems) or a Bearer token."""
    if api_key:
        key = verify_key(db, api_key)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")
        rate_limiter.check(key.id)
        return ApiCaller(team=key.team, api_key=key)
    if token:
        user = get_current_user(token, db)
        return ApiCaller(team=user.team, user=user)
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Provide an API key in the X-API-Key header (or a Bearer token)",
    )


Caller = Annotated[ApiCaller, Depends(get_api_caller)]
