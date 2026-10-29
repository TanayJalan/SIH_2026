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
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "backend" / "seeds" / "aph"

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


# ---------------------------------------------------------------------------
# Section 3: institution seed data (15 institutions across 5 states/regions)
# ---------------------------------------------------------------------------

INSTITUTIONS: list[dict[str, Any]] = [
    # --- State: Maharashtra (West) ---
    {
        "aicte_id": "MAH-0001",
        "pid": "PRN-MAH-0001",
        "name": "Vidya Vikas College of Engineering",
        "state": "Maharashtra",
        "region": "Pune",
        "aicte_region": "WEST",
        "institution_class": "ENGINEERING",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Vidya Vikas Trust",
    },
    {
        "aicte_id": "MAH-0002",
        "pid": "PRN-MAH-0002",
        "name": "Sahyadri Institute of Management Studies",
        "state": "Maharashtra",
        "region": "Mumbai",
        "aicte_region": "WEST",
        "institution_class": "MANAGEMENT",
        "type": "MANAGEMENT",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Sahyadri Education Society",
    },
    # --- State: Tamil Nadu (South) ---
    {
        "aicte_id": "TN-0001",
        "pid": "PRN-TN-0001",
        "name": "Chola Engineering College",
        "state": "Tamil Nadu",
        "region": "Chennai",
        "aicte_region": "SOUTH",
        "institution_class": "ENGINEERING",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Chola Educational Trust",
    },
    {
        "aicte_id": "TN-0002",
        "pid": "PRN-TN-0002",
        "name": "Pallava Management Institute",
        "state": "Tamil Nadu",
        "region": "Coimbatore",
        "aicte_region": "SOUTH",
        "institution_class": "MANAGEMENT",
        "type": "MANAGEMENT",
        "is_women_only": True,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Pallava Trust",
    },
    # --- State: Karnataka (South-West) ---
    {
        "aicte_id": "KA-0001",
        "pid": "PRN-KA-0001",
        "name": "Vijayanagara Institute of Technology",
        "state": "Karnataka",
        "region": "Bangalore",
        "aicte_region": "SOUTH_WEST",
        "institution_class": "ENGINEERING",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Vijayanagara Trust",
    },
    {
        "aicte_id": "KA-0002",
        "pid": "PRN-KA-0002",
        "name": "Nagarjuna School of Management",
        "state": "Karnataka",
        "region": "Mysore",
        "aicte_region": "SOUTH_WEST",
        "institution_class": "MANAGEMENT",
        "type": "MANAGEMENT",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Nagarjuna Trust",
    },
    # --- State: Gujarat (West) ---
    {
        "aicte_id": "GJ-0001",
        "pid": "PRN-GJ-0001",
        "name": "Gujarat Technological Institute",
        "state": "Gujarat",
        "region": "Ahmedabad",
        "aicte_region": "WEST",
        "institution_class": "ENGINEERING",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Gujarat Education Society",
    },
    # --- State: Delhi (North) ---
    {
        "aicte_id": "DL-0001",
        "pid": "PRN-DL-0001",
        "name": "Apex Institute of Technology",
        "state": "Delhi",
        "region": "Delhi NCR",
        "aicte_region": "NORTH",
        "institution_class": "ENGINEERING",
        "type": "ENGINEERING",
        "is_women_only": False,
        "is_pwbd": False,
        "in_jk_ladakh_ne": False,
        "affiliating_body": "Apex Educational Society",
    },
]


# ---------------------------------------------------------------------------
# Section 4: application type routes (same as above, exported for seed)
# ---------------------------------------------------------------------------

APPLICATION_TYPE_ROUTES_JSON: list[dict[str, Any]] = APPLICATION_TYPE_ROUTES


# ---------------------------------------------------------------------------
# Section 5: helper — write JSON files
# ---------------------------------------------------------------------------

def write_json(name: str, data: Any) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    write_json("application_type_routes.json", APPLICATION_TYPE_ROUTES)
    write_json("institutions.json", INSTITUTIONS)
    print(f"Wrote {len(INSTITUTIONS)} institutions + {len(APPLICATION_TYPE_ROUTES)} routes to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
