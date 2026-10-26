"""ORM model registry.

Importing this package registers every table on ``Base.metadata`` for Alembic.
"""

from app.models.alert import Alert, AlertRule, AlertTriggerCatalogue
from app.models.appeal import Appeal
from app.models.application import Application, ApplicationProgram
from app.models.application_type_route import ApplicationTypeRoute
from app.models.audit import AuditLog
from app.models.calendar import AcademicCalendarEvent, PublicNotice
from app.models.committee import Committee, CommitteeMember, CommitteeReport
from app.models.complaint import Complaint, PenalAction
from app.models.compliance import (
    ComplianceConfig,
    ComplianceResult,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.deadline import DeadlineRule, Timer
from app.models.decision import CouncilRatification, Decision, DecisionLetter
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.document_sequence import DecisionLetterSequence
from app.models.enums import (
    AlertChannel,
    AlertStatus,
    AlertTrigger,
    ApplicationCategory,
    ApplicationStatus,
    ApplicationTrack,
    ApplicationType,
    CalendarEventKey,
    CommitteeMode,
    CommitteeStatus,
    CommitteeType,
    ComplaintStatus,
    ComplianceHealth,
    DecisionBody,
    DecisionLetterType,
    DecisionOutcome,
    DecisionType,
    DeficiencyStatus,
    DocumentVerificationStatus,
    FacultyCadre,
    FeeKind,
    FeeUnit,
    InspectionRecommendation,
    InspectionStatus,
    InstitutionClass,
    InstitutionRegion,
    InstitutionStatus,
    LandOwnership,
    PenalActionType,
    ProgrammeMode,
    ProgrammeStatus,
    Role,
    SecurityDepositStatus,
    Severity,
    TimerStatus,
    WorkflowAction,
    WorkflowStage,
)
from app.models.expert_pool import ExpertPool
from app.models.faculty import Faculty
from app.models.fee import FeeSchedule, FeeTransaction
from app.models.inspection import Inspection
from app.models.institution import Institution
from app.models.programme import ApprovedIntakeLedger, Programme
from app.models.required_document import RequiredDocument
from app.models.security_deposit import SecurityDeposit
from app.models.security_deposit_schedule import SecurityDepositSchedule
from app.models.sla import SLAConfig
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)

__all__ = [
    "AcademicCalendarEvent",
    "Alert",
    "AlertChannel",
    "AlertRule",
    "AlertStatus",
    "AlertTrigger",
    "AlertTriggerCatalogue",
    "Appeal",
    "Application",
    "ApplicationCategory",
    "ApplicationProgram",
    "ApplicationStatus",
    "ApplicationTrack",
    "ApplicationType",
    "ApplicationTypeRoute",
    "ApprovedIntakeLedger",
    "AuditLog",
    "CalendarEventKey",
    "Committee",
    "CommitteeMember",
    "CommitteeMode",
    "CommitteeReport",
    "CommitteeStatus",
    "CommitteeType",
    "Complaint",
    "ComplaintStatus",
    "ComplianceConfig",
    "ComplianceHealth",
    "ComplianceResult",
    "ComplianceRule",
    "ComplianceSnapshot",
    "CouncilRatification",
    "DeadlineRule",
    "Decision",
    "DecisionBody",
    "DecisionLetter",
    "DecisionLetterSequence",
    "DecisionLetterType",
    "DecisionOutcome",
    "DecisionType",
    "Deficiency",
    "DeficiencyStatus",
    "Document",
    "DocumentVerificationStatus",
    "ExpertPool",
    "Faculty",
    "FacultyCadre",
    "FeeKind",
    "FeeSchedule",
    "FeeTransaction",
    "FeeUnit",
    "Inspection",
    "InspectionRecommendation",
    "InspectionStatus",
    "Institution",
    "InstitutionClass",
    "InstitutionRegion",
    "InstitutionStatus",
    "LandOwnership",
    "PenalAction",
    "PenalActionType",
    "Programme",
    "ProgrammeMode",
    "ProgrammeStatus",
    "PublicNotice",
    "RequiredDocument",
    "Role",
    "SLAConfig",
    "SecurityDeposit",
    "SecurityDepositSchedule",
    "SecurityDepositStatus",
    "Severity",
    "Timer",
    "TimerStatus",
    "User",
    "WorkflowAction",
    "WorkflowDefinition",
    "WorkflowEvent",
    "WorkflowStage",
    "WorkflowState",
    "WorkflowTransition",
]
