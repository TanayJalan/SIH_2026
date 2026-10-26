"""Database-backed fee quotation, payment, refund and reopen service.

The arithmetic lives in :mod:`app.services.fee_calculator`; this module loads
the admin-editable ``fee_schedules`` rows, writes immutable ``fee_transactions``
and keeps the application's TER receipt fields in step.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.models.application import Application
from app.models.application_type_route import ApplicationTypeRoute
from app.models.calendar import PublicNotice
from app.models.enums import (
    ApplicationCategory,
    ApplicationStatus,
    FeeKind,
    InstitutionClass,
    LandOwnership,
    WorkflowAction,
)
from app.models.fee import FeeSchedule, FeeTransaction
from app.models.security_deposit_schedule import SecurityDepositSchedule
from app.models.user import User
from app.schemas.fees import (
    FeeLineRead,
    FeePaymentResultRead,
    FeeQuoteRead,
    FeeTransactionRead,
    RefundRequest,
    RefundResultRead,
    ReopenRequest,
    ReopenResultRead,
    SecurityDepositLineRead,
    SecurityDepositQuoteRead,
)
from app.schemas.workflow import WorkflowActionRequest
from app.services import workflow
from app.services.audit import AuditService
from app.services.fee_calculator import (
    FeeLine,
    compute_committee_charge,
    compute_late_penalty,
    compute_line,
    compute_refund,
    security_deposit_amount,
    security_deposit_penalty,
    security_deposit_total,
)

#: Application type -> FeeSchedule item code. Amounts stay in the database;
#: this map is only the routing between an APH application type and its row.
TER_ITEM_CODES: dict[str, str] = {
    "NEW_INSTITUTION": "NEW_INSTITUTION_TER",
    "NEW_INSTITUTION_OTHER_REGULATOR": "NOC_OTHER_REGULATOR",
    "CLOSURE_AND_NEW_INSTITUTION": "NEW_INSTITUTION_TER",
    "UNIVERSITY": "UNIVERSITY_TER",
    "EOA_SELF_DISCLOSURE": "EOA_SELF_DISCLOSURE",
    "NRI_SEATS": "NRI_SEATS",
    "DIPLOMA_DEGREE_CONVERSION": "DIPLOMA_DEGREE_CONVERSION",
    "CHANGE_OF_NAME": "CHANGE_OF_INSTITUTION_NAME",
    "NEW_PROGRAMME": "NEW_PROGRAMME",
    "MERGER_OF_INSTITUTIONS": "MERGER_OF_INSTITUTIONS",
    "EOA_AFTER_BREAK": "BREAK_RESTORATION",
    "SUPERNUMERARY_FN_OCI": "OCI_FN_GULF_CONTINUATION",
    "INCREASE_INTAKE": "INCREASE_INTAKE",
    "INTEGRATED_DUAL_DEGREE": "INTEGRATED_DUAL_DEGREE",
    "OFF_CAMPUS": "OCI_FN_GULF_INTRODUCTION",
    "FPM": "FPM_INTRODUCTION",
    "COURSE_RENAME_MERGE_REDUCTION": "COURSE_RENAME_MERGE_REDUCTION",
    "COLLABORATION_TWINNING": "COLLABORATION_INTRODUCTION",
    "CHANGE_OF_SITE": "CHANGE_OF_SITE",
    "CLOSURE_OF_INSTITUTION": "CLOSURE_OF_INSTITUTION",
    "WOMEN_COED_CONVERSION": "WOMEN_COED_CONVERSION",
    "CLOSURE_OF_PROGRAMME": "COURSE_RENAME_MERGE_REDUCTION",
    "CHANGE_IN_BANK_DETAILS": "CHANGE_IN_BANK_DETAILS",
    "CHANGE_OF_TRUST_NAME": "CHANGE_OF_TRUST_NAME",
    "EXTENDED_EOA": "NEW_INSTITUTION_TER",
    "DEEMED_UNIVERSITY_CONVERSION": "UNIVERSITY_TER",
    "ODL_ONLINE": "ODL_EOA",
}

_PGDM_MBA_MARKERS = ("mba", "pgdm", "pgcm", "management")
_MANAGEMENT_MARKERS = ("mba", "pgdm", "pgcm", "bba", "bms", "management")
_COMPUTER_APPLICATIONS_MARKERS = ("mca", "bca", "computer application")
_DESIGN_MARKERS = ("design",)
_HMCT_MARKERS = ("hmct", "hotel", "catering", "hospitality")
_PLANNING_MARKERS = ("planning",)
_APPLIED_ARTS_MARKERS = ("applied art", "applied arts", "craft")


@dataclass(frozen=True, slots=True)
class _Schedule:
    """A fee schedule row reduced to the values the calculator needs."""

    item_code: str
    label: str
    unit: str
    amount_paise: int
    base_academic_year: str
    annual_increase_pct: Decimal
    apH_clause: str
    needs_verification: bool


class FeeError(Exception):
    """An expected fee-flow failure with an HTTP representation."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def next_academic_year(academic_year: str) -> str:
    """Return the academic year that follows ``YYYY-YY`` (for example 2026-27 -> 2027-28)."""
    try:
        start = int(academic_year.split("-", maxsplit=1)[0])
    except (AttributeError, ValueError) as exc:
        raise FeeError(422, f"Invalid academic year {academic_year!r}") from exc
    return f"{start + 1}-{str(start + 2)[-2:]}"


