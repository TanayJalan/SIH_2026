"""Unit tests for the pure APH fee, refund and Security Deposit calculator."""

from datetime import date
from decimal import Decimal

import pytest

from app.services.fee_calculator import (
    LAKH_PAISE,
    SecurityDepositPenaltyWindows,
    annual_multiplier,
    apply_annual_increase,
    compute_committee_charge,
    compute_late_penalty,
    compute_line,
    compute_refund,
    refund_after_revocation,
    refund_after_scrutiny_rejection,
    security_deposit_amount,
    security_deposit_penalty,
    security_deposit_total,
    units_for,
)


def test_annual_multiplier_compounds_each_academic_year() -> None:
    assert annual_multiplier("2026-27", "2026-27", Decimal("10")) == Decimal("1")
    assert annual_multiplier("2026-27", "2027-28", Decimal("10")) == Decimal("1.10")
    assert annual_multiplier("2026-27", "2028-29", Decimal("10")) == Decimal("1.21")
    assert apply_annual_increase(
        2_000_000,
        base_academic_year="2026-27",
        target_academic_year="2028-29",
        annual_increase_pct=Decimal("10"),
    ) == 2_420_000


def test_eoa_self_disclosure_is_charged_per_division() -> None:
    """APH Table 2.1: Rs 0.20 lakh per division for all other institutions."""
    assert units_for("PER_DIVISION", programme_intakes=(60, 61, 120)) == 1 + 2 + 2
    line = compute_line(
        item_code="EOA_SELF_DISCLOSURE",
        label="EoA on self-disclosure per division",
        unit="PER_DIVISION",
        unit_amount_paise=2_000_000,
        base_academic_year="2026-27",
        target_academic_year="2026-27",
        annual_increase_pct=Decimal("10"),
        programme_intakes=(60, 120),
        apH_clause="APH Table 2.1",
    )
    assert line.units == 3
    assert line.amount_paise == 6_000_000


def test_pgdm_mba_division_rate_is_higher() -> None:
    """APH Table 2.1: Rs 0.15 lakh per PGDM/MBA division for Govt-type."""
    line = compute_line(
        item_code="EOA_SELF_DISCLOSURE_PGDM_MBA",
        label="EoA per division PGDM/MBA",
        unit="PER_DIVISION",
        unit_amount_paise=1_500_000,
        base_academic_year="2026-27",
        target_academic_year="2026-27",
        annual_increase_pct=10,
        programme_intakes=(60, 60),
        apH_clause="APH Table 2.1",
    )
    assert line.amount_paise == 3_000_000


def test_oci_continuation_is_charged_per_course() -> None:
    """APH Table 2.1: Rs 0.30 lakh per course for all other institutions."""
    line = compute_line(
        item_code="OCI_FN_GULF_CONTINUATION",
        label="Continuation of OCI/FN/Gulf seats per course",
        unit="PER_COURSE",
        unit_amount_paise=3_000_000,
        base_academic_year="2026-27",
        target_academic_year="2026-27",
        annual_increase_pct=10,
        programme_intakes=(60, 60, 60),
        apH_clause="APH Table 2.1",
    )
    assert line.units == 3
    assert line.amount_paise == 9_000_000


def test_late_submission_penalty_only_applies_when_late() -> None:
    assert (
        compute_late_penalty(
            item_code="LATE_SUBMISSION_PENALTY",
            label="Late submission penalty",
            unit_amount_paise=25_000_000,
            base_academic_year="2026-27",
            target_academic_year="2026-27",
            annual_increase_pct=10,
            is_late=False,
        )
        is None
    )
    line = compute_late_penalty(
        item_code="LATE_SUBMISSION_PENALTY",
        label="Late submission penalty",
        unit_amount_paise=25_000_000,
        base_academic_year="2026-27",
        target_academic_year="2026-27",
        annual_increase_pct=10,
        is_late=True,
    )
    assert line is not None
    assert line.amount_paise == 25_000_000


@pytest.mark.parametrize(
    ("item_code", "amount_paise", "expected"),
    [
        ("EXTRA_SCRUTINY_SHC_SAC_OTHER", 6_000_000, 6_000_000),
        ("EXTRA_SCRUTINY_SHC_SAC_GOVT", 1_500_000, 1_500_000),
        ("EXTRA_EVC_ONLINE_OTHER", 12_500_000, 12_500_000),
        ("EXTRA_EVC_PHYSICAL_OTHER", 25_000_000, 25_000_000),
    ],
)
def test_extra_committee_charges_are_flat_per_sitting(
    item_code: str,
    amount_paise: int,
    expected: int,
) -> None:
    line = compute_committee_charge(
        item_code=item_code,
        label=item_code,
        unit_amount_paise=amount_paise,
        base_academic_year="2026-27",
        target_academic_year="2026-27",
        annual_increase_pct=10,
    )
    assert line.units == 1
    assert line.amount_paise == expected


def test_refund_deductions_match_aph() -> None:
    paid = 20_000_000
    assert refund_after_scrutiny_rejection(paid) == paid - 6_000_000
    assert refund_after_revocation(paid) == paid - 2_500_000
    assert compute_refund(paid, "SCRUTINY_REJECTED_NO_APPEAL") == 14_000_000
    assert compute_refund(paid, "REVOKED_AFTER_PAYMENT") == 17_500_000
    assert compute_refund(paid, "EXCESS_PAYMENT") == paid


def test_refund_never_goes_negative() -> None:
    assert refund_after_scrutiny_rejection(1_000_000) == 0
    assert refund_after_revocation(1_000_000) == 0


def test_security_deposit_by_programme_and_level() -> None:
    """APH Table 1.4, in lakh: E&T Diploma 15 / UG 35 / PG 15."""
    assert security_deposit_amount(15 * LAKH_PAISE, leased=False) == 15 * LAKH_PAISE
    assert security_deposit_amount(35 * LAKH_PAISE, leased=False) == 35 * LAKH_PAISE
    assert security_deposit_amount(35 * LAKH_PAISE, leased=True) == 70 * LAKH_PAISE
    assert security_deposit_amount(5 * LAKH_PAISE, leased=False) == 5 * LAKH_PAISE


def test_security_deposit_penalty_windows() -> None:
    windows = SecurityDepositPenaltyWindows()
    created = date(2026, 4, 1)
    assert security_deposit_penalty(created, date(2026, 4, 10), windows) == 0
    assert security_deposit_penalty(created, date(2026, 4, 20), windows) == 10
    assert security_deposit_penalty(created, date(2026, 5, 31), windows) == 10
    assert security_deposit_penalty(created, date(2026, 6, 1), windows) == 20
    assert security_deposit_penalty(created, date(2026, 7, 31), windows) == 20
    assert security_deposit_penalty(created, date(2026, 8, 1), windows) == 20


def test_security_deposit_total_adds_penalty_to_doubled_deposit() -> None:
    assert security_deposit_total(35 * LAKH_PAISE, leased=True, penalty_percent=10) == (
        70 * LAKH_PAISE + 7 * LAKH_PAISE
    )
    with pytest.raises(ValueError):
        security_deposit_total(LAKH_PAISE, leased=False, penalty_percent=15)


def test_units_for_supports_flat_and_lsc_units() -> None:
    assert units_for("FLAT") == 1
    assert units_for("PER_LSC", declared_units=3) == 3
    assert units_for("PER_1000_SEATS", programme_intakes=(1500,)) == 2
    with pytest.raises(ValueError):
        units_for("UNKNOWN")
