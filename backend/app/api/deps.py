from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, joinedload

from app.core.plans import Feature
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User, UserRole
from app.services.activity import ActivityLogger, get_activity_logger
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
