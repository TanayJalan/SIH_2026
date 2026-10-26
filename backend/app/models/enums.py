"""Enumerations shared by ORM models and services.

The APH vocabulary is deliberately kept in code as a convenience for services
and tests. The runtime authority for application types and committee
compositions is the database (``application_type_routes`` and the
``committee_compositions`` configuration), because APH rules are data and must
be editable without a deployment.
"""

from enum import StrEnum


class Role(StrEnum):
    """The ten APH system roles (APH_SPEC section 1 role mapping)."""

    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    REGULATION_BUREAU_OFFICER = "REGULATION_BUREAU_OFFICER"
    SCRUTINY_COMMITTEE_MEMBER = "SCRUTINY_COMMITTEE_MEMBER"
    EVC_MEMBER = "EVC_MEMBER"
    REGIONAL_OFFICER = "REGIONAL_OFFICER"
    SHC_MEMBER = "SHC_MEMBER"
    SAC_MEMBER = "SAC_MEMBER"
    EXECUTIVE_COMMITTEE_MEMBER = "EXECUTIVE_COMMITTEE_MEMBER"
    COMPLAINT_SCRUTINY_MEMBER = "COMPLAINT_SCRUTINY_MEMBER"
    SUPER_ADMIN = "SUPER_ADMIN"


class ApplicationType(StrEnum):
    """APH application types transcribed from APH_SPEC section 2.

    ``application_type_routes`` is authoritative at runtime; this enum keeps the
    vocabulary typed for code and tests. A test asserts that both sets match.
    """

    # Chapter I / Chapter IV variants.
    NEW_INSTITUTION = "NEW_INSTITUTION"
    NEW_INSTITUTION_OTHER_REGULATOR = "NEW_INSTITUTION_OTHER_REGULATOR"
    CLOSURE_AND_NEW_INSTITUTION = "CLOSURE_AND_NEW_INSTITUTION"
    UNIVERSITY = "UNIVERSITY"

    # Category 1: cut-off date in the Public Notice.
    EOA_SELF_DISCLOSURE = "EOA_SELF_DISCLOSURE"
    NRI_SEATS = "NRI_SEATS"
    DIPLOMA_DEGREE_CONVERSION = "DIPLOMA_DEGREE_CONVERSION"
    CHANGE_OF_NAME = "CHANGE_OF_NAME"
    NEW_PROGRAMME = "NEW_PROGRAMME"
    MERGER_OF_INSTITUTIONS = "MERGER_OF_INSTITUTIONS"
    EOA_AFTER_BREAK = "EOA_AFTER_BREAK"
    SUPERNUMERARY_FN_OCI = "SUPERNUMERARY_FN_OCI"
    INCREASE_INTAKE = "INCREASE_INTAKE"
    INTEGRATED_DUAL_DEGREE = "INTEGRATED_DUAL_DEGREE"
    OFF_CAMPUS = "OFF_CAMPUS"
    FPM = "FPM"
    COURSE_RENAME_MERGE_REDUCTION = "COURSE_RENAME_MERGE_REDUCTION"
    COLLABORATION_TWINNING = "COLLABORATION_TWINNING"

    # Category 2: year-round.
    CHANGE_OF_SITE = "CHANGE_OF_SITE"
    CLOSURE_OF_INSTITUTION = "CLOSURE_OF_INSTITUTION"
    WOMEN_COED_CONVERSION = "WOMEN_COED_CONVERSION"
    CLOSURE_OF_PROGRAMME = "CLOSURE_OF_PROGRAMME"
    CHANGE_IN_BANK_DETAILS = "CHANGE_IN_BANK_DETAILS"
    CHANGE_OF_TRUST_NAME = "CHANGE_OF_TRUST_NAME"
    EXTENDED_EOA = "EXTENDED_EOA"
    DEEMED_UNIVERSITY_CONVERSION = "DEEMED_UNIVERSITY_CONVERSION"
    ODL_ONLINE = "ODL_ONLINE"


