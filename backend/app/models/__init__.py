"""ORM model registry.

Importing this package registers every table on ``Base.metadata`` for Alembic.
"""

from app.models.alert import Alert, AlertRule
from app.models.application import Application, ApplicationProgram
from app.models.audit import AuditLog
from app.models.compliance import (
    ComplianceConfig,
    ComplianceResult,
    ComplianceRule,
    ComplianceSnapshot,
)
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    AlertChannel,
    AlertStatus,
    AlertTrigger,
    ApplicationStatus,
    ApplicationType,
    ComplianceHealth,
    DeficiencyStatus,
    DocumentVerificationStatus,
    InspectionRecommendation,
    InspectionStatus,
    Role,
    Severity,
    WorkflowAction,
    WorkflowStage,
)
from app.models.inspection import Inspection
from app.models.institution import Institution
from app.models.required_document import RequiredDocument
from app.models.sla import SLAConfig
from app.models.user import User
from app.models.workflow import WorkflowEvent

__all__ = [
    "Alert",
    "AlertChannel",
    "AlertRule",
    "AlertStatus",
    "AlertTrigger",
    "Application",
    "ApplicationProgram",
    "ApplicationStatus",
    "ApplicationType",
    "AuditLog",
    "ComplianceConfig",
    "ComplianceHealth",
    "ComplianceResult",
    "ComplianceRule",
    "ComplianceSnapshot",
    "Deficiency",
    "DeficiencyStatus",
    "Document",
    "DocumentVerificationStatus",
    "Inspection",
    "InspectionRecommendation",
    "InspectionStatus",
    "Institution",
    "RequiredDocument",
    "Role",
    "SLAConfig",
    "Severity",
    "User",
    "WorkflowAction",
    "WorkflowEvent",
    "WorkflowStage",
]
