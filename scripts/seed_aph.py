#!/usr/bin/env python3
"""Generate the APH seed files from the domain specification.

The script is the single place where APH_SPEC.md is transcribed into machine
readable configuration. It writes JSON files under ``backend/seeds/aph`` which
``app.seed`` loads into the database, so a reviewer can diff the configuration
against the handbook without reading Python.

Run from the repository root::

    python scripts/seed_aph.py

Money is stored as integer paise. Values marked ``DEMO`` are clearly labelled
demo data because the handbook does not publish the actual dates.

Nothing here invents a norm: every row carries an ``apH_clause``. Where the
handbook does not state a value or clause, ``needs_verification`` is true and
the item is listed in ``docs/OPEN_QUESTIONS.md``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "backend" / "seeds" / "aph"
APH_PDF = REPO_ROOT / "docs" / "reference" / "APH_2024-27.pdf"

sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.workflow_catalogue import (  # noqa: E402
    NOT_IMPLEMENTED_TYPES,
    ROUTE_WORKFLOW_KEYS,
    build_workflow_definitions,
)

LAKH = 100_000
"""One lakh rupees."""


def rupees(value: float) -> int:
    """Return rupees expressed in integer paise."""
    return int(round(value * 100))


def lakh(value: float) -> int:
    """Return lakh rupees expressed in integer paise."""
    return int(round(value * LAKH * 100))


# ---------------------------------------------------------------------------
# Section 2: application types and routing (Table 2.2 and 2.3)
# ---------------------------------------------------------------------------

# Every route is bound to one workflow definition. The APH prints the steps for
# each application type (Table 2.3) but not a prototype track name, so this
# mapping is one engineering decision, recorded in docs/OPEN_QUESTIONS.md:
#
#   TRACK_A  Chapter I/IV/V new institution and extension of approval
#   TRACK_B  EoA by self-disclosure
#   TRACK_C  Chapter II changes with scrutiny/EVC/hearing
#   TRACK_D  Year-round simple changes (scrutiny and EC listing only)
WORKFLOW_KEY_BY_TYPE: dict[str, str] = {
    # Track A
    "NEW_INSTITUTION": "TRACK_A",
    "NEW_INSTITUTION_OTHER_REGULATOR": "TRACK_A",
    "CLOSURE_AND_NEW_INSTITUTION": "TRACK_A",
    "UNIVERSITY": "TRACK_A",
    "EOA_AFTER_BREAK": "TRACK_A",
    "DEEMED_UNIVERSITY_CONVERSION": "TRACK_A",
    # Track B
    "EOA_SELF_DISCLOSURE": "TRACK_B",
    "NRI_SEATS": "TRACK_B",
    # Track C
    "DIPLOMA_DEGREE_CONVERSION": "TRACK_C",
    "CHANGE_OF_NAME": "TRACK_C",
    "NEW_PROGRAMME": "TRACK_C",
    "MERGER_OF_INSTITUTIONS": "TRACK_C",
    "SUPERNUMERARY_FN_OCI": "TRACK_C",
    "INCREASE_INTAKE": "TRACK_C",
    "INTEGRATED_DUAL_DEGREE": "TRACK_C",
    "OFF_CAMPUS": "TRACK_C",
    "FPM": "TRACK_C",
    "COURSE_RENAME_MERGE_REDUCTION": "TRACK_C",
    "COLLABORATION_TWINNING": "TRACK_C",
    "EXTENDED_EOA": "TRACK_C",
    # Track D
    "CHANGE_OF_SITE": "TRACK_D",
    "CLOSURE_OF_INSTITUTION": "TRACK_D",
    "WOMEN_COED_CONVERSION": "TRACK_D",
    "CLOSURE_OF_PROGRAMME": "TRACK_D",
    "CHANGE_IN_BANK_DETAILS": "TRACK_D",
    "CHANGE_OF_TRUST_NAME": "TRACK_D",
    "ODL_ONLINE": "TRACK_D",
}

APPLICATION_TYPE_ROUTES: list[dict[str, Any]] = [
    # Chapter I / IV / V variants.
    {
        "type": "NEW_INSTITUTION",
        "label": "New technical institution (Chapter I)",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 1.3.2",
        "needs_verification": False,
    },
    {
        "type": "NEW_INSTITUTION_OTHER_REGULATOR",
        "label": "Institution approved by another regulator, first AICTE approval",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 1.3.3",
        "needs_verification": False,
    },
    {
        "type": "CLOSURE_AND_NEW_INSTITUTION",
        "label": "Closure plus new institution in the same premises",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 1.5.2",
        "needs_verification": False,
    },
    {
        "type": "UNIVERSITY",
        "label": "University (Chapter IV)",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 4.4",
        "needs_verification": False,
    },
    # Category 1: cut-off date in the Public Notice.
    {
        "type": "EOA_SELF_DISCLOSURE",
        "label": "Extension of approval based on self-disclosure",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": True,
        "requires_scrutiny": False,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.5",
        "needs_verification": False,
    },
    {
        "type": "NRI_SEATS",
        "label": "Introduction or continuation of NRI seats",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": True,
        "requires_scrutiny": False,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.8a",
        "needs_verification": False,
    },
    {
        "type": "DIPLOMA_DEGREE_CONVERSION",
        "label": "Conversion of diploma level into degree level and vice versa",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.14",
        "needs_verification": False,
    },
    {
        "type": "CHANGE_OF_NAME",
        "label": "Change of institution, affiliating body or type name",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.19",
        "needs_verification": False,
    },
    {
        "type": "NEW_PROGRAMME",
        "label": "Start a new programme or level in an existing institution",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.7",
        "needs_verification": False,
    },
    {
        "type": "MERGER_OF_INSTITUTIONS",
        "label": "Merger of institutions under the same or a different trust",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.13",
        "needs_verification": False,
    },
    {
        "type": "EOA_AFTER_BREAK",
        "label": "EoA after a break, restoration of intake or hibernation",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.16",
        "needs_verification": False,
    },
    {
        "type": "SUPERNUMERARY_FN_OCI",
        "label": "Supernumerary seats for FN, OCI and Gulf children",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.9",
        "needs_verification": False,
    },
    {
        "type": "INCREASE_INTAKE",
        "label": "Increase in intake or additional course",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.6",
        "needs_verification": False,
    },
    {
        "type": "INTEGRATED_DUAL_DEGREE",
        "label": "Integrated or dual degree course",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.12",
        "needs_verification": False,
    },
    {
        "type": "OFF_CAMPUS",
        "label": "Off-campus programme",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 3.2",
        "needs_verification": False,
    },
    {
        "type": "FPM",
        "label": "PhD (Full-time PhD)",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 5.2",
        "needs_verification": False,
    },
    {
        "type": "COURSE_RENAME_MERGE_REDUCTION",
        "label": "Course rename, merge or reduction",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 3.6",
        "needs_verification": False,
    },
    {
        "type": "COLLABORATION_TWINNING",
        "label": "Collaboration / twinning programme",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 3.8",
        "needs_verification": False,
    },
    # Category 2: year-round.
    {
        "type": "CHANGE_OF_SITE",
        "label": "Change of site",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": False,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 1.7",
        "needs_verification": False,
    },
    {
        "type": "CLOSURE_OF_INSTITUTION",
        "label": "Closure of institution",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 1.6",
        "needs_verification": False,
    },
    {
        "type": "WOMEN_COED_CONVERSION",
        "label": "Women to co-ed conversion",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 1.4",
        "needs_verification": False,
    },
    {
        "type": "CLOSURE_OF_PROGRAMME",
        "label": "Closure of programme",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 1.8",
        "needs_verification": False,
    },
    {
        "type": "CHANGE_IN_BANK_DETAILS",
        "label": "Change in bank details",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": False,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 3.10",
        "needs_verification": False,
    },
    {
        "type": "CHANGE_OF_TRUST_NAME",
        "label": "Change of trust name",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": False,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 3.11",
        "needs_verification": False,
    },
    {
        "type": "EXTENDED_EOA",
        "label": "Extended EoA",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 1.10b",
        "needs_verification": False,
    },
    {
        "type": "DEEMED_UNIVERSITY_CONVERSION",
        "label": "Deemed university conversion",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 5.3",
        "needs_verification": False,
    },
    {
        "type": "ODL_ONLINE",
        "label": "Online/distance learning programme",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 3.5",
        "needs_verification": False,
    },
]

# Attach the prototype workflow binding after the table is written so the route
# definitions above stay a faithful transcription of Table 2.3.
for _route in APPLICATION_TYPE_ROUTES:
    _route["workflow_key"] = WORKFLOW_KEY_BY_TYPE.get(_route["type"], "TRACK_C")


# ---------------------------------------------------------------------------
# Section 3: curated demo institutions reused by named demo scenarios
# ---------------------------------------------------------------------------

INSTITUTIONS: list[dict[str, Any]] = [
    {
        "aicte_id": "MAH-0001",
        "pid": "PRN-MAH-0001",
        "name": "Vidya Vikas College of Engineering (Fictional)",
        "state": "Maharashtra",
        "region": "Pune",
        "aicte_region": "WESTERN",
        "established_year": 2001,
        "institution_class": "GOVT_TYPE",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Vidya Vikas Trust (Fictional)",
    },
    {
        "aicte_id": "MAH-0002",
        "pid": "PRN-MAH-0002",
        "name": "Sahyadri Institute of Management Studies (Fictional)",
        "state": "Maharashtra",
        "region": "Mumbai",
        "aicte_region": "WESTERN",
        "established_year": 2008,
        "institution_class": "OTHER",
        "type": "MANAGEMENT",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Sahyadri Education Society (Fictional)",
    },
    {
        "aicte_id": "TN-0001",
        "pid": "PRN-TN-0001",
        "name": "Chola Engineering College (Fictional)",
        "state": "Tamil Nadu",
        "region": "Chennai",
        "aicte_region": "SOUTHERN",
        "established_year": 1996,
        "institution_class": "OTHER",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Chola Educational Trust (Fictional)",
    },
    {
        "aicte_id": "TN-0002",
        "pid": "PRN-TN-0002",
        "name": "Pallava Management Institute (Fictional)",
        "state": "Tamil Nadu",
        "region": "Coimbatore",
        "aicte_region": "SOUTHERN",
        "established_year": 2010,
        "institution_class": "OTHER",
        "type": "MANAGEMENT",
        "is_women_only": True,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Pallava Trust (Fictional)",
    },
    {
        "aicte_id": "KA-0001",
        "pid": "PRN-KA-0001",
        "name": "Vijayanagara Institute of Technology (Fictional)",
        "state": "Karnataka",
        "region": "Bengaluru",
        "aicte_region": "SOUTH_WESTERN",
        "established_year": 1999,
        "institution_class": "OTHER",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Vijayanagara Trust (Fictional)",
    },
    {
        "aicte_id": "KA-0002",
        "pid": "PRN-KA-0002",
        "name": "Nagarjuna School of Management (Fictional)",
        "state": "Karnataka",
        "region": "Mysuru",
        "aicte_region": "SOUTH_WESTERN",
        "established_year": 2012,
        "institution_class": "OTHER",
        "type": "MANAGEMENT",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Nagarjuna Trust (Fictional)",
    },
    {
        "aicte_id": "GJ-0001",
        "pid": "PRN-GJ-0001",
        "name": "Gujarat Technological Institute (Fictional)",
        "state": "Gujarat",
        "region": "Ahmedabad",
        "aicte_region": "WESTERN",
        "established_year": 2003,
        "institution_class": "GOVT_TYPE",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Gujarat Education Society (Fictional)",
    },
    {
        "aicte_id": "DL-0001",
        "pid": "PRN-DL-0001",
        "name": "Apex Institute of Technology (Fictional)",
        "state": "Delhi",
        "region": "New Delhi",
        "aicte_region": "NORTHERN",
        "established_year": 2005,
        "institution_class": "OTHER",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Apex Educational Society (Fictional)",
    },
]


# ---------------------------------------------------------------------------
# Section 4: demo institution directory (60 fictional institutions)
# ---------------------------------------------------------------------------

# Ten States chosen so every AICTE region is represented. The first two
# entries of each State reuse the original hand-written demo institutions; the
# rest are generated with clearly fictional names. Cities stay inside the
# State so the regional tile map and the State filter have real coverage.
_STATE_PLAN: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("Maharashtra", "WESTERN", "MAH", ("Pune", "Mumbai", "Nagpur", "Nashik", "Kolhapur", "Aurangabad")),
    ("Tamil Nadu", "SOUTHERN", "TN", ("Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Vellore")),
    ("Karnataka", "SOUTH_WESTERN", "KA", ("Bengaluru", "Mysuru", "Mangaluru", "Hubballi", "Belagavi", "Shivamogga")),
    ("Gujarat", "WESTERN", "GJ", ("Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Anand")),
    ("Delhi", "NORTHERN", "DL", ("New Delhi", "Dwarka", "Rohini", "Pitampura", "Janakpuri", "Saket")),
    ("Madhya Pradesh", "CENTRAL", "MP", ("Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar")),
    ("West Bengal", "EASTERN", "WB", ("Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol", "Kharagpur")),
    ("Odisha", "EASTERN", "OD", ("Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Balasore")),
    ("Rajasthan", "NORTH_WESTERN", "RJ", ("Jaipur", "Jodhpur", "Kota", "Udaipur", "Ajmer", "Bikaner")),
    ("Telangana", "SOUTH_CENTRAL", "TS", ("Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam", "Mahbubnagar")),
)

_ENGINEERING_THEMES = (
    "Institute of Engineering and Technology",
    "College of Engineering",
    "Technical Institute",
    "School of Engineering",
)
_MANAGEMENT_THEMES = (
    "Institute of Management Studies",
    "Business School",
    "School of Management",
    "Institute of Business Administration",
)


def _institution_name(city: str, kind: str, index: int) -> str:
    """Return a clearly fictional, deterministic institution name."""
    if kind == "MANAGEMENT":
        theme = _MANAGEMENT_THEMES[index % len(_MANAGEMENT_THEMES)]
    else:
        theme = _ENGINEERING_THEMES[index % len(_ENGINEERING_THEMES)]
    return f"{city} {theme} (Fictional)"


def build_institutions() -> list[dict[str, Any]]:
    """Return 60 fictional institutions across 10 States and all 8 regions.

    Six institutions per State keeps every State visible on the tile map. The
    first two entries of Maharashtra, Tamil Nadu and Karnataka and the first of
    Gujarat and Delhi are the original hand-written demo records so existing
    screenshots and references keep resolving.
    """
    by_state: dict[str, list[dict[str, Any]]] = {}
    for base in INSTITUTIONS:
        by_state.setdefault(base["state"], []).append(dict(base))

    generated: list[dict[str, Any]] = []
    for state, region, prefix, cities in _STATE_PLAN:
        existing = by_state.get(state, [])
        institutions = [dict(item) for item in existing]
        for index in range(len(institutions), 6):
            city = cities[index]
            kind = "MANAGEMENT" if index % 4 == 3 else "ENGINEERING"
            sequence = index + 1
            aicte_id = f"{prefix}-{sequence:04d}"
            institutions.append(
                {
                    "aicte_id": aicte_id,
                    "pid": f"PRN-{aicte_id}",
                    "name": _institution_name(city, kind, index),
                    "state": state,
                    "region": city,
                    "aicte_region": region,
                    "established_year": 1985 + ((index * 7 + sequence * 3) % 35),
                    "institution_class": "GOVT_TYPE" if sequence % 5 == 0 else "OTHER",
                    "type": kind,
                    "is_women_only": sequence % 6 == 0,
                    "is_pwbd": sequence % 11 == 0,
                    "in_jk_ladakh_ne": False,
                    "affiliating_body": f"{city} Education Trust (Fictional)",
                }
            )
        generated.extend(institutions)

    # Keep AICTE IDs unique even when a generated ID collides with a curated one.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for index, item in enumerate(generated):
        if item["aicte_id"] in seen:
            item["aicte_id"] = f"{item['aicte_id']}-{index:02d}"
            item["pid"] = f"PRN-{item['aicte_id']}"
        seen.add(item["aicte_id"])
        unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Section 5: Annexure-11 nomenclature and Annexure-14 competent authorities
# ---------------------------------------------------------------------------

_NOMENCLATURE_SECTIONS: dict[str, tuple[str, str]] = {
    "11.1": ("Diploma", "Engineering and Technology"),
    "11.2": ("Post Diploma", "Engineering and Technology"),
    "11.3": ("UG", "Engineering and Technology"),
    "11.4": ("Minor/Hons", "Emerging/Multidisciplinary"),
    "11.5": ("PG Diploma", "Engineering and Technology"),
    "11.6": ("PG", "Engineering and Technology"),
    "11.7": ("UG", "Planning"),
    "11.8": ("PG", "Planning"),
    "11.9": ("Diploma", "Applied Arts and Crafts"),
    "11.10": ("Post Diploma", "Applied Arts and Crafts"),
    "11.11": ("UG", "Applied Arts and Crafts"),
    "11.12": ("PG", "Applied Arts and Crafts"),
    "11.13": ("UG", "Design"),
    "11.14": ("PG", "Design"),
    "11.15": ("Diploma", "Hotel Management and Catering Technology"),
    "11.16": ("UG", "Hotel Management and Catering Technology"),
    "11.17": ("PG", "Hotel Management and Catering Technology"),
    "11.18": ("UG", "Computer Applications"),
    "11.19": ("UG", "Management"),
}

_ANNEXURE_14_REGIONS = {
    "central region": "CENTRAL",
    "eastern region": "EASTERN",
    "northern region": "NORTHERN",
    "north western region": "NORTH_WESTERN",
    "south central region": "SOUTH_CENTRAL",
    "southern region": "SOUTHERN",
    "south western region": "SOUTH_WESTERN",
    "western region": "WESTERN",
}

_STATE_NORMALISE = {
    "gujrat": "Gujarat",
    "orissa": "Odisha",
    "new delhi": "Delhi",
    "pondicherry": "Puducherry",
    "j&k/ ladakh": "Jammu and Kashmir / Ladakh",
}


def _annexure_pdf() -> Any:
    """Open the handbook PDF, or raise a clear error when it is missing."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - developer environment helper
        raise SystemExit(
            "pdfplumber is required to regenerate the annexure seed files: "
            "pip install pdfplumber"
        ) from exc
    if not APH_PDF.is_file():
        raise SystemExit(f"Handbook PDF not found: {APH_PDF}")
    return pdfplumber.open(APH_PDF)