class ApplicationTrack(StrEnum):
    """High-level APH track that selects the workflow path."""

    NEW_INSTITUTION = "NEW_INSTITUTION"
    EXISTING = "EXISTING"
    UNIVERSITY = "UNIVERSITY"
    ODL = "ODL"


class ApplicationCategory(StrEnum):
    """Public-notice category (APH_SPEC section 2, Table 2.2)."""

    CAT1_CUTOFF = "CAT1_CUTOFF"
    CAT2_YEAR_ROUND = "CAT2_YEAR_ROUND"


class DecisionType(StrEnum):
    """Final decision letters issued by the Executive Committee (APH 1.10)."""

    LOA = "LOA"
    EOA = "EOA"
    LOD = "LOD"
    LOR = "LOR"


class DecisionBody(StrEnum):
    """Committee or Council that recorded a decision (APH 1.10-1.11, 2.23-2.24)."""

    EC = "EC"
    COUNCIL = "COUNCIL"
    SAC = "SAC"
    SHC = "SHC"


class DecisionOutcome(StrEnum):
    """Outcome recorded against a decision.

    ``RECOMMEND``/``NOT_RECOMMEND``/``SEND_BACK`` cover SAC and SHC
    recommendations; the letter outcomes cover EC and Council decisions.
    """

    LOA = "LOA"
    EOA = "EOA"
    LOD = "LOD"
    LOR = "LOR"
    RECOMMEND = "RECOMMEND"
    NOT_RECOMMEND = "NOT_RECOMMEND"
    SEND_BACK = "SEND_BACK"


class DecisionLetterType(StrEnum):
    """Letter types published on the portal (APH 1.10, 2.23.3, 2.24a)."""

    LOA = "LOA"
    EOA = "EOA"
    LOD = "LOD"
    LOR = "LOR"
    SPEAKING_ORDER = "SPEAKING_ORDER"
    DEFICIENCY_REPORT = "DEFICIENCY_REPORT"
    SHOW_CAUSE = "SHOW_CAUSE"


