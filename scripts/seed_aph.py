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
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "backend" / "seeds" / "aph"

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
        "apH_clause": "APH 2.10",
        "needs_verification": False,
    },
    {
        "type": "OFF_CAMPUS",
        "label": "Off-campus institution",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.11",
        "needs_verification": False,
    },
    {
        "type": "FPM",
        "label": "Fellow Programme in Management",
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
        "type": "COURSE_RENAME_MERGE_REDUCTION",
        "label": "Change of course name, merger of courses or reduction in intake",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 2.18",
        "needs_verification": False,
    },
    {
        "type": "COLLABORATION_TWINNING",
        "label": "Collaboration and twinning programme",
        "category": "CAT1_CUTOFF",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": True,
        "no_ter": False,
        "year_round": False,
        "apH_clause": "APH 3.2a",
        "needs_verification": False,
    },
    # Category 2: year-round.
    {
        "type": "CHANGE_OF_SITE",
        "label": "Change of site or location",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 2.17",
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
        "no_ter": True,
        "year_round": True,
        "apH_clause": "APH 2.21",
        "needs_verification": False,
    },
    {
        "type": "WOMEN_COED_CONVERSION",
        "label": "Conversion of a women's institution into co-ed and vice versa",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 2.15",
        "needs_verification": False,
    },
    {
        "type": "CLOSURE_OF_PROGRAMME",
        "label": "Closure of a programme or course",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 2.18",
        "needs_verification": False,
    },
    {
        "type": "CHANGE_IN_BANK_DETAILS",
        "label": "Change in bank details",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH Annexure-2 2.12",
        "needs_verification": True,
        "note": (
            "Table 2.2 lists the type as year-round, but the main body has no "
            "clause number (section 2.22 is missing). Only Annexure-2 2.12 "
            "describes the documents."
        ),
    },
    {
        "type": "CHANGE_OF_TRUST_NAME",
        "label": "Change of trust, society or company name or address",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": False,
        "requires_hearing_aa": False,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 2.20",
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
        "apH_clause": "APH 2.1a",
        "needs_verification": False,
    },
    {
        "type": "DEEMED_UNIVERSITY_CONVERSION",
        "label": "Institution converted to a deemed university",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH Table 2.2",
        "needs_verification": True,
        "note": (
            "Table 2.2 lists the type but the handbook gives no dedicated "
            "clause for the conversion itself; Chapter IV applies."
        ),
    },
    {
        "type": "ODL_ONLINE",
        "label": "ODL and online courses",
        "category": "CAT2_YEAR_ROUND",
        "requires_self_disclosure": False,
        "requires_scrutiny": True,
        "requires_evc": True,
        "requires_hearing_aa": True,
        "nil_deficiency_required": False,
        "no_ter": False,
        "year_round": True,
        "apH_clause": "APH 5.3",
        "needs_verification": False,
    },
]


# ---------------------------------------------------------------------------
# Section 4: fee schedules (integer paise)
# ---------------------------------------------------------------------------