def parse_nomenclature_courses() -> list[dict[str, Any]]:
    """Parse Annexure-11 from the handbook PDF into course rows.

    Every page of the annexure splits the course list into independent tables,
    one per printed column. Tables are assigned to the sub-section heading that
    sits above them, which keeps the level and programme family correct even
    when a page starts a new sub-section in the middle.
    """
    heading_re = re.compile(r"^\s*(11\.\d+)\s*((?:\([a-z ]\))?)\s*(.+)$")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    with _annexure_pdf() as pdf:
        start = end = None
        for number, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if start is None and "Approved Nomenclature of Courses" in text:
                start = number
            elif start is not None and "ANNEXURE-12" in text:
                end = number
                break
        if start is None or end is None:
            raise SystemExit("Could not locate Annexure-11 in the handbook PDF.")

        current: tuple[str, str, str] | None = None
        for number in range(start, end):
            page = pdf.pages[number]
            headings: list[tuple[float, tuple[str, str, str]]] = []
            for line in page.extract_text_lines():
                match = heading_re.match(line["text"])
                if match:
                    section = match.group(1)
                    marker = re.sub(r"\s+", "", match.group(2))
                    headings.append((line["top"], (section, marker, match.group(3).strip())))
            tables = sorted(page.find_tables(), key=lambda table: (round(table.bbox[1]), table.bbox[0]))
            for table in tables:
                above = [heading for heading in headings if heading[0] <= table.bbox[1] + 2]
                if above:
                    current = max(above, key=lambda heading: heading[0])[1]
                if current is None:
                    continue
                section, marker, _title = current
                level, family = _NOMENCLATURE_SECTIONS.get(section, (None, None))
                if level is None:
                    continue
                # 11.18/11.19 use (a)/(b) to split UG from PG.
                if section in {"11.18", "11.19"}:
                    level = "UG" if "a" in marker.lower() else "PG"
                for row in table.extract():
                    cells = [(cell or "").replace("\n", " ").strip() for cell in row]
                    cells = [cell for cell in cells if cell]
                    if not cells:
                        continue
                    name = re.sub(r"\s+", " ", " ".join(cells)).strip(" ,;-")
                    if not name or name.lower().startswith("course name"):
                        continue
                    if re.fullmatch(r"\d{1,3}", name):
                        continue
                    if len(name) < 3 or name[0].islower():
                        continue
                    key = (level, family, name.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "level": level,
                            "programme_family": family,
                            "course_name": name,
                            "source_section": section,
                            "is_emerging": section == "11.4",
                            "apH_clause": f"APH Annexure-11 {section}",
                            "needs_verification": False,
                        }
                    )
    return sorted(rows, key=lambda row: (row["source_section"], row["level"], row["course_name"]))