class ApplicationStatus(StrEnum):
    """Primary status values for an application.

    The state vocabulary follows the APH Annexure-7 cycle. Withdrawal is an
    overlay stored on the application so it can coexist with the primary
    workflow state instead of terminating it.

    The values below the "legacy" marker were emitted by the pre-APH linear
    workflow. They are retained so historical rows and their events remain
    readable; the state machine never emits them. Migration
    ``0013_workflow_definition`` remaps existing rows to the APH states.
    """

    # Track A (Chapter I: new institution, extension of approval).
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SCRUTINY = "SCRUTINY"
    DEFICIENCY_COMMUNICATED = "DEFICIENCY_COMMUNICATED"
    INSTITUTION_COMPLIANCE = "INSTITUTION_COMPLIANCE"
    RE_SCRUTINY = "RE_SCRUTINY"
    EVC_CONSTITUTED = "EVC_CONSTITUTED"
    EVC_DONE = "EVC_DONE"
    REGULATION_BUREAU_OBSERVATIONS = "REGULATION_BUREAU_OBSERVATIONS"
    EC_DECISION = "EC_DECISION"
    COUNCIL_RATIFICATION = "COUNCIL_RATIFICATION"
    LOA_ISSUED = "LOA_ISSUED"
    LOD_ISSUED = "LOD_ISSUED"
    LOR_ISSUED = "LOR_ISSUED"
    APPEAL_WINDOW = "APPEAL_WINDOW"
    SAC_REVIEW = "SAC_REVIEW"
    COUNCIL_FINAL = "COUNCIL_FINAL"
    REGIONAL_ENDORSEMENT = "REGIONAL_ENDORSEMENT"
    FINAL_LOA = "FINAL_LOA"
    FINAL_LOD = "FINAL_LOD"
    FINAL_LOR = "FINAL_LOR"
    SECURITY_DEPOSIT_PENDING = "SECURITY_DEPOSIT_PENDING"
    ACTIVE_LOA = "ACTIVE_LOA"
    CANCELLED = "CANCELLED"
    WITHDRAWN = "WITHDRAWN"

    # Track B (extension of approval by self-disclosure).
    SELF_DISCLOSURE_CHECK = "SELF_DISCLOSURE_CHECK"
    RANDOM_EVC = "RANDOM_EVC"
    COMPLIANCE_WINDOW = "COMPLIANCE_WINDOW"
    EC_LISTING = "EC_LISTING"
    EOA_ISSUED = "EOA_ISSUED"
    SPEAKING_ORDER = "SPEAKING_ORDER"
    ACTIVE_EOA = "ACTIVE_EOA"

    # Track C / D (existing-institution changes).
    SHC_HEARING = "SHC_HEARING"
    CLOSED = "CLOSED"

    # Legacy pre-APH values (read-only for historical rows).
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    DEFICIENCY_RAISED = "DEFICIENCY_RAISED"
    DEFICIENCY_RESPONDED = "DEFICIENCY_RESPONDED"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    INSPECTION_DONE = "INSPECTION_DONE"
    COMMITTEE_REVIEW = "COMMITTEE_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class WorkflowAction(StrEnum):
    """Actions accepted by the workflow state machine.

    The names are the stable public API for ``POST
    /applications/{id}/actions/{action}``. Which action is legal in which
    state, and which role may perform it, is data in ``workflow_transitions``.
    """

    SUBMIT = "submit"
    PAY_TER = "pay_ter"
    ASSIGN_SCRUTINY = "assign_scrutiny"
    SCRUTINY_RECOMMEND = "scrutiny_recommend"
    COMMUNICATE_DEFICIENCY = "communicate_deficiency"
    SUBMIT_COMPLIANCE = "submit_compliance"
    RE_SCRUTINY_VERIFY = "re_scrutiny_verify"
    CONSTITUTE_EVC = "constitute_evc"
    SUBMIT_EVC_VIDEO = "submit_evc_video"
    EVC_REPORT = "evc_report"
    OBSERVATIONS = "observations"
    LIST_FOR_EC = "list_for_ec"
    EC_DECIDE = "ec_decide"
    COUNCIL_RATIFICATION = "council_ratification"
    ISSUE_LETTER = "issue_letter"
    ISSUE_LOA = "issue_loa"
    ISSUE_EOA = "issue_eoa"
    ISSUE_LOD = "issue_lod"
    ISSUE_LOR = "issue_lor"
    FILE_APPEAL = "file_appeal"
    SAC_RECOMMEND = "sac_recommend"
    SEND_BACK = "send_back"
    COUNCIL_FINAL = "council_final"
    ENDORSE_DECISION = "endorse_decision"
    PAY_SECURITY_DEPOSIT = "pay_security_deposit"
    APPLY_DEPOSIT_PENALTY = "apply_deposit_penalty"
    FINALIZE_NO_APPEAL = "finalize_no_appeal"
    EXPIRE_LOA = "expire_loa"
    SHC_HEARING = "shc_hearing"
    RUN_SELF_DISCLOSURE_CHECK = "run_self_disclosure_check"
    REOPEN_ONCE = "reopen_once"
    WITHDRAW_APPLICATION = "withdraw_application"

    # Legacy names retained as aliases so existing integrations keep working.
    AUTO_ASSIGN = "assign_scrutiny"
    VERIFY_DOCUMENTS = "scrutiny_recommend"
    START_SCRUTINY = "assign_scrutiny"
    RAISE_DEFICIENCY = "communicate_deficiency"
    RESPOND_DEFICIENCY = "submit_compliance"
    CLOSE_DEFICIENCY = "re_scrutiny_verify"
    SCHEDULE_INSPECTION = "constitute_evc"
    SUBMIT_INSPECTION_REPORT = "evc_report"
    SEND_TO_COMMITTEE = "observations"
    APPROVE = "issue_loa"
    REJECT = "issue_lor"
    WITHDRAW = "withdraw_application"
    REOPEN = "reopen_once"


class WorkflowStage(StrEnum):
    """High-level stages used for SLA tracking and dashboards."""

    APPLICATION = "APPLICATION"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    SCRUTINY = "SCRUTINY"
    DEFICIENCY = "DEFICIENCY"
    INSPECTION = "INSPECTION"
    COMMITTEE_REVIEW = "COMMITTEE_REVIEW"
    DECISION = "DECISION"
    COMPLETED = "COMPLETED"


