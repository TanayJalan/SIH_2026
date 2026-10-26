"""Pure fee, refund and Security Deposit calculations from APH Table 2.1/1.4.

Every function in this module is deterministic and free of database access so
the money rules can be unit-tested from the worked examples in the handbook.
Database-configured rates are loaded by :mod:`app.services.fees` and passed in
as integer paise; this module only performs the arithmetic.

Money is always integer paise. A lakh is ``10_000_000`` paise.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

LAKH_PAISE = 10_000_000

#: APH Table 2.1 refund deductions (integer paise).
REFUND_DEDUCTION_SCRUTINY_PAISE = 6_000_000
"""Rs. 0.60 lakh retained when an application is rejected at scrutiny (APH 1.4.2h)."""
REFUND_DEDUCTION_REVOCATION_PAISE = 2_500_000
"""Rs. 0.25 lakh retained when an application is revoked after TER payment (APH 2.3.3f)."""


@dataclass(frozen=True, slots=True)
class FeeLine:
    """One priced line in a fee quotation."""

    item_code: str
    label: str
    unit: str
    units: int
    unit_amount_paise: int
    amount_paise: int
    apH_clause: str
    needs_verification: bool = False


@dataclass(frozen=True, slots=True)
class SecurityDepositPenaltyWindows:
    """Penalty clock for a late Security Deposit (APH 2.25f).

    The handbook fixes the windows (15 days, then 10% up to 31 May, then 20% up
    to 31 July). They are parameters so an administrator or a test can move the
    illustrative dates without changing the arithmetic.
    """

    grace_days: int = 15
    first_penalty_until_month: int = 5
    first_penalty_until_day: int = 31
    second_penalty_until_month: int = 7
    second_penalty_until_day: int = 31
    apH_clause: str = "APH 2.25f"


def academic_year_start(academic_year: str) -> int:
    """Return the starting calendar year of an ``YYYY-YY`` academic year."""
    try:
        return int(academic_year.split("-", maxsplit=1)[0])
    except (AttributeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid academic year {academic_year!r}") from exc


def academic_year_span(base_academic_year: str, target_academic_year: str) -> int:
    """Return how many annual increments separate two academic years."""
    return max(
        0,
        academic_year_start(target_academic_year) - academic_year_start(base_academic_year),
    )


def annual_multiplier(
    base_academic_year: str,
    target_academic_year: str,
    annual_increase_pct: Decimal | int | float,
) -> Decimal:
    """Compound the configured annual increase for each year after the base."""
    pct = Decimal(str(annual_increase_pct)) / Decimal("100")
    return (Decimal("1") + pct) ** academic_year_span(base_academic_year, target_academic_year)


def apply_annual_increase(
    amount_paise: int,
    *,
    base_academic_year: str,
    target_academic_year: str,
    annual_increase_pct: Decimal | int | float,
) -> int:
    """Apply the APH annual increase and round to the nearest paise."""
    if amount_paise < 0:
        raise ValueError("amount_paise must not be negative")
    multiplier = annual_multiplier(
        base_academic_year,
        target_academic_year,
        annual_increase_pct,
    )
    return int(
        (Decimal(amount_paise) * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def units_for(
    unit: str,
    *,
    programme_intakes: tuple[int, ...] = (),
    declared_units: int | None = None,
) -> int:
    """Return how many chargeable units a ``FeeUnit`` represents.

    ``PER_DIVISION`` follows APH Table 1.3: one division per 60 seats, with a
    minimum of one division so a draft always quotes a fee. ``PER_COURSE``
    charges one unit per programme. Callers may pass ``declared_units`` when the
    handbook already gives the count (for example learning support centres).
    """
    if declared_units is not None:
        return max(0, declared_units)
    if unit == "FLAT":
        return 1
    if unit == "PER_DIVISION":
        if not programme_intakes:
            return 1
        return sum(max(1, -(-max(0, intake) // 60)) for intake in programme_intakes)
    if unit == "PER_COURSE":
        return max(1, len(programme_intakes))
    if unit == "PER_1000_SEATS":
        total = sum(max(0, intake) for intake in programme_intakes)
        return max(1, -(-total // 1000))
    if unit == "PER_LSC":
        return max(1, len(programme_intakes))
    raise ValueError(f"Unknown fee unit {unit!r}")


def compute_line(
    *,
    item_code: str,
    label: str,
    unit: str,
    unit_amount_paise: int,
    base_academic_year: str,
    target_academic_year: str,
    annual_increase_pct: Decimal | int | float,
    programme_intakes: tuple[int, ...] = (),
    declared_units: int | None = None,
    apH_clause: str,
    needs_verification: bool = False,
) -> FeeLine:
    """Price one fee schedule row for an academic year."""
    units = units_for(unit, programme_intakes=programme_intakes, declared_units=declared_units)
    subtotal = unit_amount_paise * units
    return FeeLine(
        item_code=item_code,
        label=label,
        unit=unit,
        units=units,
        unit_amount_paise=unit_amount_paise,
        amount_paise=apply_annual_increase(
            subtotal,
            base_academic_year=base_academic_year,
            target_academic_year=target_academic_year,
            annual_increase_pct=annual_increase_pct,
        ),
        apH_clause=apH_clause,
        needs_verification=needs_verification,
    )


def compute_late_penalty(
    *,
    item_code: str,
    label: str,
    unit_amount_paise: int,
    base_academic_year: str,
    target_academic_year: str,
    annual_increase_pct: Decimal | int | float,
    is_late: bool,
    apH_clause: str = "APH Table 2.1",
    needs_verification: bool = False,
) -> FeeLine | None:
    """Return the flat late-submission penalty only when the application is late."""
    if not is_late:
        return None
    return compute_line(
        item_code=item_code,
        label=label,
        unit="FLAT",
        unit_amount_paise=unit_amount_paise,
        base_academic_year=base_academic_year,
        target_academic_year=target_academic_year,
        annual_increase_pct=annual_increase_pct,
        apH_clause=apH_clause,
        needs_verification=needs_verification,
    )


def compute_committee_charge(
    *,
    item_code: str,
    label: str,
    unit_amount_paise: int,
    base_academic_year: str,
    target_academic_year: str,
    annual_increase_pct: Decimal | int | float,
    apH_clause: str = "APH 2.1 note",
    needs_verification: bool = False,
) -> FeeLine:
    """Price an additional Scrutiny/SHC/SAC or EVC charge (flat per sitting)."""
    return compute_line(
        item_code=item_code,
        label=label,
        unit="FLAT",
        unit_amount_paise=unit_amount_paise,
        base_academic_year=base_academic_year,
        target_academic_year=target_academic_year,
        annual_increase_pct=annual_increase_pct,
        apH_clause=apH_clause,
        needs_verification=needs_verification,
    )


def refund_after_scrutiny_rejection(paid_paise: int) -> int:
    """Refund TER paid minus Rs. 0.60 lakh when rejected at scrutiny (APH 1.4.2h)."""
    return max(0, paid_paise - REFUND_DEDUCTION_SCRUTINY_PAISE)


def refund_after_revocation(paid_paise: int) -> int:
    """Refund TER paid minus Rs. 0.25 lakh when revoked after payment (APH 2.3.3f)."""
    return max(0, paid_paise - REFUND_DEDUCTION_REVOCATION_PAISE)


def compute_refund(paid_paise: int, reason: str) -> int:
    """Return the refundable amount for a documented refund reason.

    ``SCRUTINY_REJECTED_NO_APPEAL`` and ``REVOKED_AFTER_PAYMENT`` are the two
    handbook deductions. Unknown reasons refund the full amount so a manual
    review can decide.
    """
    if reason == "SCRUTINY_REJECTED_NO_APPEAL":
        return refund_after_scrutiny_rejection(paid_paise)
    if reason == "REVOKED_AFTER_PAYMENT":
        return refund_after_revocation(paid_paise)
    return max(0, paid_paise)


def security_deposit_amount(base_paise: int, *, leased: bool) -> int:
    """Double the Security Deposit for a private leased building or land (Table 1.4)."""
    if base_paise < 0:
        raise ValueError("base_paise must not be negative")
    return base_paise * 2 if leased else base_paise


def security_deposit_penalty(
    created_on: date,
    as_of: date,
    windows: SecurityDepositPenaltyWindows | None = None,
) -> int:
    """Return 0, 10 or 20 percent for the Security Deposit penalty clock (APH 2.25f).

    * within 15 days of intimation: no penalty,
    * after that, up to 31 May: 10 percent,
    * after that, up to 31 July: 20 percent,
    * later: capped at 20 percent (the deposit may then be forfeited or the
      approval withdrawn; that decision is outside this calculator).
    """
    clock = windows or SecurityDepositPenaltyWindows()
    grace_end = created_on + timedelta(days=clock.grace_days)
    if as_of <= grace_end:
        return 0
    first_deadline = date(
        created_on.year,
        clock.first_penalty_until_month,
        clock.first_penalty_until_day,
    )
    if as_of <= first_deadline:
        return 10
    second_deadline = date(
        created_on.year,
        clock.second_penalty_until_month,
        clock.second_penalty_until_day,
    )
    if as_of <= second_deadline:
        return 20
    return 20


def security_deposit_total(
    base_paise: int,
    *,
    leased: bool,
    penalty_percent: int = 0,
) -> int:
    """Return the deposit plus any penalty, in paise."""
    if penalty_percent not in (0, 10, 20):
        raise ValueError("penalty_percent must be 0, 10 or 20")
    deposit = security_deposit_amount(base_paise, leased=leased)
    return deposit + (deposit * penalty_percent // 100)