def parse_competent_authorities() -> list[dict[str, Any]]:
    """Parse the Annexure-14 State/UT authority table from the PDF.

    The table is split across pages by AICTE region. Rajasthan uses an extended
    eight-column layout and Maharashtra is printed as two rows; both are folded
    into one row per State.
    """
    rows: list[dict[str, Any]] = []
    current_region: str | None = None

    with _annexure_pdf() as pdf:
        start = end = None
        for number, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if start is None and "State Wise Competent Authorities" in text:
                start = number
            elif start is not None and "ANNEXURE-15" in text:
                end = number
                break
        if start is None or end is None:
            raise SystemExit("Could not locate Annexure-14 in the handbook PDF.")

        for number in range(start, end):
            page = pdf.pages[number]
            for table in page.extract_tables():
                for raw in table:
                    if not raw or not raw[0]:
                        continue
                    label = re.sub(r"\s+", " ", raw[0]).strip()
                    key = label.lower()
                    if key in _ANNEXURE_14_REGIONS:
                        current_region = _ANNEXURE_14_REGIONS[key]
                        continue
                    if key in {"state", "approval process handbook"}:
                        continue
                    if current_region is None or len(label) > 60:
                        continue
                    if not any(cell and cell.strip() for cell in raw[1:]):
                        continue
                    state = _STATE_NORMALISE.get(key, label)
                    if key.startswith("maharashtra"):
                        # The handbook prints Maharashtra as Metro and
                        # Urban/Rural rows; fold them into one State entry.
                        state = "Maharashtra"
                    values = [
                        re.sub(r"\s+", " ", cell or "").strip()
                        for cell in raw[1:]
                    ]
                    # Five columns: land use, site plan, building plan, occupation.
                    # Rajasthan's eight-column layout adds area/unit columns.
                    if "Rajasthan" in state and len(values) >= 7:
                        land_use = values[1] or None
                        site_plan = values[2] or None
                        building_plan = values[3] or None
                        occupation = values[6] or None
                    else:
                        land_use = values[0] or None
                        site_plan = values[1] if len(values) > 1 else None
                        building_plan = values[2] if len(values) > 2 else None
                        occupation = values[3] if len(values) > 3 else None
                        site_plan = site_plan or None
                        building_plan = building_plan or None
                        occupation = occupation or None
                    existing = next((row for row in rows if row["state"] == state), None)
                    if existing is not None:
                        # Maharashtra is printed as Metro and Urban/Rural rows.
                        for field, value in (
                            ("land_use_authority", land_use),
                            ("site_plan_authority", site_plan),
                            ("building_plan_authority", building_plan),
                            ("occupation_authority", occupation),
                        ):
                            if value and value not in (existing[field] or ""):
                                existing[field] = (
                                    f"{existing[field]}; {value}" if existing[field] else value
                                )
                        continue
                    rows.append(
                        {
                            "state": state,
                            "aicte_region": current_region,
                            "land_use_authority": land_use,
                            "site_plan_authority": site_plan,
                            "building_plan_authority": building_plan,
                            "occupation_authority": occupation,
                            "source_text": None,
                            "apH_clause": "APH Annexure-14",
                            # Column extraction is automated; a reviewer should
                            # spot-check it against the PDF before production use.
                            "needs_verification": True,
                        }
                    )
    return sorted(rows, key=lambda row: (row["aicte_region"], row["state"]))


# ---------------------------------------------------------------------------
# Section 6: helper — write JSON files
# ---------------------------------------------------------------------------

def write_json(name: str, data: Any) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    institutions = build_institutions()
    nomenclature = parse_nomenclature_courses()
    authorities = parse_competent_authorities()
    write_json("application_type_routes.json", APPLICATION_TYPE_ROUTES)
    write_json("institutions.json", institutions)
    write_json("nomenclature_courses.json", nomenclature)
    write_json("competent_authorities.json", authorities)
    print(
        f"Wrote {len(institutions)} institutions, {len(nomenclature)} courses, "
        f"{len(authorities)} competent authorities and "
        f"{len(APPLICATION_TYPE_ROUTES)} routes to {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()
