"""Validated JSON sections for institution application drafts.

Draft values intentionally stay permissive. Users type into a wizard and save
after each change, so a partially typed email address or URL must not prevent a
draft from being stored. Format checks that block submission live in the
completeness service and return field-level messages.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NaacGrade = Literal["A++", "A+", "A", "B++", "B+", "B", "C", "NOT_ACCREDITED"]
NbaStatus = Literal["ACCREDITED", "NOT_ACCREDITED", "APPLIED"]


class SectionModel(BaseModel):
    """Base model for a draft section."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class InstitutionProfileSection(SectionModel):
    """Institution identity and primary contact details."""

    head_name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pin_code: str | None = Field(default=None, max_length=12)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=24)
    website: str | None = Field(default=None, max_length=500)


class InfrastructureSection(SectionModel):
    """Physical infrastructure values supplied by the institution."""

    land_area: float | None = Field(default=None, ge=0)
    built_up_area: float | None = Field(default=None, ge=0)
    labs: int | None = Field(default=None, ge=0)
    library: int | None = Field(default=None, ge=0)
    hostel: int | None = Field(default=None, ge=0)


class FacultySection(SectionModel):
    """Faculty totals by cadre and the ratio inputs used for scrutiny."""

    total: int | None = Field(default=None, ge=0)
    professors: int | None = Field(default=None, ge=0)
    associate_professors: int | None = Field(default=None, ge=0)
    assistant_professors: int | None = Field(default=None, ge=0)
    student_faculty_ratio: float | None = Field(default=None, ge=0)
    phd_faculty_ratio: float | None = Field(default=None, ge=0, le=100)


class FinanceSection(SectionModel):
    """Annual fee structure and the institution's declared balance."""

    tuition_fee: float | None = Field(default=None, ge=0)
    development_fee: float | None = Field(default=None, ge=0)
    other_fees: float | None = Field(default=None, ge=0)
    balance: float | None = None


class AccreditationSection(SectionModel):
    """NAAC and NBA accreditation inputs."""

    naac_grade: NaacGrade | None = None
    nba_status: NbaStatus | None = None
    last_validated_on: date | None = None


class ApplicationData(BaseModel):
    """The multi-step form payload stored in ``applications.data``."""

    model_config = ConfigDict(extra="ignore")

    institution_profile: InstitutionProfileSection | None = None
    infrastructure: InfrastructureSection | None = None
    faculty: FacultySection | None = None
    finance: FinanceSection | None = None
    accreditation: AccreditationSection | None = None
    mandatory_disclosure_url: str | None = Field(default=None, max_length=500)
