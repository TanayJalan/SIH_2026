"""Pure APH compliance calculators (no database, no I/O).

Every function here is deterministic and unit-testable. The formulas and
thresholds come from ``docs/reference/APH_SPEC.md`` sections 6, 7 and 12; the
defaults below mirror the handbook but can be overridden with the
``ComplianceConfig`` rows so an administrator never has to edit code.

Money is not handled here. Areas are square metres, ratios are students per
faculty or students per computer, and years are academic years unless stated.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

ENGINEERING = "ENGINEERING_TECHNOLOGY"
PLANNING = "PLANNING"
APPLIED_ARTS = "APPLIED_ARTS_CRAFTS"
DESIGN = "DESIGN"
HMCT = "HMCT"
COMPUTER_APPLICATIONS = "COMPUTER_APPLICATIONS"
MANAGEMENT = "MANAGEMENT"

_FAMILY_ALIASES = {
    "ENGINEERING": ENGINEERING,
    "ENGINEERING AND TECHNOLOGY": ENGINEERING,
    "ENGINEERING & TECHNOLOGY": ENGINEERING,
    "ENGINEERING_TECHNOLOGY": ENGINEERING,
    "E&T": ENGINEERING,
    "PLANNING": PLANNING,
    "APPLIED ARTS": APPLIED_ARTS,
    "APPLIED ARTS & CRAFTS": APPLIED_ARTS,
    "APPLIED_ARTS_AND_CRAFTS": APPLIED_ARTS,
    "APPLIED_ARTS_CRAFTS": APPLIED_ARTS,
    "DESIGN": DESIGN,
    "HMCT": HMCT,
    "HOTEL MANAGEMENT": HMCT,
    "HOTEL MANAGEMENT AND CATERING TECHNOLOGY": HMCT,
    "COMPUTER APPLICATIONS": COMPUTER_APPLICATIONS,
    "COMPUTER_APPLICATION": COMPUTER_APPLICATIONS,
    "COMPUTER_APPLICATIONS": COMPUTER_APPLICATIONS,
    "MCA": COMPUTER_APPLICATIONS,
    "BCA": COMPUTER_APPLICATIONS,
    "MANAGEMENT": MANAGEMENT,
    "MBA": MANAGEMENT,
    "PGDM": MANAGEMENT,
    "BBA": MANAGEMENT,
}

_LEVEL_ALIASES = {
    "DIPLOMA": "DIPLOMA",
    "POST DIPLOMA": "PG_DIPLOMA",
    "POST_DIPLOMA": "PG_DIPLOMA",
    "PG DIPLOMA": "PG_DIPLOMA",
    "PG_DIPLOMA": "PG_DIPLOMA",
    "UG": "UG",
    "UNDERGRADUATE": "UG",
    "BACHELOR": "UG",
    "PG": "PG",
    "POSTGRADUATE": "PG",
    "POST GRADUATE": "PG",
    "MASTER": "PG",
    "PG DEGREE": "PG",
    "INTEGRATED": "INTEGRATED",
    "DUAL": "INTEGRATED",
    "INTEGRATED_DUAL": "INTEGRATED",
    "FPM": "FPM",
}


def normalise_family(value: str | None) -> str:
    """Return the canonical programme family used by the rule engine."""
    if not value:
        return ENGINEERING
    key = str(value).strip().upper().replace("-", " ")
    return _FAMILY_ALIASES.get(key, key.replace(" ", "_"))


def normalise_level(value: str | None) -> str:
    """Return the canonical programme level used by the rule engine."""
    if not value:
        return "UG"
    key = str(value).strip().upper().replace("-", " ")
    return _LEVEL_ALIASES.get(key, key.replace(" ", "_"))


# ---------------------------------------------------------------------------
# Handbook defaults (editable through ComplianceConfig)
# ---------------------------------------------------------------------------

# APH_SPEC 7.1: faculty:student ratio (students per faculty member).
FSR_RATIOS: dict[str, dict[str, float]] = {
    ENGINEERING: {"DIPLOMA": 25, "UG": 20, "PG": 15, "INTEGRATED": 20, "PG_DIPLOMA": 15},
    PLANNING: {"DIPLOMA": 25, "UG": 16, "PG": 10, "INTEGRATED": 16, "PG_DIPLOMA": 10},
    APPLIED_ARTS: {"DIPLOMA": 25, "UG": 15, "PG": 15, "PG_DIPLOMA": 15},
    DESIGN: {"DIPLOMA": 25, "UG": 15, "PG": 15, "PG_DIPLOMA": 15},
    HMCT: {"DIPLOMA": 25, "UG": 20, "PG": 12, "PG_DIPLOMA": 12},
    COMPUTER_APPLICATIONS: {"DIPLOMA": 25, "UG": 25, "PG": 20, "PG_DIPLOMA": 20},
    MANAGEMENT: {"DIPLOMA": 25, "UG": 25, "PG": 20, "PG_DIPLOMA": 20},
}

# APH_SPEC 7.1 footnote and §12.10: cadre split weights.
CADRE_RATIOS: dict[str, list[int]] = {
    f"{ENGINEERING}|UG": [1, 2, 6],
    f"{ENGINEERING}|PG": [1, 1, 1],
    f"{HMCT}|PG": [1, 1, 1],
    f"{COMPUTER_APPLICATIONS}|PG": [1, 2, 6],
    f"{MANAGEMENT}|PG": [1, 2, 6],
    f"{PLANNING}|UG": [1, 2, 6],
    f"{PLANNING}|PG": [1, 1, 1],
    f"{APPLIED_ARTS}|UG": [1, 2, 6],
    f"{APPLIED_ARTS}|PG": [1, 1, 1],
    f"{DESIGN}|UG": [1, 2, 6],
    f"{DESIGN}|PG": [1, 1, 1],
}
DEFAULT_CADRE_WEIGHTS = [1, 2, 6]

# APH_SPEC 7.3: PCs per student, printers and bandwidth.
PC_RATIOS: dict[str, dict[str, float]] = {
    ENGINEERING: {"DIPLOMA": 10, "UG": 10, "PG": 4, "INTEGRATED": 10},
    PLANNING: {"UG": 6, "PG": 4, "DIPLOMA": 6},
    APPLIED_ARTS: {"DIPLOMA": 6, "UG": 6, "PG": 4},
    DESIGN: {"UG": 6, "PG": 4, "DIPLOMA": 6},
    HMCT: {"DIPLOMA": 6, "UG": 6, "PG": 4},
    COMPUTER_APPLICATIONS: {"UG": 10, "PG": 4, "DIPLOMA": 10},
    MANAGEMENT: {"UG": 10, "PG": 6, "DIPLOMA": 10},
}
MIN_PCS = 20
PRINTER_SHARE = 0.05
LANGUAGE_LAB_PCS_PER_300 = 20

BANDWIDTH_TIERS: list[dict[str, float]] = [
    {"max_intake": 300, "mbps": 100},
    {"max_intake": 600, "mbps": 300},
    {"max_intake": 900, "mbps": 500},
    {"max_intake": None, "mbps": 1000},
]

# APH_SPEC 7.2 / Annexure-3 3.2.
ADMIN_AREA_SQM = 750.0
AMENITIES_AREA_SQM = 500.0
CIRCULATION_FACTOR = 1.25
LIBRARY_BASE_SQM = 400.0
LIBRARY_EXTRA_PER_60_STUDENTS = 50.0
LIBRARY_EXTRA_AFTER_INTAKE = 420.0
CLASSROOM_LARGE_SQM = 66.0
CLASSROOM_SMALL_SQM = 33.0
TUTORIAL_SHARE = 0.25
WORKSHOP_SQM = 200.0
CAD_HALL_SQM = 132.0
COMPUTER_CENTRE_SQM = 150.0
SEMINAR_HALL_SQM = 132.0
LANGUAGE_LAB_SQM = 33.0

# APH_SPEC 7.3 / Annexure-4.
READING_SEAT_SHARE_UG = 0.15
READING_SEAT_SHARE_PG = 0.25
READING_SEAT_MAX_UG = 150
READING_SEAT_MAX_PG = 100
DIGITAL_LIBRARY_PC_SHARE = 0.10
DIGITAL_LIBRARY_PC_MAX = 30
JOURNALS_PER_COURSE_PER_LEVEL = 6


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProgrammeInput:
    """One approved programme in the form the calculators need."""

    family: str
    level: str
    intake: int
    """Annual approved intake per division."""
    duration_years: float
    divisions: int = 1
    course_name: str = ""
    has_pg_course: bool = False

    @property
    def canonical_family(self) -> str:
        return normalise_family(self.family)

    @property
    def canonical_level(self) -> str:
        return normalise_level(self.level)

    @property
    def total_intake(self) -> int:
        """S = approved intake summed across all years of the programme."""
        return max(0, int(round(self.intake * self.duration_years)))

    @property
    def division_size(self) -> int:
        if self.divisions <= 0:
            return self.intake
        return int(round(self.intake / self.divisions)) if self.divisions else self.intake


@dataclass(frozen=True)
class FacultyRequirement:
    """The required faculty establishment for a set of programmes."""

    total_required: int
    required_by_group: dict[str, int]
    professors: int
    associate_professors: int
    assistant_professors: int
    principal_director: int
    heads_of_department: int
    reduced: bool = False
    """True when the 25% reduction for average admission at most 50% applied."""
    groups: dict[str, dict[str, int]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Faculty
# ---------------------------------------------------------------------------


def classroom_divisions(programme: ProgrammeInput) -> int:
    """Return rooms needed by the Annexure-3 formula for one programme."""
    return max(1, math.ceil(programme.divisions * programme.duration_years * 0.5))


def required_faculty(total_intake: int, ratio: float) -> int:
    """Required faculty = ceil(S / ratio) (APH_SPEC 7.1)."""
    if total_intake <= 0 or ratio <= 0:
        return 0
    return math.ceil(total_intake / ratio)


def cadre_split(required: int, weights: Sequence[int] = (1, 2, 6)) -> tuple[int, int, int]:
    """Split a faculty establishment into Professor / Associate / Assistant.

    The handbook states the ratio (1:2:6, i.e. R = 9, for UG and MCA/MBA/PGDM)
    but not how to round a non-multiple. Professors and Associate Professors are
    rounded down and the remainder is assigned to Assistant Professors, so the
    total always equals ``required``. A non-empty establishment always keeps at
    least one Professor because every programme needs one (APH 6.14f); a
    qualified Associate Professor may substitute (APH 7.1).
    """
    if required <= 0:
        return (0, 0, 0)
    weight_values = [max(1, int(weight)) for weight in weights[:3]]
    while len(weight_values) < 3:
        weight_values.append(1)
    total_weight = sum(weight_values)
    professors = required * weight_values[0] // total_weight
    associates = required * weight_values[1] // total_weight
    if professors == 0:
        professors = 1
    assistants = required - professors - associates
    if assistants < 0:
        associates = max(0, associates + assistants)
        assistants = required - professors - associates
    return (professors, associates, assistants)


def _ratio_for(
    family: str,
    level: str,
    ratios: Mapping[str, Mapping[str, float]] | None,
) -> float:
    table = ratios or FSR_RATIOS
    family_table = table.get(family) or table.get(ENGINEERING) or {}
    return float(family_table.get(level) or family_table.get("UG") or 20)


def _cadre_weights_for(
    family: str,
    level: str,
    cadre_ratios: Mapping[str, Sequence[int]] | None,
) -> Sequence[int]:
    table = cadre_ratios or CADRE_RATIOS
    return table.get(f"{family}|{level}") or table.get(f"{family}|UG") or DEFAULT_CADRE_WEIGHTS


def faculty_requirement(
    programmes: Iterable[ProgrammeInput],
    *,
    average_admission_pct: float | None = None,
    fsr_ratios: Mapping[str, Mapping[str, float]] | None = None,
    cadre_ratios: Mapping[str, Sequence[int]] | None = None,
) -> FacultyRequirement:
    """Calculate the required faculty establishment (APH_SPEC 7.1).

    ``average_admission_pct`` is the three-year average admissions as a
    percentage of sanctioned intake. At or below 50% the requirement is
    reduced by 25% (APH 7.1).
    """
    groups: dict[str, dict[str, Any]] = {}
    for programme in programmes:
        family = programme.canonical_family
        level = programme.canonical_level
        key = f"{family}|{level}"
        group = groups.setdefault(
            key,
            {
                "family": family,
                "level": level,
                "total_intake": 0,
                "programmes": 0,
                "divisions": 0,
            },
        )
        group["total_intake"] += programme.total_intake
        group["programmes"] += 1
        group["divisions"] += max(1, programme.divisions)

    reduction = average_admission_pct is not None and average_admission_pct <= 50
    required_by_group: dict[str, int] = {}
    detail: dict[str, dict[str, int]] = {}
    total_required = 0
    professors = associate = assistant = 0
    heads = 0

    for key, group in groups.items():
        ratio = _ratio_for(group["family"], group["level"], fsr_ratios)
        required = required_faculty(group["total_intake"], ratio)
        if reduction:
            required = math.ceil(required * 0.75)
        required_by_group[key] = required
        total_required += required

        if group["level"] == "DIPLOMA":
            # Diploma: one Principal/Director and one HoD per department; the
            # remaining faculty come out of S/25 (APH_SPEC 7.1).
            principal = 1 if required > 0 else 0
            hod = min(group["divisions"], max(0, required - principal))
            batch = max(0, required - principal - hod)
            professors += 0
            associate += 0
            assistant += batch
            heads += hod
            detail[key] = {
                "required": required,
                "principal": principal,
                "hod": hod,
                "professors": 0,
                "associate_professors": 0,
                "assistant_professors": batch,
            }
        else:
            weights = _cadre_weights_for(group["family"], group["level"], cadre_ratios)
            prof, assoc, asst = cadre_split(required, weights)
            professors += prof
            associate += assoc
            assistant += asst
            detail[key] = {
                "required": required,
                "principal": 0,
                "hod": 0,
                "professors": prof,
                "associate_professors": assoc,
                "assistant_professors": asst,
            }

    principal_total = 1 if any(
        group["level"] != "DIPLOMA" and group["total_intake"] > 0
        for group in groups.values()
    ) else 0
    # APH 7.1 lists the Principal/Director as the first Professor slot, not as
    # an extra post, so S/ratio already funds it. Diploma counts it inside
    # S/25. ``principal_director`` is therefore reported, not added.
    return FacultyRequirement(
        total_required=total_required,
        required_by_group=required_by_group,
        professors=professors,
        associate_professors=associate,
        assistant_professors=assistant,
        principal_director=principal_total,
        heads_of_department=heads,
        reduced=reduction,
        groups=detail,
    )


def cadre_compliance(
    professors: int,
    associate_professors: int,
    assistant_professors: int,
    required: int,
    weights: Sequence[int] = (1, 2, 6),
) -> bool:
    """True when the actual cadre mix is at least the required 1:2:6 split.

    Upward substitution is allowed: a surplus of Professors may cover an
    Associate Professor vacancy, because APH 7.1 lets a qualified Associate
    Professor substitute for a Professor and a stronger senior cadre is never a
    shortfall. The establishment must still meet the total and each cumulative
    tier.
    """
    prof, assoc, _asst = cadre_split(required, weights)
    total = professors + associate_professors + assistant_professors
    return (
        required > 0
        and total >= required
        and professors >= prof
        and professors + associate_professors >= prof + assoc
    )


def adjunct_cap(required: int, family: str, level: str) -> dict[str, int]:
    """Adjunct / Professor-of-Practice caps (APH 6.14d).

    Up to 15% of required faculty may be adjunct, but not less than 10% must
    be Professors of Practice. Design allows 20% adjunct and Planning 30%.
    """
    family = normalise_family(family)
    cap_pct = 30 if family == PLANNING else 20 if family == DESIGN else 15
    cap = math.floor(required * cap_pct / 100)
    minimum_practice = math.ceil(required * 0.10)
    return {"cap": cap, "cap_pct": cap_pct, "min_professors_of_practice": minimum_practice}


# ---------------------------------------------------------------------------
# Land and building
# ---------------------------------------------------------------------------


def lease_compliance(
    *,
    land_ownership: str | None,
    lease_years_total: int | None,
    lease_years_live: int | None,
    longest_course_years: float,
) -> dict[str, bool]:
    """Title or lease rules (APH 6.17a, 2.1e).

    Owned land needs a clear title. Leased land needs a total lease of at
    least 30 years and a live lease at least as long as the longest course.
    """
    owned = str(land_ownership or "").upper() in {"OWNED", "GOVERNMENT", "GOVT"}
    if owned:
        return {"title_ok": True, "lease_ok": True, "tenure_ok": True}
    total_ok = lease_years_total is not None and lease_years_total >= 30
    live_ok = (
        lease_years_live is not None
        and lease_years_live >= math.ceil(longest_course_years)
    )
    return {
        "title_ok": False,
        "lease_ok": bool(total_ok and live_ok),
        "tenure_ok": bool(total_ok and live_ok),
    }


def plot_compliance(
    plots: Sequence[Mapping[str, Any]],
    *,
    max_plots: int = 3,
    max_distance_km: float = 2.0,
    contiguous: bool | None = None,
    obstacles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Land parcel rules (APH 6.17d, Annexure-3 3.1g-h)."""
    distances = [
        float(plot.get("distance_km") or 0)
        for plot in plots
        if plot.get("distance_km") is not None
    ]
    return {
        "plot_count": len(plots),
        "plots_ok": 1 <= len(plots) <= max_plots,
        "max_distance_km": max(distances) if distances else 0.0,
        "distance_ok": not distances or max(distances) <= max_distance_km,
        "contiguous": bool(contiguous) if contiguous is not None else True,
        "obstacle_count": len([item for item in (obstacles or []) if item]),
    }