class DocumentVerificationStatus(StrEnum):
    """Verification state for an uploaded document."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


class DeficiencyStatus(StrEnum):
    """Lifecycle of a deficiency raised against an application."""

    OPEN = "OPEN"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"


class InspectionStatus(StrEnum):
    """Lifecycle of an inspection visit."""

    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InspectionRecommendation(StrEnum):
    """Committee recommendation recorded with an inspection report.

    APH does not permit conditional or partial approval (APH 4.9c, 2.27): an
    EVC either finds the institution compliant or records deficiencies that
    must be closed before the next stage.
    """

    APPROVE = "APPROVE"
    DEFICIENCY = "DEFICIENCY"
    REJECT = "REJECT"


class Severity(StrEnum):
    """Severity shared by compliance and alert rules."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceHealth(StrEnum):
    """Red/Amber/Green monitoring status for an institution's compliance."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


class AlertChannel(StrEnum):
    """Delivery channels supported by the notification service."""

    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class AlertStatus(StrEnum):
    """Delivery and acknowledgement state for an alert."""

    PENDING = "PENDING"
    SENT = "SENT"
    READ = "READ"
    ACKED = "ACKED"


class AlertTrigger(StrEnum):
    """Rule-driven events that can raise an alert."""

    DEADLINE_APPROACHING = "DEADLINE_APPROACHING"
    SLA_BREACHED = "SLA_BREACHED"
    DEFICIENCY_DUE = "DEFICIENCY_DUE"
    DEFICIENCY_OVERDUE = "DEFICIENCY_OVERDUE"
    DOCUMENT_EXPIRING = "DOCUMENT_EXPIRING"
    COMPLIANCE_RED = "COMPLIANCE_RED"
    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    APPEAL_WINDOW_CLOSING = "APPEAL_WINDOW_CLOSING"
    DEPOSIT_DUE = "DEPOSIT_DUE"


class InstitutionRegion(StrEnum):
    """AICTE regions (APH_SPEC section 10, Annexure-14)."""

    CENTRAL = "CENTRAL"
    EASTERN = "EASTERN"
    NORTHERN = "NORTHERN"
    NORTH_WESTERN = "NORTH_WESTERN"
    SOUTH_CENTRAL = "SOUTH_CENTRAL"
    SOUTHERN = "SOUTHERN"
    SOUTH_WESTERN = "SOUTH_WESTERN"
    WESTERN = "WESTERN"


class InstitutionClass(StrEnum):
    """Fee class used by the TER tables (APH_SPEC section 4)."""

    GOVT_TYPE = "GOVT_TYPE"
    OTHER = "OTHER"


class InstitutionStatus(StrEnum):
    """Institution lifecycle status used by APH post-approval rules."""

    ACTIVE = "ACTIVE"
    HIBERNATION = "HIBERNATION"
    NO_ADMISSION = "NO_ADMISSION"
    CLOSED_PROGRESSIVE = "CLOSED_PROGRESSIVE"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class LandOwnership(StrEnum):
    """Land tenure; lease rules are in APH 6.17a."""

    OWNED = "OWNED"
    LEASED = "LEASED"


class CommitteeType(StrEnum):
    """Committees named in APH_SPEC section 1."""

    SCRUTINY = "SCRUTINY"
    RE_SCRUTINY = "RE_SCRUTINY"
    EVC = "EVC"
    SHC = "SHC"
    SAC = "SAC"
    SCSC = "SCSC"
    EC = "EC"
    COUNCIL = "COUNCIL"


class CommitteeMode(StrEnum):
    """Hearing/visit mode; APH scrutiny may be online, physical or hybrid."""

    ONLINE = "ONLINE"
    PHYSICAL = "PHYSICAL"
    HYBRID = "HYBRID"


class CommitteeStatus(StrEnum):
    """Lifecycle of a scheduled committee."""

    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FeeUnit(StrEnum):
    """Unit that a fee schedule row is charged per (APH_SPEC section 4)."""

    FLAT = "FLAT"
    PER_DIVISION = "PER_DIVISION"
    PER_COURSE = "PER_COURSE"
    PER_1000_SEATS = "PER_1000_SEATS"
    PER_LSC = "PER_LSC"


class FeeKind(StrEnum):
    """Money movement attached to an application."""

    TER = "TER"
    PENALTY = "PENALTY"
    REFUND = "REFUND"
    DEDUCTION = "DEDUCTION"


class SecurityDepositStatus(StrEnum):
    """Security Deposit lifecycle (APH 1.12, 2.25f, 6.46)."""

    PENDING = "PENDING"
    PAID = "PAID"
    PENALTY_10 = "PENALTY_10"
    PENALTY_20 = "PENALTY_20"
    WITHDRAWN = "WITHDRAWN"
    RELEASED = "RELEASED"
    FORFEITED = "FORFEITED"


class TimerStatus(StrEnum):
    """Lifecycle of a deadline timer created from a ``DeadlineRule``."""

    PENDING = "PENDING"
    DUE = "DUE"
    BREACHED = "BREACHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProgrammeStatus(StrEnum):
    """Lifecycle of an approved programme."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ZERO_INTAKE = "ZERO_INTAKE"


