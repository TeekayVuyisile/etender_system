from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.reference import CidbClass, IndustrySector, Province

Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


def _dedupe(values: list[str]) -> list[str]:
    """Remove duplicates (case-insensitive) while keeping the original order."""
    seen: set[str] = set()
    result = []
    for value in values:
        if value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result


UniqueTags = Annotated[list[Tag], AfterValidator(_dedupe)]


class CidbGrading(BaseModel):
    class_code: CidbClass
    grade: int = Field(ge=1, le=9)


class CompanyProfileBase(BaseModel):
    industry_sector: IndustrySector
    services: UniqueTags = Field(min_length=1, max_length=30)
    cidb_gradings: list[CidbGrading] = Field(default_factory=list, max_length=5)
    bbbee_level: int | None = Field(default=None, ge=1, le=8)
    certifications: UniqueTags = Field(default_factory=list, max_length=30)
    provinces: list[Province] = Field(min_length=1)
    years_of_experience: int = Field(ge=0, le=150)

    contact_name: str = Field(min_length=2, max_length=200)
    contact_email: EmailStr
    contact_phone: str = Field(min_length=7, max_length=30, pattern=r"^\+?[0-9 ()-]+$")
    website: str | None = Field(default=None, max_length=300)
    physical_address: str | None = Field(default=None, max_length=500)

    @field_validator("provinces")
    @classmethod
    def unique_provinces(cls, provinces: list[str]) -> list[str]:
        return list(dict.fromkeys(provinces))

    @field_validator("cidb_gradings")
    @classmethod
    def one_grade_per_class(cls, gradings: list[CidbGrading]) -> list[CidbGrading]:
        codes = [g.class_code for g in gradings]
        if len(codes) != len(set(codes)):
            raise ValueError("Each CIDB class can only be listed once")
        return gradings

    @field_validator("website", "physical_address")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class CompanyProfileUpdate(CompanyProfileBase):
    """Request body for creating or replacing a team's profile."""


class CompanyProfileRead(CompanyProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    created_at: datetime
    updated_at: datetime


class Option(BaseModel):
    value: str
    label: str


class ProfileOptions(BaseModel):
    industry_sectors: list[str]
    provinces: list[str]
    cidb_classes: list[Option]
    cidb_grades: list[int]
    bbbee_levels: list[int]
    certification_suggestions: list[str]