FEE_SCHEDULES: list[dict[str, Any]] = [
    {
        "item_code": "PORTAL_USER_ID",
        "label": "Portal user ID",
        "description": "One-time portal user ID fee (APH 1.4.1).",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": rupees(6000),
        "apH_clause": "APH 1.4.1",
    },
    {
        "item_code": "NEW_INSTITUTION_TER",
        "label": "New institution TER",
        "description": "Government, J&K, Ladakh, North East, PwBD or exclusively women.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(1.00),
        "apH_clause": "APH Table 1.1",
    },
    {
        "item_code": "NEW_INSTITUTION_TER",
        "label": "New institution TER",
        "description": "All other institutions, including minority and government-aided.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(10.00),
        "apH_clause": "APH Table 1.1",
    },
    {
        "item_code": "NEW_INSTITUTION_TER_LOR",
        "label": "New institution TER (previous-year final LoR)",
        "description": "Reduced TER for applicants rejected with a final LoR the previous year.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 1.1 iii",
    },
    {
        "item_code": "NEW_INSTITUTION_TER_LOR",
        "label": "New institution TER (previous-year final LoR)",
        "description": "Reduced TER for applicants rejected with a final LoR the previous year.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.00),
        "apH_clause": "APH Table 1.1 iii",
    },
    {
        "item_code": "EOA_SELF_DISCLOSURE",
        "label": "EoA on self-disclosure, per division",
        "description": "All programmes except PGDM/MBA.",
        "institution_class": "GOVT_TYPE",
        "unit": "PER_DIVISION",
        "amount_paise": lakh(0.05),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "EOA_SELF_DISCLOSURE",
        "label": "EoA on self-disclosure, per division",
        "description": "All programmes except PGDM/MBA.",
        "institution_class": "OTHER",
        "unit": "PER_DIVISION",
        "amount_paise": lakh(0.20),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "EOA_SELF_DISCLOSURE_PGDM_MBA",
        "label": "EoA on self-disclosure, per division (PGDM/MBA)",
        "description": "Per division for PGDM and MBA programmes.",
        "institution_class": "GOVT_TYPE",
        "unit": "PER_DIVISION",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "EOA_SELF_DISCLOSURE_PGDM_MBA",
        "label": "EoA on self-disclosure, per division (PGDM/MBA)",
        "description": "Per division for PGDM and MBA programmes.",
        "institution_class": "OTHER",
        "unit": "PER_DIVISION",
        "amount_paise": lakh(0.40),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "LATE_SUBMISSION_PENALTY",
        "label": "Late submission penalty",
        "description": "Payable when an application misses the Public Notice cut-off.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "LATE_SUBMISSION_PENALTY",
        "label": "Late submission penalty",
        "description": "Payable when an application misses the Public Notice cut-off.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(2.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "BREAK_RESTORATION",
        "label": "Break in EoA or restoration of intake",
        "description": "Flat fee for EoA after a break or restoration.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "BREAK_RESTORATION",
        "label": "Break in EoA or restoration of intake",
        "description": "Flat fee for EoA after a break or restoration.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(2.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "OCI_FN_GULF_INTRODUCTION",
        "label": "Introduction of OCI/FN/Gulf seats or off-campus",
        "description": "Flat fee for the first introduction.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "OCI_FN_GULF_INTRODUCTION",
        "label": "Introduction of OCI/FN/Gulf seats or off-campus",
        "description": "Flat fee for the first introduction.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(6.00),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "OCI_FN_GULF_CONTINUATION",
        "label": "Continuation of OCI/FN/Gulf seats, per course",
        "description": "Per-course continuation fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "PER_COURSE",
        "amount_paise": lakh(0.05),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "OCI_FN_GULF_CONTINUATION",
        "label": "Continuation of OCI/FN/Gulf seats, per course",
        "description": "Per-course continuation fee.",
        "institution_class": "OTHER",
        "unit": "PER_COURSE",
        "amount_paise": lakh(0.30),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "FPM_INTRODUCTION",
        "label": "Introduction of Fellow Programme in Management",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "FPM_INTRODUCTION",
        "label": "Introduction of Fellow Programme in Management",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_SITE",
        "label": "Change of site",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_SITE",
        "label": "Change of site",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "DIPLOMA_DEGREE_CONVERSION",
        "label": "Diploma to degree conversion",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "DIPLOMA_DEGREE_CONVERSION",
        "label": "Diploma to degree conversion",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "NEW_PROGRAMME",
        "label": "New programme or level",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "NEW_PROGRAMME",
        "label": "New programme or level",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_TRUST_NAME",
        "label": "Change of trust name",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_TRUST_NAME",
        "label": "Change of trust name",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "MERGER_OF_INSTITUTIONS",
        "label": "Merger of institutions",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "MERGER_OF_INSTITUTIONS",
        "label": "Merger of institutions",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "DEGREE_DIPLOMA_CONVERSION",
        "label": "Degree to diploma conversion",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "DEGREE_DIPLOMA_CONVERSION",
        "label": "Degree to diploma conversion",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "WOMEN_COED_CONVERSION",
        "label": "Women to co-ed conversion",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "WOMEN_COED_CONVERSION",
        "label": "Women to co-ed conversion",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "NRI_SEATS",
        "label": "NRI seats",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "NRI_SEATS",
        "label": "NRI seats",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "INCREASE_INTAKE",
        "label": "Increase in intake or additional course",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "INCREASE_INTAKE",
        "label": "Increase in intake or additional course",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "INTEGRATED_DUAL_DEGREE",
        "label": "Integrated or dual degree",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "INTEGRATED_DUAL_DEGREE",
        "label": "Integrated or dual degree",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "COURSE_RENAME_MERGE_REDUCTION",
        "label": "Course rename, merger, reduction or programme closure",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.10),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "COURSE_RENAME_MERGE_REDUCTION",
        "label": "Course rename, merger, reduction or programme closure",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(0.60),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_INSTITUTION_NAME",
        "label": "Change of institution, affiliating body or type name",
        "description": "Flat fee.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.10),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_OF_INSTITUTION_NAME",
        "label": "Change of institution, affiliating body or type name",
        "description": "Flat fee.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(0.60),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CHANGE_IN_BANK_DETAILS",
        "label": "Change in bank details",
        "description": "Flat fee of Rs 6,000 for both classes.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": rupees(6000),
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "CLOSURE_OF_INSTITUTION",
        "label": "Closure of institution",
        "description": "No TER is charged for closure.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": 0,
        "apH_clause": "APH Table 2.1",
    },
    {
        "item_code": "EXTRA_SCRUTINY_SHC_SAC",
        "label": "Extra Scrutiny, SHC or SAC",
        "description": "Additional committee sitting, including court directions.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.15),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "EXTRA_SCRUTINY_SHC_SAC",
        "label": "Extra Scrutiny, SHC or SAC",
        "description": "Additional committee sitting, including court directions.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(0.60),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "EXTRA_EVC_ONLINE",
        "label": "Extra EVC (online)",
        "description": "Additional online EVC sitting.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "EXTRA_EVC_ONLINE",
        "label": "Extra EVC (online)",
        "description": "Additional online EVC sitting.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "EXTRA_EVC_PHYSICAL",
        "label": "Extra EVC (physical)",
        "description": "Additional physical EVC sitting.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(0.50),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "EXTRA_EVC_PHYSICAL",
        "label": "Extra EVC (physical)",
        "description": "Additional physical EVC sitting.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(2.50),
        "apH_clause": "APH 2.1 note",
    },
    {
        "item_code": "COLLABORATION_INTRODUCTION",
        "label": "Collaboration or twinning introduction",
        "description": "Flat fee from Table 3.1.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(2.00),
        "apH_clause": "APH Table 3.1",
    },
    {
        "item_code": "COLLABORATION_INTRODUCTION",
        "label": "Collaboration or twinning introduction",
        "description": "Flat fee from Table 3.1.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(12.00),
        "apH_clause": "APH Table 3.1",
    },
    {
        "item_code": "COLLABORATION_CONTINUATION",
        "label": "Collaboration or twinning continuation",
        "description": "Flat fee from Table 3.1.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(1.00),
        "apH_clause": "APH Table 3.1",
    },
    {
        "item_code": "COLLABORATION_CONTINUATION",
        "label": "Collaboration or twinning continuation",
        "description": "Flat fee from Table 3.1.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(6.00),
        "apH_clause": "APH Table 3.1",
    },
    {
        "item_code": "UNIVERSITY_TER",
        "label": "University TER",
        "description": "Government-type university.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(2.00),
        "apH_clause": "APH Table 4.1",
    },
    {
        "item_code": "UNIVERSITY_TER",
        "label": "University TER",
        "description": "Private university.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(10.00),
        "apH_clause": "APH Table 4.1",
    },
    {
        "item_code": "UNIVERSITY_TER_LOR",
        "label": "University TER (previous-year final LoR)",
        "description": "Reduced TER for a previous-year final LoR.",
        "institution_class": "GOVT_TYPE",
        "unit": "FLAT",
        "amount_paise": lakh(1.00),
        "apH_clause": "APH Table 4.1",
    },
    {
        "item_code": "UNIVERSITY_TER_LOR",
        "label": "University TER (previous-year final LoR)",
        "description": "Reduced TER for a previous-year final LoR.",
        "institution_class": "OTHER",
        "unit": "FLAT",
        "amount_paise": lakh(4.00),
        "apH_clause": "APH Table 4.1",
    },
    {
        "item_code": "ODL_NEW_HQ_LSC",
        "label": "New ODL headquarters plus up to two LSCs",
        "description": "Applies to an intake of 5,000 or fewer learners.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": lakh(10.00),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_EXISTING_INSTITUTION",
        "label": "New ODL application by an existing approved institution",
        "description": "Flat fee.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": lakh(1.25),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_ADDITIONAL_LSC",
        "label": "Additional Learner Support Centre",
        "description": "Each additional LSC of up to 1,000 learners.",
        "institution_class": None,
        "unit": "PER_LSC",
        "amount_paise": lakh(3.50),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_EOA",
        "label": "ODL EoA",
        "description": "EoA for up to 1,000 learners.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": lakh(2.00),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_NEW_COURSE_INCREASE",
        "label": "New ODL course or increase in seats",
        "description": "Charged per 1,000 seats.",
        "institution_class": None,
        "unit": "PER_1000_SEATS",
        "amount_paise": lakh(2.50),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_LOR",
        "label": "ODL TER (previous-year final LoR)",
        "description": "Reduced TER for a previous-year final LoR.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": lakh(2.50),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "ODL_CLOSURE_RENAME",
        "label": "ODL closure, reduction or rename",
        "description": "Charged per LSC or headquarters.",
        "institution_class": None,
        "unit": "PER_LSC",
        "amount_paise": lakh(0.25),
        "apH_clause": "APH Table 5.5",
    },
    {
        "item_code": "NOC_OTHER_REGULATOR",
        "label": "NOC to run another regulator's courses",
        "description": "Flat fee; Affidavit 12 is also required.",
        "institution_class": None,
        "unit": "FLAT",
        "amount_paise": lakh(0.60),
        "apH_clause": "APH 6.30",
    },
]