class ProgrammeMode(StrEnum):
    """Delivery mode recorded against a programme (APH 6.5, Chapter V)."""

    REGULAR = "REGULAR"
    FLEXIBLE_TIMING = "FLEXIBLE_TIMING"
    ODL_ONLINE = "ODL_ONLINE"


class FacultyCadre(StrEnum):
    """Faculty cadre used by the FSR calculator (APH 6.14)."""

    PRINCIPAL_DIRECTOR = "PRINCIPAL_DIRECTOR"
    HOD = "HOD"
    PROFESSOR = "PROFESSOR"
    ASSOC_PROFESSOR = "ASSOC_PROFESSOR"
    ASST_PROFESSOR = "ASST_PROFESSOR"
    PROF_OF_PRACTICE = "PROF_OF_PRACTICE"
    ADJUNCT = "ADJUNCT"


class PenalActionType(StrEnum):
    """Penal actions available under APH 7.3."""

    NRI_SUSPENSION = "NRI_SUSPENSION"
    INTAKE_REDUCTION = "INTAKE_REDUCTION"
    NO_ADMISSION = "NO_ADMISSION"
    PROGRAMME_WITHDRAWAL = "PROGRAMME_WITHDRAWAL"
    AUTONOMY_WITHDRAWAL = "AUTONOMY_WITHDRAWAL"
    INSTITUTION_WITHDRAWAL = "INSTITUTION_WITHDRAWAL"
    EXCESS_ADMISSION_FINE = "EXCESS_ADMISSION_FINE"
    GRANT_INELIGIBLE = "GRANT_INELIGIBLE"


class ComplaintStatus(StrEnum):
    """Complaint path from PGRC to SCSC/SHC/EC (APH 7.10)."""

    RECEIVED = "RECEIVED"
    PGRC = "PGRC"
    SCSC = "SCSC"
    SHOW_CAUSE = "SHOW_CAUSE"
    HEARING = "HEARING"
    DECIDED = "DECIDED"
    CLOSED = "CLOSED"


class CalendarEventKey(StrEnum):
    """Academic Calendar events that APH references by date (APH_SPEC section 5)."""

    LAST_DATE_EOA = "LAST_DATE_EOA"
    ENROLMENT_UPLOAD_30NOV = "ENROLMENT_UPLOAD_30NOV"
    NOMENCLATURE_30NOV = "NOMENCLATURE_30NOV"
    SD_PENALTY10_31MAY = "SD_PENALTY10_31MAY"
    SD_PENALTY20_31JUL = "SD_PENALTY20_31JUL"
    IC_REPORT_30JUN = "IC_REPORT_30JUN"
    CLOSURE_REVOKE_10APR = "CLOSURE_REVOKE_10APR"
    RESTORATION_30APR = "RESTORATION_30APR"