def ter_selector_rate(
    db: Session,
    application_type: str,
    institution_class: InstitutionClass,
) -> dict[str, Any] | None:
    """Return the base TER rate used by the application-type selector card.

    The selector shows the per-unit rate (per division, per course or flat) for
    the signed-in institution's fee class. The payable amount is still computed
    per application by :class:`FeeService`.
    """
    item_code = TER_ITEM_CODES.get(application_type)
    if item_code is None:
        return None
    row = db.scalar(
        select(FeeSchedule)
        .where(
            FeeSchedule.item_code == item_code,
            FeeSchedule.institution_class == institution_class,
        )
        .order_by(FeeSchedule.base_academic_year.desc())
    )
    if row is None:
        row = db.scalar(
            select(FeeSchedule)
            .where(
                FeeSchedule.item_code == item_code,
                FeeSchedule.institution_class.is_(None),
            )
            .order_by(FeeSchedule.base_academic_year.desc())
        )
    if row is None:
        return None
    return {
        "item_code": row.item_code,
        "label": row.label,
        "unit": row.unit.value,
        "unit_amount_paise": row.amount_paise,
        "base_academic_year": row.base_academic_year,
        "apH_clause": row.apH_clause,
        "needs_verification": row.needs_verification,
    }


class FeeService:
    """Quote, collect, refund and reopen application fees."""

    def __init__(self, db: Session, audit: AuditService, clock: SimulatedClock) -> None:
        self._db = db
        self._audit = audit
        self._clock = clock

    # ------------------------------------------------------------------
    # Quotation
    # ------------------------------------------------------------------
    def quote(
        self,
        application: Application,
        *,
        now: datetime | None = None,
        extra_scrutiny: bool = False,
        extra_evc_mode: str | None = None,
        force_late: bool = False,
    ) -> FeeQuoteRead:
        """Compute the TER, late penalty and optional extra committee charges."""
        route = self._route(application)
        institution_class = self._institution_class(application)
        now = now or self._clock.now()
        notes: list[str] = []
        lines: list[FeeLine] = []

        if route is not None and route.no_ter:
            notes.append(f"No TER is due for {route.label} (APH 2.21).")
        else:
            item_code = self._ter_item_code(application)
            schedule = self._schedule(item_code, institution_class)
            if schedule is None:
                notes.append(
                    f"No fee schedule is configured for {item_code} and {institution_class.value}; "
                    "the amount must be verified by an administrator."
                )
            else:
                lines.append(self._price_ter(application, schedule))

        late = force_late or application.late_submission or self.is_after_cutoff(
            application, now
        )
        if late and not (route is not None and route.no_ter):
            penalty = self._schedule("LATE_SUBMISSION_PENALTY", institution_class)
            if penalty is not None:
                penalty_line = compute_late_penalty(
                    item_code=penalty.item_code,
                    label=penalty.label,
                    unit_amount_paise=penalty.amount_paise,
                    base_academic_year=penalty.base_academic_year,
                    target_academic_year=application.academic_year,
                    annual_increase_pct=penalty.annual_increase_pct,
                    is_late=True,
                    apH_clause=penalty.apH_clause,
                    needs_verification=penalty.needs_verification,
                )
                if penalty_line is not None:
                    lines.append(penalty_line)

        if extra_scrutiny:
            extra = self._schedule("EXTRA_SCRUTINY_SHC_SAC", institution_class)
            if extra is not None:
                lines.append(
                    compute_committee_charge(
                        item_code=extra.item_code,
                        label=extra.label,
                        unit_amount_paise=extra.amount_paise,
                        base_academic_year=extra.base_academic_year,
                        target_academic_year=application.academic_year,
                        annual_increase_pct=extra.annual_increase_pct,
                        apH_clause=extra.apH_clause,
                        needs_verification=extra.needs_verification,
                    )
                )
        if extra_evc_mode in {"ONLINE", "PHYSICAL"}:
            item_code = f"EXTRA_EVC_{extra_evc_mode}"
            extra = self._schedule(item_code, institution_class)
            if extra is not None:
                lines.append(
                    compute_committee_charge(
                        item_code=extra.item_code,
                        label=extra.label,
                        unit_amount_paise=extra.amount_paise,
                        base_academic_year=extra.base_academic_year,
                        target_academic_year=application.academic_year,
                        annual_increase_pct=extra.annual_increase_pct,
                        apH_clause=extra.apH_clause,
                        needs_verification=extra.needs_verification,
                    )
                )

        total_paise = sum(line.amount_paise for line in lines)
        paid_paise = self._paid_paise(application)
        refunded_paise = self._refunded_paise(application)
        due_paise = max(0, total_paise - paid_paise)
        no_ter = route is not None and route.no_ter
        is_paid = total_paise == 0 or (
            application.ter_paid_at is not None and due_paise == 0
        )
        payment_required = (not no_ter) and total_paise > 0 and not is_paid
        if late:
            notes.append(
                "Submitted after the Public Notice cut-off: the application is flagged as a "
                "late submission, the late penalty applies and it moves to the next academic year "
                "(APH 2.3.2)."
            )
        if application.ter_receipt_no:
            notes.append(f"TER receipt {application.ter_receipt_no} is on record.")

        return FeeQuoteRead(
            application_id=application.id,
            application_no=application.portal_application_no,
            academic_year=application.academic_year,
            institution_class=institution_class.value,
            lines=[FeeLineRead(**asdict(line)) for line in lines],
            total_paise=total_paise,
            paid_paise=paid_paise,
            refunded_paise=refunded_paise,
            due_paise=due_paise,
            is_paid=is_paid,
            late_submission=late,
            ter_receipt_no=application.ter_receipt_no,
            ter_paid_at=application.ter_paid_at,
            payment_required_for_submission=payment_required,
            notes=notes,
        )

    def security_deposit_quote(
        self,
        application: Application,
        *,
        as_of: date | None = None,
    ) -> SecurityDepositQuoteRead:
        """Quote the Table 1.4 deposit for every programme on the application."""
        as_of = as_of or self._clock.now().date()
        institution = application.institution
        leased = bool(
            institution
            and (
                institution.land_ownership == LandOwnership.LEASED
                or institution.building_leased
            )
        )
        intimation = application.security_deposit_due_on
        penalty_percent = (
            security_deposit_penalty(intimation, as_of) if intimation is not None else 0
        )
        lines: list[SecurityDepositLineRead] = []
        notes: list[str] = []
        for programme in application.programs:
            family = _programme_family(programme.program_name, programme.level)
            level = _programme_level(programme.program_name, programme.level)
            schedule = self._security_schedule(family, level)
            if schedule is None:
                notes.append(f"No Security Deposit rate is configured for {family} {level}.")
                continue
            base = schedule.amount_paise
            deposit = security_deposit_amount(base, leased=leased)
            lines.append(
                SecurityDepositLineRead(
                    programme_family=family,
                    level=level,
                    base_paise=base,
                    leased=leased,
                    deposit_paise=deposit,
                    penalty_percent=penalty_percent,
                    total_due_paise=security_deposit_total(
                        base,
                        leased=leased,
                        penalty_percent=penalty_percent,
                    ),
                    apH_clause=schedule.apH_clause,
                    needs_verification=schedule.needs_verification,
                )
            )
        if not institution:
            notes.append("The application has no institution record, so tenure could not be read.")
        if leased:
            notes.append(
                "The deposit is doubled because the building or land is privately leased "
                "(APH Table 1.4)."
            )
        notes.append(
            "Deposit proof and Affidavit 3 are due within 15 days of intimation (APH 2.25f)."
        )
        return SecurityDepositQuoteRead(
            application_id=application.id,
            as_of=as_of,
            intimation_on=intimation,
            lines=lines,
            total_base_paise=sum(line.base_paise for line in lines),
            total_due_paise=sum(line.total_due_paise for line in lines),
            penalty_windows=(
                "15 days: no penalty; up to 31 May: 10%; up to 31 July: 20%; "
                "after that the approval may be withdrawn (APH 2.25f)."
            ),
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Payments and refunds
    # ------------------------------------------------------------------
    def pay_ter(
        self,
        actor: User,
        application: Application,
        *,
        request: Any | None = None,
    ) -> FeePaymentResultRead:
        """Record a simulated TER payment and stamp the application receipt fields."""
        if application.status != ApplicationStatus.DRAFT:
            raise FeeError(409, "TER can only be paid while the application is a draft.")
        quote = self.quote(application)
        if quote.total_paise <= 0:
            raise FeeError(422, "No TER is due for this application type.")
        if quote.is_paid:
            raise FeeError(409, "TER has already been paid for this application.")

        receipt_base = (
            f"TER-{application.academic_year.replace('-', '')}-"
            f"{uuid.uuid4().hex[:10].upper()}"
        )
        transactions: list[FeeTransaction] = []
        for index, line in enumerate(quote.lines, start=1):
            kind = FeeKind.PENALTY if line.item_code == "LATE_SUBMISSION_PENALTY" else FeeKind.TER
            transaction = FeeTransaction(
                application_id=application.id,
                item_code=line.item_code,
                amount_paise=line.amount_paise,
                kind=kind,
                receipt_no=f"{receipt_base}-{index:02d}",
                paid_at=self._clock.now(),
                apH_clause=line.apH_clause,
                needs_verification=line.needs_verification,
            )
            self._db.add(transaction)
            transactions.append(transaction)
        self._db.flush()

        application.ter_amount_paise = quote.total_paise
        application.ter_paid_at = self._clock.now()
        application.ter_receipt_no = transactions[0].receipt_no if transactions else None
        self._audit.log(
            actor,
            "application.fee.ter.pay",
            "Application",
            application.id,
            after={
                "amount_paise": quote.total_paise,
                "receipt_no": application.ter_receipt_no,
                "lines": [line.model_dump(mode="json") for line in quote.lines],
            },
            request=request,
        )
        self._commit()
        refreshed = self.quote(application)
        return FeePaymentResultRead(
            quote=refreshed,
            transactions=[FeeTransactionRead.model_validate(item) for item in transactions],
        )

    def refund(
        self,
        actor: User,
        application: Application,
        payload: RefundRequest,
        *,
        request: Any | None = None,
    ) -> RefundResultRead:
        """Record a refund without adjusting it into any later payment."""
        paid = self._paid_paise(application)
        if paid <= 0:
            raise FeeError(422, "There is no paid TER to refund.")
        refundable = compute_refund(paid, payload.reason)
        retained = paid - refundable
        receipt_no = (
            f"REF-{application.academic_year.replace('-', '')}-"
            f"{uuid.uuid4().hex[:10].upper()}"
        )
        clause = {
            "SCRUTINY_REJECTED_NO_APPEAL": "APH 1.4.2h",
            "REVOKED_AFTER_PAYMENT": "APH 2.3.3f",
            "EXCESS_PAYMENT": "APH Ch VIII 8-10",
        }[payload.reason]
        transaction = FeeTransaction(
            application_id=application.id,
            item_code="TER_REFUND",
            amount_paise=refundable,
            kind=FeeKind.REFUND,
            receipt_no=receipt_no,
            paid_at=self._clock.now(),
            apH_clause=clause,
        )
        self._db.add(transaction)
        self._db.flush()
        self._audit.log(
            actor,
            "application.fee.refund",
            "Application",
            application.id,
            after={
                "reason": payload.reason,
                "refundable_paise": refundable,
                "retained_paise": retained,
                "receipt_no": receipt_no,
                "note": payload.note,
            },
            request=request,
        )
        self._commit()
        return RefundResultRead(
            transaction=FeeTransactionRead.model_validate(transaction),
            refundable_paise=refundable,
            retained_paise=retained,
            note=(
                "Refunds are paid back; they are never adjusted into a later payment "
                "(APH Ch VIII 8-10)."
            ),
        )

    def reopen(
        self,
        actor: User,
        application: Application,
        payload: ReopenRequest,
        *,
        request: Any | None = None,
    ) -> ReopenResultRead:
        """Reopen a submitted application once, with a new TER and late penalty.

        The state change itself goes through the central workflow state machine.
        The fee rows are written first so a failed transition rolls them back in
        the same transaction.
        """
        if application.reopen_count >= 1:
            raise FeeError(409, "An application can be reopened only once (APH 2.3.3d-e).")
        if application.status not in {
            ApplicationStatus.SUBMITTED,
            ApplicationStatus.SCRUTINY,
            ApplicationStatus.DEFICIENCY_COMMUNICATED,
            ApplicationStatus.INSTITUTION_COMPLIANCE,
            ApplicationStatus.RE_SCRUTINY,
        }:
            raise FeeError(409, "Only a submitted application can be reopened.")
        if not payload.late_penalty_acknowledged:
            raise FeeError(422, "The late penalty must be acknowledged before reopening.")

        quote = self.quote(application, force_late=True)
        if quote.total_paise <= 0:
            raise FeeError(422, "A new TER could not be computed for this application.")

        receipt_base = (
            f"REOPEN-{application.academic_year.replace('-', '')}-"
            f"{uuid.uuid4().hex[:10].upper()}"
        )
        transactions: list[FeeTransaction] = []
        for index, line in enumerate(quote.lines, start=1):
            kind = FeeKind.PENALTY if line.item_code == "LATE_SUBMISSION_PENALTY" else FeeKind.TER
            transaction = FeeTransaction(
                application_id=application.id,
                item_code=line.item_code,
                amount_paise=line.amount_paise,
                kind=kind,
                receipt_no=f"{receipt_base}-{index:02d}",
                paid_at=self._clock.now(),
                apH_clause=line.apH_clause,
                needs_verification=line.needs_verification,
            )
            self._db.add(transaction)
            transactions.append(transaction)
        self._db.flush()
        application.ter_amount_paise = quote.total_paise
        application.ter_paid_at = self._clock.now()
        application.ter_receipt_no = transactions[0].receipt_no
        self._audit.log(
            actor,
            "application.fee.reopen.pay",
            "Application",
            application.id,
            after={
                "amount_paise": quote.total_paise,
                "receipt_no": application.ter_receipt_no,
                "reason": payload.reason,
                "trust_resolution_reference": payload.trust_resolution_reference,
            },
            request=request,
        )

        service = workflow.WorkflowService(self._db, self._audit, self._clock)
        service.execute(
            application,
            actor=actor,
            action=WorkflowAction.REOPEN,
            payload=WorkflowActionRequest(comment=payload.reason),
            request=request,
        )
        refreshed = self.quote(application)
        return ReopenResultRead(
            application_id=application.id,
            reopen_count=application.reopen_count,
            status=application.status.value,
            quote=refreshed,
            transactions=[FeeTransactionRead.model_validate(item) for item in transactions],
            message=(
                "Application reopened once. Replace the corrected documents, keep the new TER "
                "receipt and resubmit before the Public Notice last date (APH 2.3.3d-e)."
            ),
        )

    # ------------------------------------------------------------------
    # Late submission and cutoff helpers
    # ------------------------------------------------------------------
    def is_after_cutoff(self, application: Application, now: datetime | None = None) -> bool:
        """Return True when a Category 1 application is past its Public Notice cut-off."""
        route = self._route(application)
        if route is None or route.category != ApplicationCategory.CAT1_CUTOFF:
            return False
        notice = self._public_notice(application)
        if notice is None:
            return False
        now = now or self._clock.now()
        return now.date() > notice.cutoff_on

    def flag_late_submission(self, application: Application, now: datetime | None = None) -> bool:
        """Flag a late Category 1 application and move it to the next academic year."""
        if application.late_submission:
            return True
        if not self.is_after_cutoff(application, now):
            return False
        application.late_submission = True
        application.academic_year = next_academic_year(application.academic_year)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _route(self, application: Application) -> ApplicationTypeRoute | None:
        return self._db.scalar(
            select(ApplicationTypeRoute).where(
                ApplicationTypeRoute.type == application.application_type
            )
        )

    def _public_notice(self, application: Application) -> PublicNotice | None:
        return self._db.scalar(
            select(PublicNotice).where(
                PublicNotice.academic_year == application.academic_year,
                PublicNotice.category == application.category,
            )
        )

    @staticmethod
    def _institution_class(application: Application) -> InstitutionClass:
        institution = application.institution
        if institution is not None and institution.institution_class is not None:
            return institution.institution_class
        return InstitutionClass.OTHER

    def _schedule(self, item_code: str, institution_class: InstitutionClass) -> _Schedule | None:
        row = self._db.scalar(
            select(FeeSchedule)
            .where(
                FeeSchedule.item_code == item_code,
                FeeSchedule.institution_class == institution_class,
            )
            .order_by(FeeSchedule.base_academic_year.desc())
        )
        if row is None:
            row = self._db.scalar(
                select(FeeSchedule)
                .where(
                    FeeSchedule.item_code == item_code,
                    FeeSchedule.institution_class.is_(None),
                )
                .order_by(FeeSchedule.base_academic_year.desc())
            )
        if row is None:
            return None
        return _Schedule(
            item_code=row.item_code,
            label=row.label,
            unit=row.unit.value,
            amount_paise=row.amount_paise,
            base_academic_year=row.base_academic_year,
            annual_increase_pct=Decimal(row.annual_increase_pct),
            apH_clause=row.apH_clause,
            needs_verification=row.needs_verification,
        )

    def _security_schedule(
        self,
        programme_family: str,
        level: str,
    ) -> SecurityDepositSchedule | None:
        return self._db.scalar(
            select(SecurityDepositSchedule).where(
                SecurityDepositSchedule.programme_family == programme_family,
                SecurityDepositSchedule.level == level,
            )
        )

    def _ter_item_code(self, application: Application) -> str:
        item_code = TER_ITEM_CODES.get(application.application_type)
        if item_code is None:
            raise FeeError(
                422,
                f"No TER item is configured for application type {application.application_type}.",
            )
        if item_code == "EOA_SELF_DISCLOSURE" and any(
            _is_pgdm_or_mba(programme.program_name)
            for programme in application.programs
        ):
            return "EOA_SELF_DISCLOSURE_PGDM_MBA"
        return item_code

    def _price_ter(self, application: Application, schedule: _Schedule) -> FeeLine:
        intakes = tuple(int(programme.intake) for programme in application.programs)
        return compute_line(
            item_code=schedule.item_code,
            label=schedule.label,
            unit=schedule.unit,
            unit_amount_paise=schedule.amount_paise,
            base_academic_year=schedule.base_academic_year,
            target_academic_year=application.academic_year,
            annual_increase_pct=schedule.annual_increase_pct,
            programme_intakes=intakes,
            apH_clause=schedule.apH_clause,
            needs_verification=schedule.needs_verification,
        )

    def _paid_paise(self, application: Application) -> int:
        total = self._db.scalar(
            select(func.coalesce(func.sum(FeeTransaction.amount_paise), 0)).where(
                FeeTransaction.application_id == application.id,
                FeeTransaction.kind.in_((FeeKind.TER, FeeKind.PENALTY)),
            )
        )
        return int(total or 0)

    def _refunded_paise(self, application: Application) -> int:
        total = self._db.scalar(
            select(func.coalesce(func.sum(FeeTransaction.amount_paise), 0)).where(
                FeeTransaction.application_id == application.id,
                FeeTransaction.kind == FeeKind.REFUND,
            )
        )
        return int(total or 0)

    def _commit(self) -> None:
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise


def _is_pgdm_or_mba(programme_name: str | None) -> bool:
    name = (programme_name or "").lower()
    return any(marker in name for marker in _PGDM_MBA_MARKERS)


def _programme_family(programme_name: str | None, level: str | None) -> str:
    name = (programme_name or "").lower()
    if any(marker in name for marker in _MANAGEMENT_MARKERS):
        return "MANAGEMENT"
    if any(marker in name for marker in _COMPUTER_APPLICATIONS_MARKERS):
        return "COMPUTER_APPLICATIONS"
    if any(marker in name for marker in _DESIGN_MARKERS):
        return "DESIGN"
    if any(marker in name for marker in _HMCT_MARKERS):
        return "HMCT"
    if any(marker in name for marker in _PLANNING_MARKERS):
        return "PLANNING"
    if any(marker in name for marker in _APPLIED_ARTS_MARKERS):
        return "APPLIED_ARTS"
    return "ENGINEERING_TECHNOLOGY"


def _programme_level(programme_name: str | None, level: str | None) -> str:
    value = f"{programme_name or ''} {level or ''}".lower()
    if "diploma" in value:
        return "DIPLOMA"
    if any(
        marker in value
        for marker in ("pg", "post graduate", "postgraduate", "mba", "mca", "pgdm", "pgcm")
    ):
        return "PG"
    return "UG"