# ---------------------------------------------------------------------------
# Section 8: document catalogue
# ---------------------------------------------------------------------------

BASE_DOCUMENTS: list[dict[str, Any]] = [
    {
        "doc_code": "AFFIDAVIT_2",
        "doc_type": "AFFIDAVIT_2",
        "mandatory": True,
        "condition_expr": None,
        "apH_clause": "APH 8",
    },
    {
        "doc_code": "TER_RECEIPT",
        "doc_type": "TER_RECEIPT",
        "mandatory": True,
        "condition_expr": "no_ter == false",
        "apH_clause": "APH 8",
    },
]

NEW_INSTITUTION_DOCUMENTS: list[dict[str, Any]] = [
    ("BUILDING_PLAN_APPROVAL", "ARCHITECT_CERTIFIED_BUILDING_PLAN", True, "APH Annexure-1"),
    ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Format 3"),
    ("OCCUPANCY_CERTIFICATE", "OCCUPANCY_CERTIFICATE", True, "APH Annexure-1"),
    ("FIRE_SAFETY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE", True, "APH Annexure-1"),
    ("BANK_MANAGER_CERTIFICATE", "BANK_MANAGER_CERTIFICATE", True, "APH Certificate 3"),
    ("APPLICATION_HARD_COPY", "APPLICATION_HARD_COPY", True, "APH Annexure-1"),
    ("TRUST_REGISTRATION", "TRUST_REGISTRATION", True, "APH Annexure-1"),
    ("BOG_COMPOSITION", "BOG_COMPOSITION", True, "APH Annexure-17"),
    ("SECTION_8_MOA", "SECTION_8_MOA", False, "APH 1.3.4"),
    ("LAND_OWNERSHIP_DOCUMENT", "LAND_OWNERSHIP_DOCUMENT", True, "APH Annexure-1"),
    ("LAND_LEASE_DEED", "LAND_LEASE_DEED", True, "APH 6.17a"),
    ("JOINT_AFFIDAVIT_7", "JOINT_AFFIDAVIT_7", True, "APH Affidavit 7"),
    ("WORKING_CAPITAL_PROOF", "WORKING_CAPITAL_PROOF", True, "APH Table 1.2"),
    ("AUDITED_ACCOUNTS_3Y", "AUDITED_ACCOUNTS_3Y", True, "APH Annexure-1"),
    ("MINORITY_CERTIFICATE", "MINORITY_CERTIFICATE", False, "APH Annexure-1"),
    ("DETAILED_PROJECT_REPORT", "DETAILED_PROJECT_REPORT", True, "APH Annexure-1"),
    ("NO_HT_LINE_UNDERTAKING", "NO_HT_LINE_UNDERTAKING", True, "APH Annexure-1"),
    ("AFFILIATION_CERTIFICATE", "AFFILIATION_CERTIFICATE", True, "APH Annexure-1"),
    ("FACULTY_DETAILS", "FACULTY_DETAILS", True, "APH Annexure-5"),
    ("FINANCIAL_STATEMENT", "FINANCIAL_STATEMENT", True, "APH Annexure-1"),
    ("MANDATORY_DISCLOSURE", "MANDATORY_DISCLOSURE", True, "APH Annexure-18"),
    ("NAAC_NBA_CERTIFICATE", "NAAC_NBA_CERTIFICATE", False, "APH Annexure-1"),
]

