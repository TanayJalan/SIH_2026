"""Enumerations shared by ORM models and services."""

from enum import StrEnum


class Role(StrEnum):
    """Roles supported by the approval workflow."""

    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    SCRUTINY_OFFICER = "SCRUTINY_OFFICER"
    INSPECTION_COMMITTEE = "INSPECTION_COMMITTEE"
    REGIONAL_HEAD = "REGIONAL_HEAD"
    SUPER_ADMIN = "SUPER_ADMIN"


class ApplicationType(StrEnum):
    """Supported application types for the MVP flow."""

    NEW = "NEW"
    EXTENSION = "EXTENSION"
    INTAKE_CHANGE = "INTAKE_CHANGE"


class ApplicationStatus(StrEnum):
    """Primary status values for an application.

    Withdrawal and escalation are overlays stored on the application so they
    can coexist with the primary workflow state instead of terminating it.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    SCRUTINY = "SCRUTINY"
    DEFICIENCY_RAISED = "DEFICIENCY_RAISED"
    DEFICIENCY_RESPONDED = "DEFICIENCY_RESPONDED"
    INSPECTION_SCHEDULED = "INSPECTION_SCHEDULED"
    INSPECTION_DONE = "INSPECTION_DONE"
    COMMITTEE_REVIEW = "COMMITTEE_REVIEW"
    APPROVED = "APPROVED"
    CONDITIONALLY_APPROVED = "CONDITIONALLY_APPROVED"
    REJECTED = "REJECTED"


class WorkflowAction(StrEnum):
    """Actions accepted by the workflow state machine."""

    SUBMIT = "submit"
    AUTO_ASSIGN = "auto_assign"
    VERIFY_DOCUMENTS = "verify_documents"
    START_SCRUTINY = "start_scrutiny"
    RAISE_DEFICIENCY = "raise_deficiency"
    RESPOND_DEFICIENCY = "respond_deficiency"
    CLOSE_DEFICIENCY = "close_deficiency"
    SCHEDULE_INSPECTION = "schedule_inspection"
    SUBMIT_INSPECTION_REPORT = "submit_inspection_report"
    SEND_TO_COMMITTEE = "send_to_committee"
    APPROVE = "approve"
    CONDITIONALLY_APPROVE = "conditionally_approve"
    REJECT = "reject"
    WITHDRAW = "withdraw"


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
    """Committee recommendation recorded with an inspection report."""

    APPROVE = "APPROVE"
    CONDITIONAL_APPROVE = "CONDITIONAL_APPROVE"
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
