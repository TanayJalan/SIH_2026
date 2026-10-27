"""Reviewer rejection, verification and institution replacement rules.

APH 1.4.3 locks the submitted application, but 1.8f and 2.4 let the institution
comply with deficiencies communicated through the portal, and 1.8g limits
Re-Scrutiny to the listed deficiencies. This module is the single decision point
for whether a document may be rejected, verified or replaced; the API routes and
the UI both read the same answer so a button can never call a forbidden action.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.core.config import Settings
from app.models.application import Application
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    ApplicationStatus,
    DeficiencyStatus,
    DocumentRejectionReason,
    DocumentVerificationStatus,
    Role,
    WorkflowAction,
)
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.schemas.application import DocumentReviewRequest
from app.services.alert_engine import NotificationService
from app.services.audit import AuditService
from app.services.workflow import WorkflowService
from app.services.workflow_errors import WorkflowError

logger = logging.getLogger("app.documents")

COMPLIANCE_WINDOW_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        # Chapter I / Chapter II deficiency cycle.
        ApplicationStatus.DEFICIENCY_COMMUNICATED,
        ApplicationStatus.INSTITUTION_COMPLIANCE,
        # Chapter II equivalent for extension of approval by self-disclosure.
        ApplicationStatus.COMPLIANCE_WINDOW,
        # APH 2.4 gives the institution a chance to comply before Re-Scrutiny.
        ApplicationStatus.RE_SCRUTINY,
    }
)
"""Application states in which a rejected or flagged document may be replaced."""

REVIEW_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.SCRUTINY,
        # A reviewer must be able to look again at a replacement while the case
        # sits in the compliance cycle (APH 1.8g, 2.4).
        *COMPLIANCE_WINDOW_STATUSES,
    }
)
"""States in which a Scrutiny Committee member may review documents."""

REVIEWER_ROLES = frozenset(
    {Role.SCRUTINY_COMMITTEE_MEMBER, Role.REGULATION_BUREAU_OFFICER}
)

REJECTION_CLAUSE = "APH 1.8f"
"""Deficiencies are communicated through the portal and fulfilled by the institution."""

VERIFICATION_CLAUSE = "APH 1.8g"
"""Re-Scrutiny verifies only the deficiencies that were listed."""

REUPLOAD_CLAUSE = "APH 2.4"
"""The institution gets a chance to comply before Scrutiny, Re-Scrutiny or Hearing."""

REJECTION_LABELS: dict[DocumentRejectionReason, str] = {
    DocumentRejectionReason.UNREADABLE: "Unreadable or illegible copy",
    DocumentRejectionReason.NO_DSC: "Not digitally signed (DSC missing)",
    DocumentRejectionReason.EXPIRED: "Certificate has expired",
    DocumentRejectionReason.WRONG_DOCUMENT: "Wrong document uploaded",
    DocumentRejectionReason.NAME_MISMATCH: "Name does not match the institution",
    DocumentRejectionReason.INCOMPLETE: "Document is incomplete",
    DocumentRejectionReason.OTHER: "Other reason",
}


class DocumentReviewError(Exception):
    """A reviewer or institution document action that cannot proceed."""

    def __init__(self, status_code: int, detail: str | dict[str, object]) -> None:
        super().__init__(detail if isinstance(detail, str) else str(detail.get("message")))
        self.status_code = status_code
        self.detail = detail


def latest_documents(db: Session, application_id: uuid.UUID) -> dict[str, Document]:
    """Return the newest version of every document type on an application."""
    rows = db.scalars(
        select(Document)
        .where(Document.application_id == application_id)
        .order_by(Document.doc_type.asc(), Document.version.desc())
    ).all()
    latest: dict[str, Document] = {}
    for document in rows:
        latest.setdefault(document.doc_type, document)
    return latest


def is_latest_version(db: Session, document: Document) -> bool:
    """Return whether ``document`` is the newest version of its type."""
    newest = db.scalar(
        select(func.max(Document.version)).where(
            Document.application_id == document.application_id,
            Document.doc_type == document.doc_type,
        )
    )
    return newest == document.version


def reupload_count(db: Session, document: Document) -> int:
    """Return how many replacement versions exist for this document type."""
    return int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.application_id == document.application_id,
                Document.doc_type == document.doc_type,
                Document.version > 1,
            )
        )
        or 0
    )


def replacement_block_reason(
    db: Session,
    application: Application,
    document: Document,
    settings: Settings,
) -> str | None:
    """Return why an institution may not replace ``document``, or ``None``.

    ``None`` means the action is allowed. The messages are shown verbatim in the
    UI, including the APH clause that authorises or limits the action.
    """
    if document.application_id != application.id:
        return "This document does not belong to the application."
    if not is_latest_version(db, document):
        return (
            "This version has already been superseded. Re-upload the latest version "
            f"instead ({REUPLOAD_CLAUSE} / 1.8f)."
        )
    if application.status == ApplicationStatus.DRAFT:
        # Nothing is locked before submission (APH 1.4.3), so the institution may
        # always replace a draft upload.
        return None
    if document.verification_status == DocumentVerificationStatus.VERIFIED:
        return (
            "A verified document cannot be replaced. Ask the reviewer to reject it "
            "first (APH 1.4.3)."
        )
    if document.verification_status not in {
        DocumentVerificationStatus.REJECTED,
        DocumentVerificationStatus.FLAGGED,
    }:
        return (
            "Application is locked; only rejected or flagged documents can be replaced "
            "(APH 1.4.3)."
        )
    if application.status not in COMPLIANCE_WINDOW_STATUSES:
        return (
            "Application is locked outside a compliance window; only rejected documents "
            f"can be replaced after the institution is asked to comply ({REUPLOAD_CLAUSE})."
        )
    if reupload_count(db, document) >= settings.max_reuploads_per_document:
        return (
            "This document has reached the replacement limit "
            f"({settings.max_reuploads_per_document}). Contact the Regulation Bureau."
        )
    return None


def reviewer_block_reason(
    actor: User,
    application: Application,
    document: Document,
) -> str | None:
    """Return why ``actor`` may not review ``document``, or ``None``."""
    if actor.role not in REVIEWER_ROLES:
        return (
            "Only a Scrutiny Committee member or a Regulation Bureau officer may "
            "review documents."
        )
    if actor.role == Role.SCRUTINY_COMMITTEE_MEMBER:
        if application.status not in REVIEW_STATUSES:
            return (
                "Documents can only be reviewed while the case is in Scrutiny or "
                "Re-Scrutiny (APH 1.8)."
            )
    elif application.is_withdrawn or application.status in {
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.CANCELLED,
    }:
        return "A withdrawn or cancelled application cannot be reviewed."
    if document.application_id != application.id:
        return "This document does not belong to the application."
    return None


def document_allowed_actions(
    db: Session,
    application: Application,
    actor: User,
    document: Document,
    settings: Settings,
) -> list[str]:
    """Return the document actions the current actor may take right now."""
    actions: list[str] = []
    if (
        is_latest_version(db, document)
        and reviewer_block_reason(actor, application, document) is None
    ):
        # A reviewer's decision overrides the automated pre-check, and an expired
        # certificate is exactly the case the automated check cannot catch.
        if document.verification_status != DocumentVerificationStatus.REJECTED:
            actions.append("reject")
        if document.verification_status in {
            DocumentVerificationStatus.PENDING,
            DocumentVerificationStatus.FLAGGED,
        }:
            actions.append("verify")
    if actor.role == Role.INSTITUTION_ADMIN and actor.institution_id == application.institution_id:
        if replacement_block_reason(db, application, document, settings) is None:
            actions.append("reupload")
    return actions


class DocumentReviewService:
    """Record reviewer decisions and keep the deficiency trail in sync."""

    def __init__(
        self,
        db: Session,
        audit: AuditService,
        clock: SimulatedClock,
        settings: Settings,
        *,
        notifications: NotificationService,
    ) -> None:
        self._db = db
        self._audit = audit
        self._clock = clock
        self._settings = settings
        self._notifications = notifications

    def reject(
        self,
        actor: User,
        application: Application,
        document: Document,
        payload: DocumentReviewRequest,
    ) -> tuple[Document, Deficiency]:
        """Reject one document, link a deficiency and notify the institution."""
        block = reviewer_block_reason(actor, application, document)
        if block is not None:
            raise DocumentReviewError(403, block)
        if not is_latest_version(self._db, document):
            raise DocumentReviewError(
                409, "Only the latest version of a document can be rejected."
            )
        if document.verification_status == DocumentVerificationStatus.REJECTED:
            raise DocumentReviewError(409, "This document is already rejected.")
        if payload.reason_code is None:
            raise DocumentReviewError(422, "Select a rejection reason.")

        now = self._clock.now()
        before = self._document_snapshot(document)
        summary = payload.comment or REJECTION_LABELS[payload.reason_code]

        # Rejecting during Scrutiny communicates the deficiency through the
        # seeded edge, so the case reaches the compliance window the same way a
        # Scrutiny Committee's own Deficiency Report does (APH 1.8f, 2.3.3b).
        # It runs before the document mutation because a refused transition
        # rolls the session back.
        deficiency = self._open_compliance_window(
            actor, application, document, payload.reason_code, summary, now
        )

        document.verification_status = DocumentVerificationStatus.REJECTED
        document.rejection_reason_code = payload.reason_code
        document.rejection_comment = payload.comment
        document.rejected_by = actor.id
        document.rejected_at = now
        document.apH_clause = payload.apH_clause or REJECTION_CLAUSE
        document.verification_notes = {
            **(document.verification_notes or {}),
            "review": {
                "decision": "REJECTED",
                "reason_code": payload.reason_code.value,
                "comment": payload.comment,
                "by": str(actor.id),
                "at": now.isoformat(),
                "apH_clause": document.apH_clause,
            },
        }
        self._db.flush()

        if deficiency is None:
            deficiency = self._link_deficiency(
                actor, application, document, payload.reason_code, summary, now
            )
        deficiency.status = DeficiencyStatus.OPEN
        deficiency.response_text = None
        deficiency.response_document_id = None
        deficiency.responded_at = None
        deficiency.closed_at = None
        document.related_deficiency_id = deficiency.id
        self._db.flush()

        self._audit.log(
            actor,
            "application.document.reject",
            "Document",
            document.id,
            before=before,
            after=self._document_snapshot(document),
        )
        self._write_event(
            actor,
            application,
            document,
            action="reject_document",
            comment=(
                f"{document.doc_type} version {document.version} rejected: "
                f"{REJECTION_LABELS[payload.reason_code]}."
            ),
            clause=document.apH_clause,
        )
        self._commit()
        self._notify_rejection(actor, application, document)
        return document, deficiency

    def verify(
        self,
        actor: User,
        application: Application,
        document: Document,
        payload: DocumentReviewRequest,
    ) -> Document:
        """Mark a re-uploaded or flagged document as verified."""
        block = reviewer_block_reason(actor, application, document)
        if block is not None:
            raise DocumentReviewError(403, block)
        if not is_latest_version(self._db, document):
            raise DocumentReviewError(
                409, "Only the latest version of a document can be verified."
            )
        if document.verification_status == DocumentVerificationStatus.VERIFIED:
            raise DocumentReviewError(409, "This document is already verified.")
        if document.verification_status == DocumentVerificationStatus.REJECTED:
            raise DocumentReviewError(
                409,
                "A rejected document cannot be verified; wait for the institution's "
                "replacement upload.",
            )

        now = self._clock.now()
        before = self._document_snapshot(document)
        document.verification_status = DocumentVerificationStatus.VERIFIED
        document.verification_notes = {
            **(document.verification_notes or {}),
            "review": {
                "decision": "VERIFIED",
                "comment": payload.comment,
                "by": str(actor.id),
                "at": now.isoformat(),
                "apH_clause": payload.apH_clause or VERIFICATION_CLAUSE,
            },
        }
        self._db.flush()
        self._audit.log(
            actor,
            "application.document.verify",
            "Document",
            document.id,
            before=before,
            after=self._document_snapshot(document),
        )
        self._write_event(
            actor,
            application,
            document,
            action="verify_document",
            comment=f"{document.doc_type} version {document.version} verified.",
            clause=payload.apH_clause or VERIFICATION_CLAUSE,
        )
        self._commit()
        return document

    def _link_deficiency(
        self,
        actor: User,
        application: Application,
        document: Document,
        reason_code: DocumentRejectionReason,
        comment: str,
        now: datetime,
    ) -> Deficiency:
        """Reuse the document's open deficiency or create a new one."""
        deficiency: Deficiency | None = None
        if document.related_deficiency_id is not None:
            candidate = self._db.get(Deficiency, document.related_deficiency_id)
            if (
                candidate is not None
                and candidate.application_id == application.id
                and candidate.status != DeficiencyStatus.CLOSED
            ):
                deficiency = candidate
        if deficiency is None:
            from app.services.workflow_effects import deficiency_due_date

            deficiency = Deficiency(
                application_id=application.id,
                category=f"DOCUMENT:{document.doc_type}",
                description=(
                    f"Re-upload {document.doc_type} (version {document.version}): "
                    f"{REJECTION_LABELS[reason_code]}. {comment}"
                ),
                raised_by=actor.id,
                status=DeficiencyStatus.OPEN,
                due_date=deficiency_due_date(self._db, now),
            )
            self._db.add(deficiency)
            self._db.flush()
            self._audit.log(
                actor,
                "deficiency.create",
                "Deficiency",
                deficiency.id,
                after={
                    "application_id": str(application.id),
                    "document_id": str(document.id),
                    "category": deficiency.category,
                    "status": deficiency.status.value,
                    "apH_clause": REJECTION_CLAUSE,
                },
            )
        deficiency.description = (
            f"Re-upload {document.doc_type}: {REJECTION_LABELS[reason_code]}. {comment}"
        )
        deficiency.status = DeficiencyStatus.OPEN
        deficiency.response_text = None
        deficiency.response_document_id = None
        deficiency.responded_at = None
        deficiency.closed_at = None
        self._db.flush()
        return deficiency

    def _open_compliance_window(
        self,
        actor: User,
        application: Application,
        document: Document,
        reason_code: DocumentRejectionReason,
        summary: str,
        now: datetime,
    ) -> Deficiency | None:
        """Move the case into ``DEFICIENCY_COMMUNICATED`` and return the item.

        The transition itself stays in ``workflow_transitions``; this method only
        asks the state machine which actions are legal for this actor and passes
        the rejection as the Deficiency Report payload that the edge expects
        (APH 1.8f, 2.3.3b).
        """
        if application.status in COMPLIANCE_WINDOW_STATUSES:
            return None
        service = WorkflowService(
            self._db,
            self._audit,
            self._clock,
            notifications=self._notifications,
            settings=self._settings,
        )
        from app.schemas.workflow import DeficiencyCreate, WorkflowActionRequest
        from app.services.workflow_effects import deficiency_due_date

        try:
            result = service.execute(
                application,
                actor=actor,
                action=WorkflowAction.COMMUNICATE_DEFICIENCY,
                payload=WorkflowActionRequest(
                    comment=summary,
                    deficiencies=[
                        DeficiencyCreate(
                            category=f"DOCUMENT:{document.doc_type}",
                            description=(
                                f"Re-upload {document.doc_type} "
                                f"(version {document.version}): "
                                f"{REJECTION_LABELS[reason_code]}. {summary}"
                            ),
                            due_date=deficiency_due_date(self._db, now),
                        )
                    ],
                ),
                request=None,
            )
        except WorkflowError as exc:
            # No legal edge for this actor or state: the rejection is still
            # recorded and a deficiency is opened directly below.
            logger.info(
                "Rejection of %s did not open the compliance window: %s",
                document.id,
                exc,
            )
            return None
        created = (result.events[0].details or {}).get("deficiency_ids") or []
        if not created:
            return None
        return self._db.get(Deficiency, uuid.UUID(str(created[0])))

    def _write_event(
        self,
        actor: User,
        application: Application,
        document: Document,
        *,
        action: str,
        comment: str,
        clause: str,
    ) -> None:
        event = WorkflowEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=application.status,
            actor_id=actor.id,
            action=action,
            comment=comment,
            details={
                "document_id": str(document.id),
                "doc_type": document.doc_type,
                "version": document.version,
                "rejection_reason_code": (
                    document.rejection_reason_code.value
                    if document.rejection_reason_code is not None
                    else None
                ),
                "related_deficiency_id": (
                    str(document.related_deficiency_id)
                    if document.related_deficiency_id is not None
                    else None
                ),
            },
            apH_clause=clause,
            created_at=self._clock.now(),
        )
        self._db.add(event)

    def _notify_rejection(
        self, actor: User, application: Application, document: Document
    ) -> None:
        from app.services.alert_engine import notify_document_rejected

        notify_document_rejected(
            self._db,
            application=application,
            document=document,
            actor=actor,
            notifications=self._notifications,
            clock=self._clock,
        )
    def _commit(self) -> None:
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    @staticmethod
    def _document_snapshot(document: Document) -> dict[str, object]:
        return {
            "application_id": str(document.application_id),
            "doc_type": document.doc_type,
            "version": document.version,
            "verification_status": document.verification_status.value,
            "rejection_reason_code": (
                document.rejection_reason_code.value
                if document.rejection_reason_code is not None
                else None
            ),
            "rejection_comment": document.rejection_comment,
            "rejected_by": str(document.rejected_by) if document.rejected_by else None,
            "rejected_at": (
                document.rejected_at.isoformat() if document.rejected_at else None
            ),
            "apH_clause": document.apH_clause,
            "related_deficiency_id": (
                str(document.related_deficiency_id)
                if document.related_deficiency_id is not None
                else None
            ),
            "superseded_by": (
                str(document.superseded_by) if document.superseded_by is not None else None
            ),
        }
