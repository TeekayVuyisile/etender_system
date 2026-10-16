from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.api.deps import Activity, CurrentUser, DbSession, TeamOwner
from app.core.reference import (
    CERTIFICATION_SUGGESTIONS,
    CIDB_CLASS_NAMES,
    INDUSTRY_SECTORS,
    PROVINCES,
)
from app.models import CompanyProfile
from app.schemas.company_profile import (
    CompanyProfileRead,
    CompanyProfileUpdate,
    Option,
    ProfileOptions,
)

router = APIRouter(prefix="/company-profile", tags=["company profile"])


@router.get("/options", response_model=ProfileOptions)
def get_profile_options() -> ProfileOptions:
    """Allowed values for profile fields, so clients can build forms from one source of truth."""
    return ProfileOptions(
        industry_sectors=INDUSTRY_SECTORS,
        provinces=PROVINCES,
        cidb_classes=[
            Option(value=code, label=f"{code}: {name}") for code, name in CIDB_CLASS_NAMES.items()
        ],
        cidb_grades=list(range(1, 10)),
        bbbee_levels=list(range(1, 9)),
        certification_suggestions=CERTIFICATION_SUGGESTIONS,
    )


@router.get("", response_model=CompanyProfileRead)
def get_company_profile(user: CurrentUser, db: DbSession) -> CompanyProfile:
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.team_id == user.team_id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company profile not created yet")
    return profile


@router.put("", response_model=CompanyProfileRead)
def save_company_profile(
    data: CompanyProfileUpdate,
    owner: TeamOwner,
    db: DbSession,
    activity: Activity,
    background_tasks: BackgroundTasks,
) -> CompanyProfile:
    """Create the team's profile, or replace it if it already exists (owner only)."""
    profile = db.scalar(select(CompanyProfile).where(CompanyProfile.team_id == owner.team_id))
    is_new = profile is None
    if profile is None:
        profile = CompanyProfile(team_id=owner.team_id)
        db.add(profile)

    for field, value in data.model_dump(mode="json").items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)

    background_tasks.add_task(
        activity.log,
        "company_profile.created" if is_new else "company_profile.updated",
        user_id=owner.id,
        team_id=owner.team_id,
    )
    return profile
