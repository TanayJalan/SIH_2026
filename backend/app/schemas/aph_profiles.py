"""Pydantic validators for the APH JSONB profiles stored on ``institutions``.

The key names are taken from APH_SPEC sections 7.2 (land, building and area),
7.3 (library, computing, internet and laboratories) and 7.4 (essential
requirements). Every field is optional because a draft institution may not have
answered the profile yet; when a value is present it is type- and range-checked
before it reaches the database.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AphModel(BaseModel):
    """Base model that rejects unknown keys so typos are caught early."""

    model_config = ConfigDict(extra="forbid")


class AccreditationProfile(AphModel):
    """Accreditation criteria used by the Extended EoA checker (APH 2.1a)."""

    nirf_8th: bool | None = None
    """Figured in NIRF 8th edition (APH 2.1a)."""
    qs_asia_2024: bool | None = None
    """Figured in QS Asia 2024 (APH 2.1a)."""
    naac_score: float | None = Field(default=None, ge=0, le=4)
    """NAAC score on the 4-point scale; 3.01 is the APH threshold (APH 2.1a)."""
    nba_courses_pct: float | None = Field(default=None, ge=0, le=100)
    """Share of eligible courses with valid NBA accreditation (APH 2.1a)."""
    nba_valid_until: date | None = None
    """NBA validity date; the handbook example is 30 April 2025 (APH 2.1a)."""
    autonomous: bool | None = None
    """Autonomous status from UGC or AICTE (APH 2.1a)."""
    avg_admission_pct_5y: float | None = Field(default=None, ge=0, le=100)
    """Average admissions over the last five academic years (APH 2.1a)."""


class CampusPlot(AphModel):
    """One land parcel; APH allows at most three contiguous plots (APH 6.17d)."""

    area_sqm: float | None = Field(default=None, ge=0)
    title_status: str | None = None
    lease_years: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)


class CampusProfile(AphModel):
    """Campus geometry and land constraints (APH 6.17, Annexure-3)."""

    plots: list[CampusPlot] = Field(default_factory=list)
    gap_km: float | None = Field(default=None, ge=0)
    """Maximum distance between plots; APH 6.17d caps it at 2 km."""
    contiguous: bool | None = None
    obstacles: list[str] = Field(default_factory=list)
    """Rivers, canals, rail lines, highways or high-tension lines (APH 6.17d)."""
    built_up_sqm: float | None = Field(default=None, ge=0)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class InfrastructureProfile(AphModel):
    """Built-up area breakdown (APH 6.17-6.18, Annexure-3)."""

    land_area_sqm: float | None = Field(default=None, ge=0)
    built_up_sqm: float | None = Field(default=None, ge=0)
    instructional_area_sqm: float | None = Field(default=None, ge=0)
    administrative_area_sqm: float | None = Field(default=None, ge=0)
    amenities_area_sqm: float | None = Field(default=None, ge=0)
    circulation_area_sqm: float | None = Field(default=None, ge=0)
    classrooms: int | None = Field(default=None, ge=0)
    tutorial_rooms: int | None = Field(default=None, ge=0)
    labs: int | None = Field(default=None, ge=0)
    workshops: int | None = Field(default=None, ge=0)
    library_area_sqm: float | None = Field(default=None, ge=0)
    seminar_hall_sqm: float | None = Field(default=None, ge=0)
    computer_centre_sqm: float | None = Field(default=None, ge=0)
    playground: bool | None = None
    occupancy_certificate_valid_until: date | None = None
    fire_safety_valid_until: date | None = None
    structural_stability_valid_until: date | None = None
    barrier_free: bool | None = None


class LibraryProfile(AphModel):
    """Library holdings and reading-room capacity (APH 7.3, Annexure-4)."""

    titles: int | None = Field(default=None, ge=0)
    volumes: int | None = Field(default=None, ge=0)
    journals: int | None = Field(default=None, ge=0)
    ebooks_pct: float | None = Field(default=None, ge=0, le=100)
    reading_room_seats: int | None = Field(default=None, ge=0)
    digital_library_pcs: int | None = Field(default=None, ge=0)
    ndl_membership: bool | None = None


class ComputingProfile(AphModel):
    """Computing, internet and laboratory capacity (APH 7.3)."""

    pcs: int | None = Field(default=None, ge=0)
    pc_student_ratio: float | None = Field(default=None, ge=0)
    printers: int | None = Field(default=None, ge=0)
    bandwidth_mbps: int | None = Field(default=None, ge=0)
    language_lab_pcs: int | None = Field(default=None, ge=0)
    wifi: bool | None = None
    plagiarism_software: bool | None = None


class EssentialRequirements(AphModel):
    """The yes/no compliance checklist of APH 6.47-6.53.

    Each flag must be backed by evidence; the compliance explanation and
    evidence payload record what has been checked for the institution.
    """

    anti_ragging_committee: bool | None = None
    anti_ragging_squad: bool | None = None
    cctv: bool | None = None
    internal_committee: bool | None = None
    sc_st_committee: bool | None = None
    grievance_redressal: bool | None = None
    ombudsperson: bool | None = None
    innovation_council: bool | None = None
    barrier_free_facilities: bool | None = None
    abc_compliance: bool | None = None
    campus_safety: bool | None = None
    food_safety: bool | None = None
    digital_payments: bool | None = None
    letters_displayed: bool | None = None
    mental_health_counselling: bool | None = None
    women_helpline_24x7: bool | None = None
    first_aid: bool | None = None
    potable_water: bool | None = None
    waste_management: bool | None = None
    student_insurance: bool | None = None
    sel_mechanism: bool | None = None
    compulsory_internship: bool | None = None
    swayam_electives: bool | None = None
    skilling_credits: bool | None = None
    industry_institution_cell: bool | None = None
    language_lab: bool | None = None
    iqac: bool | None = None


INSTITUTION_PROFILE_MODELS: dict[str, type[AphModel]] = {
    "accreditation": AccreditationProfile,
    "infra_profile": InfrastructureProfile,
    "library_profile": LibraryProfile,
    "computing_profile": ComputingProfile,
    "essential_requirements": EssentialRequirements,
    "campus": CampusProfile,
}


def validate_profile(field: str, value: object) -> dict[str, object]:
    """Validate one institution JSONB profile and return a JSON-safe dict.

    ``None`` and an empty dict are accepted for every profile so existing rows
    and partially completed applications remain valid.
    """
    model = INSTITUTION_PROFILE_MODELS[field]
    if value is None:
        return {}
    validated = model.model_validate(value)
    return validated.model_dump(mode="json", exclude_none=True)