EXISTING_INSTITUTION_DOCUMENTS: list[dict[str, Any]] = [
    ("OCCUPANCY_CERTIFICATE", "OCCUPANCY_CERTIFICATE", True, "APH Annexure-2.1"),
    (
        "STRUCTURAL_STABILITY_CERTIFICATE",
        "STRUCTURAL_STABILITY_CERTIFICATE",
        True,
        "APH 6.17h",
    ),
    ("FIRE_SAFETY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE", True, "APH Annexure-2.1"),
    ("SATELLITE_MAP", "SATELLITE_MAP", True, "APH Annexure-2.1"),
    ("AUDITED_ACCOUNTS_PREVIOUS_YEAR", "AUDITED_ACCOUNTS", True, "APH Annexure-2.1"),
    ("AFFILIATION_CERTIFICATE", "AFFILIATION_CERTIFICATE", True, "APH Annexure-2.1"),
    ("FACULTY_DETAILS", "FACULTY_DETAILS", True, "APH Annexure-5"),
    ("MANDATORY_DISCLOSURE", "MANDATORY_DISCLOSURE", True, "APH Annexure-18"),
]

TYPE_SPECIFIC_DOCUMENTS: dict[str, list[tuple[str, str, bool, str]]] = {
    "NRI_SEATS": [("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.8a")],
    "CHANGE_OF_SITE": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH Format 2"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Format 3"),
    ],
    "WOMEN_COED_CONVERSION": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH Format 2"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Format 3"),
    ],
    "NEW_PROGRAMME": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH Format 2"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Format 3"),
    ],
    "MERGER_OF_INSTITUTIONS": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH Format 2"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Format 3"),
        ("LEGAL_MERGER_DOCUMENTS", "LEGAL_MERGER_DOCUMENTS", True, "APH 2.13"),
    ],
    "SUPERNUMERARY_FN_OCI": [
        ("HOSTEL_DETAILS", "HOSTEL_DETAILS", True, "APH 2.9"),
        ("INTERNATIONAL_AFFAIRS_OFFICE", "INTERNATIONAL_AFFAIRS_OFFICE", True, "APH 2.9"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.9"),
    ],
    "INCREASE_INTAKE": [
        ("AFFIDAVIT_8", "AFFIDAVIT_8", True, "APH Affidavit 8"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.6"),
    ],
    "FPM": [
        ("AFFIDAVIT_8", "AFFIDAVIT_8", True, "APH 2.12"),
        ("PHD_FACULTY_PROOF", "PHD_FACULTY_PROOF", True, "APH 2.12"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.12"),
    ],
    "CLOSURE_OF_INSTITUTION": [
        ("NOC_ALTERNATIVE_ARRANGEMENTS", "NOC_ALTERNATIVE_ARRANGEMENTS", True, "APH 2.21"),
        ("SALARY_SHEET", "SALARY_SHEET", True, "APH 2.21"),
        ("FSR_DETAILS", "FSR_DETAILS", True, "APH 2.21"),
        ("RPGF_FDR_DETAILS", "RPGF_FDR_DETAILS", True, "APH 2.21"),
        ("STUDENT_STATUS", "STUDENT_STATUS", True, "APH 2.21"),
        ("FACULTY_STATUS", "FACULTY_STATUS", True, "APH 2.21"),
        ("AFFIDAVIT_4", "AFFIDAVIT_4", True, "APH Affidavit 4"),
        ("LITIGATION_DECLARATION", "LITIGATION_DECLARATION", True, "APH 2.21"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.21"),
    ],
    "CHANGE_OF_TRUST_NAME": [
        ("REGISTRAR_APPROVAL", "REGISTRAR_APPROVAL", True, "APH 2.20"),
        ("AFFIDAVIT_10", "AFFIDAVIT_10", True, "APH Affidavit 10"),
        ("TRUST_REGISTRATION", "TRUST_REGISTRATION", True, "APH 2.20"),
        ("BOG_COMPOSITION", "BOG_COMPOSITION", True, "APH Annexure-17"),
        ("SECTION_8_MOA", "SECTION_8_MOA", False, "APH 1.3.4"),
        ("LAND_OWNERSHIP_DOCUMENT", "LAND_OWNERSHIP_DOCUMENT", True, "APH 2.20"),
        ("WORKING_CAPITAL_PROOF", "WORKING_CAPITAL_PROOF", True, "APH 2.20"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.20"),
    ],
    "CHANGE_IN_BANK_DETAILS": [
        ("AFFIDAVIT_9", "AFFIDAVIT_9", True, "APH Affidavit 9"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Annexure-2 2.12"),
        ("BANK_MERGER_NOC", "BANK_MERGER_NOC", False, "APH Annexure-2 2.12"),
    ],
    "CHANGE_OF_NAME": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH Format 2"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.19"),
    ],
    "COURSE_RENAME_MERGE_REDUCTION": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH 2.18"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.18"),
    ],
    "CLOSURE_OF_PROGRAMME": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH 2.18"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.18"),
    ],
    "DIPLOMA_DEGREE_CONVERSION": [
        ("AFFILIATING_BODY_NOC_FORMAT_2", "AFFILIATING_BODY_NOC", True, "APH 2.14"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.14"),
    ],
    "INTEGRATED_DUAL_DEGREE": [
        ("AFFIDAVIT_8", "AFFIDAVIT_8", True, "APH 2.10"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH 2.10"),
    ],
    "COLLABORATION_TWINNING": [
        ("FOREIGN_RECOGNITION_LETTER", "FOREIGN_RECOGNITION_LETTER", True, "APH Chapter III"),
        ("MOU", "MOU", True, "APH Chapter III"),
        ("AFFIDAVIT_11", "AFFIDAVIT_11", True, "APH Affidavit 11"),
        ("NBA_NIRF_CERTIFICATE", "NBA_NIRF_CERTIFICATE", True, "APH Chapter III"),
        ("TRUST_RESOLUTION_FORMAT_3", "TRUST_RESOLUTION_FORMAT_3", True, "APH Chapter III"),
    ],
    "ODL_ONLINE": [
        ("AFFIDAVIT_13", "AFFIDAVIT_13", True, "APH Affidavit 13"),
        ("UGC_RECOGNITION", "UGC_RECOGNITION", True, "APH 5.3.8"),
        ("LSC_DETAILS", "LSC_DETAILS", True, "APH Table 5.2"),
    ],
    "EXTENDED_EOA": [
        ("NAAC_CERTIFICATE", "NAAC_CERTIFICATE", True, "APH 2.1a"),
        ("UGC_NOTIFICATION", "UGC_NOTIFICATION", True, "APH 2.1a"),
        ("AFFIDAVIT_5", "AFFIDAVIT_5", True, "APH Affidavit 5"),
    ],
    "UNIVERSITY": [
        ("UGC_NOTIFICATION", "UGC_NOTIFICATION", True, "APH 4.7.1"),
        ("NAAC_CERTIFICATE", "NAAC_CERTIFICATE", True, "APH 4.7.1"),
        ("AFFIDAVIT_5", "AFFIDAVIT_5", True, "APH Affidavit 5"),
    ],
}


def build_required_documents() -> list[dict[str, Any]]:
    """Expand the document catalogue into one row per application type."""
    rows: list[dict[str, Any]] = []
    for route in APPLICATION_TYPE_ROUTES:
        type_code = route["type"]
        if type_code in {"NEW_INSTITUTION", "NEW_INSTITUTION_OTHER_REGULATOR"}:
            base = NEW_INSTITUTION_DOCUMENTS
        elif type_code == "CLOSURE_AND_NEW_INSTITUTION":
            base = NEW_INSTITUTION_DOCUMENTS
        elif type_code == "UNIVERSITY":
            base = NEW_INSTITUTION_DOCUMENTS
        else:
            base = EXISTING_INSTITUTION_DOCUMENTS

        catalogue: list[tuple[str, str, bool, str]] = [
            (doc["doc_code"], doc["doc_type"], doc["mandatory"], doc["apH_clause"])
            for doc in BASE_DOCUMENTS
        ]
        catalogue.extend(base)
        catalogue.extend(TYPE_SPECIFIC_DOCUMENTS.get(type_code, []))

        seen: set[str] = set()
        for doc_code, doc_type, mandatory, clause in catalogue:
            if doc_type in seen:
                continue
            seen.add(doc_type)
            condition = None
            if doc_type == "LAND_OWNERSHIP_DOCUMENT":
                condition = "land_ownership == 'OWNED'"
            elif doc_type in {"LAND_LEASE_DEED", "JOINT_AFFIDAVIT_7"}:
                condition = "land_ownership == 'LEASED'"
            elif doc_type == "STRUCTURAL_STABILITY_CERTIFICATE":
                condition = "building_age_years >= 30"
            elif doc_type == "TER_RECEIPT":
                condition = "no_ter == false"
            rows.append(
                {
                    "application_type": type_code,
                    "doc_code": doc_code,
                    "doc_type": doc_type,
                    "mandatory": mandatory,
                    "condition_expr": condition,
                    "apH_clause": clause,
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Section 1 / Annexure-16: committee compositions
# ---------------------------------------------------------------------------

COMMITTEE_COMPOSITIONS: dict[str, Any] = {
    "SCRUTINY": {
        "label": "Scrutiny Committee",
        "members": [
            {
                "seat": "ACADEMICIAN",
                "role": "Professor/Associate Professor of IIT/IIM/NIT/Govt institution",
                "count": 1,
            },
            {
                "seat": "ADVOCATE",
                "role": "Advocate registered with a Bar Council",
                "count": 1,
            },
            {
                "seat": "ARCHITECT",
                "role": "Architect or Professor/Associate Professor of Civil/Structural",
                "count": 1,
            },
        ],
        "chapter_ii_members": [
            {
                "seat": "ACADEMICIAN",
                "role": "Professor/Associate Professor of IIT/IIM/NIT/Govt institution",
                "count": 2,
            }
        ],
        "quorum": 2,
        "co_opt": "State/UT/affiliating-university representative not below Associate Professor",
        "apH_clause": "APH Annexure-16 16.3-16.4",
        "needs_verification": False,
    },
    "RE_SCRUTINY": {
        "label": "Re-Scrutiny Committee",
        "members": [
            {
                "seat": "ACADEMICIAN",
                "role": "Professor/Associate Professor of IIT/IIM/NIT/Govt institution",
                "count": 1,
            },
            {
                "seat": "ADVOCATE",
                "role": "Advocate registered with a Bar Council",
                "count": 1,
            },
            {
                "seat": "ARCHITECT",
                "role": "Architect or Professor/Associate Professor of Civil/Structural",
                "count": 1,
            },
        ],
        "quorum": 2,
        "scope": "Verifies only the deficiencies listed by the earlier committee",
        "apH_clause": "APH Annexure-16 16.3-16.4",
        "needs_verification": False,
    },
    "EVC": {
        "label": "Expert Visit Committee",
        "members": [
            {
                "seat": "CHAIR",
                "role": "Academician not below Professor from the EC-approved panel",
                "count": 1,
            },
            {
                "seat": "EXPERT",
                "role": "Expert not below Associate Professor or industry expert with 5+ years",
                "count": 1,
            },
            {
                "seat": "ARCHITECT",
                "role": "Architect, CPWD/NBCC/DRDO/CSIR expert, or Professor of Civil/Planning",
                "count": 1,
            },
        ],
        "quorum": 3,
        "co_opt": "State/UT/affiliating-university representative not below Associate Professor",
        "apH_clause": "APH Annexure-16 16.5",
        "needs_verification": False,
    },
    "SHC": {
        "label": "Standing Hearing Committee",
        "members": [
            {
                "seat": "CHAIR",
                "role": (
                    "Retired High Court judge, educationist not below VC, or "
                    "Director of IIT/NIT/IIM"
                ),
                "count": 1,
            },
            {
                "seat": "EXPERT",
                "role": "Expert not below Associate Professor",
                "count": 1,
            },
            {
                "seat": "OFFICER",
                "role": (
                    "Officer not below Deputy Director of Revenue, architect, "
                    "or land/revenue expert"
                ),
                "count": 1,
            },
        ],
        "quorum": 2,
        "apH_clause": "APH Annexure-16 16.6",
        "needs_verification": False,
    },
    "SAC": {
        "label": "Standing Appellate Committee",
        "members": [
            {
                "seat": "CHAIR",
                "role": (
                    "Retired High Court judge, educationist not below VC, or "
                    "Director of IIT/NIT/IIM"
                ),
                "count": 1,
            },
            {
                "seat": "EXPERT",
                "role": "Expert not below Associate Professor",
                "count": 1,
            },
            {
                "seat": "OFFICER",
                "role": (
                    "Officer not below Deputy Director of Revenue, architect, "
                    "or land/revenue expert"
                ),
                "count": 1,
            },
        ],
        "quorum": 2,
        "apH_clause": "APH Annexure-16 16.6",
        "needs_verification": False,
    },
    "SCSC": {
        "label": "Standing Complaint Scrutiny Committee",
        "members": [
            {"seat": "CHAIR", "role": "Retired High Court judge", "count": 1},
            {
                "seat": "EXPERT",
                "role": "Expert not below Associate Professor",
                "count": 2,
            },
            {"seat": "ARCHITECT", "role": "Architect or Professor of Civil", "count": 1},
            {"seat": "OFFICER", "role": "DTE or Registrar", "count": 1},
        ],
        "quorum": 2,
        "apH_clause": "APH Annexure-16 16.7",
        "needs_verification": False,
    },
    "EC": {
        "label": "Executive Committee",
        "members": [
            {"seat": "CHAIR", "role": "Chairman", "count": 1},
            {"seat": "VICE_CHAIR", "role": "Vice-Chairman", "count": 1},
            {
                "seat": "MEMBER",
                "role": "Secretary, Ministry of Education and other members",
                "count": 1,
            },
        ],
        "quorum": "one third",
        "apH_clause": "APH Annexure-16 16.2",
        "needs_verification": False,
    },
    "COUNCIL": {
        "label": "Council",
        "members": [{"seat": "MEMBER", "role": "Council members", "count": 51}],
        "quorum": None,
        "apH_clause": "APH Annexure-16 16.1",
        "needs_verification": False,
    },
}


# ---------------------------------------------------------------------------
# Section 5: demo Public Notice and Academic Calendar values
# ---------------------------------------------------------------------------

DEMO_ACADEMIC_YEAR = "2026-27"

PUBLIC_NOTICES: list[dict[str, Any]] = [
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "category": "CAT1_CUTOFF",
        "opens_on": "2026-03-01",
        "cutoff_on": "2026-04-30",
        "apH_clause": "APH 1.2",
        "needs_verification": True,
        "is_demo": True,
        "note": (
            "DEMO ONLY. The handbook does not publish cut-off dates; replace "
            "with the AICTE Public Notice for the academic year."
        ),
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "category": "CAT2_YEAR_ROUND",
        "opens_on": "2026-03-01",
        "cutoff_on": "2027-03-31",
        "apH_clause": "APH Table 2.2",
        "needs_verification": True,
        "is_demo": True,
        "note": (
            "DEMO ONLY. Category 2 types are processed year-round; the end date "
            "is illustrative and must be replaced with the Public Notice."
        ),
    },
]

ACADEMIC_CALENDAR_EVENTS: list[dict[str, Any]] = [
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "LAST_DATE_EOA",
        "date": "2026-06-30",
        "description": "Illustrative last date for issue of EoA (not in the handbook).",
        "apH_clause": "APH 2.25j",
        "needs_verification": True,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "ENROLMENT_UPLOAD_30NOV",
        "date": "2026-11-30",
        "description": "Student enrolment details uploaded before 30 November.",
        "apH_clause": "APH 2.25n",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "NOMENCLATURE_30NOV",
        "date": "2026-11-30",
        "description": "New course nomenclature concurrence before 30 November.",
        "apH_clause": "APH 5.3.11",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "SD_PENALTY10_31MAY",
        "date": "2027-05-31",
        "description": "Security Deposit 10% penalty window closes.",
        "apH_clause": "APH 2.25f",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "SD_PENALTY20_31JUL",
        "date": "2027-07-31",
        "description": "Security Deposit 20% penalty window closes.",
        "apH_clause": "APH 2.25f",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "IC_REPORT_30JUN",
        "date": "2027-06-30",
        "description": "Internal Committee annual report upload.",
        "apH_clause": "APH 6.48g",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "CLOSURE_REVOKE_10APR",
        "date": "2027-04-10",
        "description": "Last date to withdraw a pending closure application.",
        "apH_clause": "APH 2.3.3g",
        "needs_verification": False,
        "is_demo": True,
    },
    {
        "academic_year": DEMO_ACADEMIC_YEAR,
        "event_key": "RESTORATION_30APR",
        "date": "2027-04-30",
        "description": "Restoration approved after 30 April applies to the next academic year.",
        "apH_clause": "APH 7.12",
        "needs_verification": False,
        "is_demo": True,
    },
]


def _write(name: str, payload: Any) -> None:
    path = OUTPUT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    """Write every APH seed file."""
    _write("application_type_routes.json", APPLICATION_TYPE_ROUTES)
    _write("fee_schedules.json", FEE_SCHEDULES)
    _write("required_documents.json", build_required_documents())
    _write("committee_compositions.json", COMMITTEE_COMPOSITIONS)
    _write("public_notices.json", PUBLIC_NOTICES)
    _write("academic_calendar_events.json", ACADEMIC_CALENDAR_EVENTS)


if __name__ == "__main__":
    main()