# ---------------------------------------------------------------------------
# Area (Annexure-3 3.2)
# ---------------------------------------------------------------------------


def instructional_area(
    programmes: Iterable[ProgrammeInput],
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Instructional area for the Engineering & Technology formula.

    The handbook formula is implemented literally: classrooms are
    ``divisions × duration × 0.5`` rooms at 66 sqm (60-seat division) or
    33 sqm (30-seat division); tutorial rooms are 25% of classrooms at
    33 sqm; workshops, CAD hall, computer centre, seminar hall and library are
    fixed additions. Non-E&T families fall back to the same room formula with
    their own configured additions.
    """
    options = dict(config or {})
    large = float(options.get("classroom_large_sqm", CLASSROOM_LARGE_SQM))
    small = float(options.get("classroom_small_sqm", CLASSROOM_SMALL_SQM))
    tutorial_sqm = float(options.get("tutorial_sqm", CLASSROOM_SMALL_SQM))
    workshop_sqm = float(options.get("workshop_sqm", WORKSHOP_SQM))

    classrooms = tutorials = labs = workshops = 0.0
    total_intake = sum(programme.total_intake for programme in programmes)
    programme_list = list(programmes)
    for programme in programme_list:
        rooms = classroom_divisions(programme)
        room_area = large if programme.division_size >= 60 else small
        classrooms += rooms * room_area
        tutorials += math.ceil(rooms * TUTORIAL_SHARE) * tutorial_sqm
        if programme.canonical_family == ENGINEERING:
            if programme.canonical_level in {"UG", "DIPLOMA"}:
                labs += 4 * large  # first-year labs (incl. two basic science)
                if programme.intake <= 180:
                    labs += 2 * programme.duration_years * large
                if programme.canonical_level == "UG":
                    workshops += workshop_sqm
            elif programme.canonical_level == "PG":
                labs += 2 * large  # PG lab + research lab
        else:
            labs += 2 * programme.duration_years * large

    if total_intake > 600:
        workshops += workshop_sqm  # one extra workshop for 601-1200
    fixed = {
        "cad_hall": CAD_HALL_SQM if any(
            programme.canonical_family == ENGINEERING for programme in programme_list
        ) else 0.0,
        "computer_centre": COMPUTER_CENTRE_SQM,
        "seminar_hall": SEMINAR_HALL_SQM,
        "library": LIBRARY_BASE_SQM
        + max(0.0, math.ceil((total_intake - LIBRARY_EXTRA_AFTER_INTAKE) / 60))
        * LIBRARY_EXTRA_PER_60_STUDENTS,
        "language_lab": LANGUAGE_LAB_SQM,
    }
    total = classrooms + tutorials + labs + workshops + sum(fixed.values())
    return {
        "classrooms": round(classrooms, 2),
        "tutorial_rooms": round(tutorials, 2),
        "labs": round(labs, 2),
        "workshops": round(workshops, 2),
        **{key: round(value, 2) for key, value in fixed.items()},
        "total": round(total, 2),
    }


def required_built_up_area(
    instructional_sqm: float,
    *,
    administrative_sqm: float | None = None,
    amenities_sqm: float | None = None,
    circulation_factor: float | None = None,
) -> dict[str, float]:
    """Built-up area = (instructional + administrative + amenities) + ~25% (Annexure-3 3.2)."""
    admin = ADMIN_AREA_SQM if administrative_sqm is None else administrative_sqm
    amenities = AMENITIES_AREA_SQM if amenities_sqm is None else amenities_sqm
    factor = CIRCULATION_FACTOR if circulation_factor is None else circulation_factor
    base = instructional_sqm + admin + amenities
    return {
        "instructional": round(instructional_sqm, 2),
        "administrative": round(admin, 2),
        "amenities": round(amenities, 2),
        "base": round(base, 2),
        "circulation": round(base * (factor - 1), 2),
        "total": round(base * factor, 2),
    }


# ---------------------------------------------------------------------------
# Library, computing and internet
# ---------------------------------------------------------------------------


def library_requirement(
    programmes: Sequence[ProgrammeInput],
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Titles, volumes, journals and reading seats (APH_SPEC 7.3 / Annexure-4)."""
    options = dict(config or {})
    titles = 0
    volumes = 0
    journals = 0
    reading_seats = 0
    digital_pcs = 0
    total_students = 0
    for programme in programmes:
        family = programme.canonical_family
        level = programme.canonical_level
        divisions = max(1, programme.divisions)
        students = programme.total_intake
        total_students += students
        later_years = max(0, int(programme.duration_years) - 1)
        if level == "PG":
            first_year_titles = 100 if family in {MANAGEMENT, COMPUTER_APPLICATIONS} else 50
            titles_for_programme = first_year_titles + 50 * later_years
            volumes_for_programme = 4 * titles_for_programme * divisions
            reading_seats += min(
                READING_SEAT_MAX_PG,
                math.ceil(students * READING_SEAT_SHARE_PG),
            )
        elif level == "DIPLOMA":
            first_year_titles = 50
            titles_for_programme = first_year_titles + 50 * later_years
            volumes_for_programme = 5 * titles_for_programme * divisions
            reading_seats += min(
                READING_SEAT_MAX_UG,
                math.ceil(students * READING_SEAT_SHARE_UG),
            )
        else:
            first_year_titles = 50 if family in {MANAGEMENT, COMPUTER_APPLICATIONS} else 100
            titles_for_programme = first_year_titles + 50 * later_years
            volumes_for_programme = 5 * titles_for_programme * divisions
            reading_seats += min(
                READING_SEAT_MAX_UG,
                math.ceil(students * READING_SEAT_SHARE_UG),
            )
        titles += titles_for_programme
        volumes += volumes_for_programme
        journals += JOURNALS_PER_COURSE_PER_LEVEL

    digital_pcs = min(
        DIGITAL_LIBRARY_PC_MAX,
        math.ceil(total_students * DIGITAL_LIBRARY_PC_SHARE),
    )
    return {
        "titles": float(titles),
        "volumes": float(volumes),
        "journals": float(journals),
        "reading_seats": float(reading_seats),
        "digital_library_pcs": float(digital_pcs),
        "students": float(total_students),
        **{
            key: float(value)
            for key, value in options.items()
            if isinstance(value, (int, float))
        },
    }


def pc_requirement(
    programmes: Sequence[ProgrammeInput],
    *,
    pc_ratios: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, int]:
    """Required computers, printers and language-lab PCs (APH_SPEC 7.3)."""
    required = 0
    for programme in programmes:
        table = (pc_ratios or PC_RATIOS).get(programme.canonical_family, {})
        ratio = float(table.get(programme.canonical_level) or table.get("UG") or 10)
        required += math.ceil(programme.total_intake / ratio) if ratio > 0 else 0
    required = max(MIN_PCS, required)
    annual_intake = sum(programme.intake for programme in programmes)
    return {
        "pcs": required,
        "printers": math.ceil(required * PRINTER_SHARE),
        "language_lab_pcs": max(
            LANGUAGE_LAB_PCS_PER_300,
            math.ceil(annual_intake / 300) * LANGUAGE_LAB_PCS_PER_300,
        ),
    }


def bandwidth_requirement(
    intake: int,
    tiers: Sequence[Mapping[str, Any]] | None = None,
) -> int:
    """Required internet bandwidth in Mbps by approved intake (APH_SPEC 7.3)."""
    for tier in tiers or BANDWIDTH_TIERS:
        max_intake = tier.get("max_intake")
        if max_intake is None or intake <= float(max_intake):
            return int(float(tier.get("mbps") or 0))
    return 1000


# ---------------------------------------------------------------------------
# Documents, admission and enrolment
# ---------------------------------------------------------------------------


def structural_certificate_required(
    completion_year: int | None,
    reference_date: date,
    *,
    building_age_threshold: int = 30,
) -> bool:
    """A structural stability certificate is required after 30 years (APH 6.17h)."""
    if completion_year is None:
        return False
    return reference_date.year - int(completion_year) >= building_age_threshold


def certificate_valid(valid_until: date | None, reference_date: date) -> bool:
    """True when a certificate exists and has not expired."""
    return valid_until is not None and valid_until >= reference_date


def longest_course_duration(programmes: Iterable[ProgrammeInput]) -> float:
    """Longest course duration in years; used by the lease rule."""
    return max((programme.duration_years for programme in programmes), default=0.0)


def reduced_enrolment_trigger(
    ledger: Sequence[Mapping[str, Any]],
    *,
    threshold_pct: float = 30.0,
    years: int = 5,
) -> dict[str, Any]:
    """Reduced-enrolment rule (APH 6.12a).

    ``ledger`` rows need ``academic_year``, ``approved_intake`` and
    ``admitted_total``. The trigger fires when each of the preceding five
    years is below 30% of the approved intake.
    """
    ordered = sorted(
        ledger[:years],
        key=lambda row: str(row.get("academic_year") or ""),
        reverse=True,
    )
    percentages = []
    for row in ordered:
        approved = float(row.get("approved_intake") or 0)
        admitted = float(row.get("admitted_total") or 0)
        percentages.append(round(admitted / approved * 100, 2) if approved else 0.0)
    return {
        "trigger": len(percentages) == years
        and all(value < threshold_pct for value in percentages),
        "years_below": sum(value < threshold_pct for value in percentages),
        "percentages": percentages,
    }


def excess_admission(ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Largest excess admission across recorded years (APH 7.4g)."""
    worst = 0
    for row in ledger:
        allowed = (
            int(row.get("approved_intake") or 0)
            + int(row.get("fn_oci") or 0)
            + int(row.get("lateral") or 0)
        )
        excess = int(row.get("admitted_total") or 0) - allowed
        worst = max(worst, excess)
    return {"max_excess": max(0, worst), "exceeds": worst > 0}
