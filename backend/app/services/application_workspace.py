"""Institution-side application draft, programme, document and submission service."""

from __future__ import annotations

import copy
import logging
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import SimulatedClock
from app.core.config import Settings
from app.models.application import Application, ApplicationProgram
from app.models.application_type_route import ApplicationTypeRoute
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    ApplicationStatus,
    ApplicationTrack,
    DeficiencyStatus,
    DocumentVerificationStatus,
    Role,
    WorkflowAction,
    WorkflowStage,
)
from app.models.required_document import RequiredDocument
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.schemas.application import (
    ApplicationChecklistRead,
    ApplicationCreate,
    ApplicationProgramCreate,
    ApplicationProgramUpdate,
    ApplicationUpdate,
)
from app.schemas.workflow import WorkflowActionRequest
from app.services import workflow
from app.services.alert_engine import NotificationService
from app.services.application_sections import build_application_checklist
from app.services.audit import AuditService
from app.services.compliance import evaluate_application
from app.services.document_review import replacement_block_reason
from app.services.document_verification import (
    certificate_requires_validity,
    name_mismatch_warning,
    pdf_readability_error,
    verify_document,
)
from app.services.fees import FeeService
from app.services.portal_number import next_portal_application_no

logger = logging.getLogger(__name__)

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
_MEDIA_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
_SAFE_DOC_TYPE = re.compile(r"^[A-Z0-9_]+$")

_NEW_INSTITUTION_TYPES = frozenset(
    {
        "NEW_INSTITUTION",
        "NEW_INSTITUTION_OTHER_REGULATOR",
        "CLOSURE_AND_NEW_INSTITUTION",
    }
)
"""Chapter I variants that start a brand-new institution (APH 1.3)."""


def _track_for(type_code: str) -> ApplicationTrack:
    """Return the APH chapter track that owns an application type.

    Chapter I types create an institution, Chapter IV types come from a
    university and Chapter V types are ODL/online. Everything else is an
    existing institution filing under Chapter II.
    """
    if type_code in _NEW_INSTITUTION_TYPES:
        return ApplicationTrack.NEW_INSTITUTION
    if type_code == "UNIVERSITY":
        return ApplicationTrack.UNIVERSITY
    if type_code == "ODL_ONLINE":
        return ApplicationTrack.ODL
    return ApplicationTrack.EXISTING


class WorkspaceError(Exception):
    """An expected workspace failure with an HTTP representation."""

    def __init__(self, status_code: int, detail: str | dict[str, Any]) -> None:
        super().__init__(detail if isinstance(detail, str) else detail.get("message", "error"))
        self.status_code = status_code
        self.detail = detail


class SubmissionBlockedError(WorkspaceError):
    """Submission failed because mandatory sections or documents are missing."""

    def __init__(self, checklist: ApplicationChecklistRead) -> None:
        self.checklist = checklist
        detail = {
            "message": "Application cannot be submitted yet. Complete the missing items.",
            "missing": [item.model_dump(mode="json") for item in checklist.missing],
            "percentage": checklist.percentage,
        }
        super().__init__(422, detail)


class DocumentUploadError(WorkspaceError):
    """An uploaded file failed validation."""


class PaymentRequiredError(WorkspaceError):
    """Submission was attempted before the TER (and any late penalty) was paid."""

    def __init__(self, quote: Any) -> None:
        super().__init__(
            409,
            {
                "message": "TER payment is required before this application can be submitted.",
                "total_paise": quote.total_paise,
                "due_paise": quote.due_paise,
                "late_submission": quote.late_submission,
                "lines": [line.model_dump(mode="json") for line in quote.lines],
            },
        )


class ApplicationWorkspaceService:
    """Own the transaction and audit trail for institution write actions."""

    def __init__(
        self,
        db: Session,
        audit: AuditService,
        settings: Settings,
        clock: SimulatedClock,
    ) -> None:
        self._db = db
        self._audit = audit
        self._settings = settings
        self._clock = clock

    def create_draft(self, actor: User, payload: ApplicationCreate) -> Application:
        """Create a draft owned by the actor's institution.

        The APH routing table decides the category, the required steps and
        whether the type is year-round. A type that is not in the table is
        rejected so the seeded configuration stays authoritative.
        """
        if actor.institution_id is None:
            raise WorkspaceError(403, "Your account is not linked to an institution")

        route = self._db.scalar(
            select(ApplicationTypeRoute).where(
                ApplicationTypeRoute.type == payload.application_type
            )
        )
        if route is None:
            raise WorkspaceError(
                422,
                "This application type is not configured. Ask an administrator to add it "
                "to the APH routing table.",
            )

        track = payload.track or _track_for(route.type)
        category = payload.category or route.category
        if category != route.category:
            raise WorkspaceError(
                422,
                f"{route.type} is a {route.category.value} application and cannot be "
                f"filed as {category.value}.",
            )

        reference = f"APP-{payload.academic_year[:4]}-{uuid.uuid4().hex[:8].upper()}"
        application = Application(
            institution_id=actor.institution_id,
            track=track,
            application_type=route.type,
            category=route.category,
            portal_application_no=next_portal_application_no(
                self._db, payload.academic_year
            ),
            academic_year=payload.academic_year,
            status=ApplicationStatus.DRAFT,
            current_stage=WorkflowStage.APPLICATION,
            data={"reference": reference},
        )
        self._db.add(application)
        self._db.flush()
        self._audit.log(
            actor,
            "application.create",
            "Application",
            application.id,
            after=self._snapshot(application),
        )
        self._commit()
        return application

    def update_data(
        self,
        actor: User,
        application: Application,
        payload: ApplicationUpdate,
    ) -> Application:
        """Merge validated section fields into a draft's JSON payload."""
        self._ensure_draft(application)
        before = copy.deepcopy(application.data)
        incoming = payload.data.model_dump(mode="json", exclude_unset=True)
        merged = copy.deepcopy(application.data) if isinstance(application.data, dict) else {}

        for section_key, section_value in incoming.items():
            existing = merged.get(section_key)
            if section_value is None:
                merged.pop(section_key, None)
            elif isinstance(section_value, dict) and isinstance(existing, dict):
                merged[section_key] = {**existing, **section_value}
            else:
                merged[section_key] = section_value

        application.data = merged
        self._db.flush()
        self._audit.log(
            actor,
            "application.update",
            "Application",
            application.id,
            before={"data": before},
            after={"data": application.data},
        )
        self._commit()
        self._reevaluate_compliance(application)
        return application

    def delete_draft(self, actor: User, application: Application) -> None:
        """Delete a draft and remove its stored files after the DB commits."""
        self._ensure_draft(application)
        application_id = application.id
        before = self._snapshot(application)
        self._db.delete(application)
        self._audit.log(
            actor,
            "application.delete",
            "Application",
            application_id,
            before=before,
        )
        self._commit()
        self._remove_application_files(application_id)

    def add_program(
        self,
        actor: User,
        application: Application,
        payload: ApplicationProgramCreate,
    ) -> ApplicationProgram:
        """Add a programme to a draft."""
        self._ensure_draft(application)
        program = ApplicationProgram(application_id=application.id, **payload.model_dump())
        self._db.add(program)
        self._db.flush()
        self._audit.log(
            actor,
            "application.program.create",
            "ApplicationProgram",
            program.id,
            after=self._program_snapshot(program),
        )
        self._commit()
        self._reevaluate_compliance(application)
        return program

    def update_program(
        self,
        actor: User,
        application: Application,
        program: ApplicationProgram,
        payload: ApplicationProgramUpdate,
    ) -> ApplicationProgram:
        """Apply supplied fields to a programme on a draft."""
        self._ensure_draft(application)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return program
        before = self._program_snapshot(program)
        for key, value in changes.items():
            setattr(program, key, value)
        self._db.flush()
        self._audit.log(
            actor,
            "application.program.update",
            "ApplicationProgram",
            program.id,
            before=before,
            after=self._program_snapshot(program),
        )
        self._commit()
        self._reevaluate_compliance(application)
        return program

    def delete_program(
        self,
        actor: User,
        application: Application,
        program: ApplicationProgram,
    ) -> None:
        """Delete a programme from a draft."""
        self._ensure_draft(application)
        program_id = program.id
        before = self._program_snapshot(program)
        self._db.delete(program)
        self._audit.log(
            actor,
            "application.program.delete",
            "ApplicationProgram",
            program_id,
            before=before,
        )
        self._commit()
        self._reevaluate_compliance(application)

    async def upload_document(
        self,
        actor: User,
        application: Application,
        *,
        doc_type: str,
        upload: UploadFile,
        signed_with_dsc: bool = True,
        signer_name: str | None = None,
        valid_until: date | None = None,
    ) -> Document:
        """Validate, store and version a draft document.

        A document without a DSC is still stored for reference, but it is marked
        ``REJECTED`` so the checklist and submission gate treat it as invalid
        (APH 1.4.3, 1.4.6).
        """
        self._ensure_draft(application)
        document, _ = await self._store_document(
            actor,
            application,
            doc_type=doc_type,
            upload=upload,
            signed_with_dsc=signed_with_dsc,
            signer_name=signer_name,
            valid_until=valid_until,
            strict=False,
        )
        return document

    async def reupload_document(
        self,
        actor: User,
        application: Application,
        document: Document,
        *,
        upload: UploadFile,
        signed_with_dsc: bool,
        signer_name: str | None,
        valid_until: date | None,
    ) -> tuple[Document, list[str]]:
        """Replace a rejected or flagged document in a compliance window.

        Only the owning institution administrator may replace a document. The
        replacement becomes version N+1, the old row is superseded but kept
        downloadable, verification resets to ``PENDING`` and the linked
        deficiency is marked responded (APH 1.4.3, 1.8f, 2.4).
        """
        if (
            actor.role != Role.INSTITUTION_ADMIN
            or actor.institution_id is None
            or actor.institution_id != application.institution_id
        ):
            raise DocumentUploadError(
                409,
                "Only the institution administrator of the owning institution may "
                "replace a document.",
            )
        block = replacement_block_reason(
            self._db, application, document, self._settings
        )
        if block is not None:
            raise DocumentUploadError(409, block)

        replacement, warnings = await self._store_document(
            actor,
            application,
            doc_type=document.doc_type,
            upload=upload,
            signed_with_dsc=signed_with_dsc,
            signer_name=signer_name,
            valid_until=valid_until,
            strict=True,
            supersedes=document,
        )
        deficiency = self._respond_to_deficiency(actor, application, document, replacement)
        self._write_reupload_event(actor, application, replacement, deficiency)
        self._commit()
        self._notify_reupload(actor, application, replacement)
        self._reevaluate_compliance(application)
        return replacement, warnings

    async def _store_document(
        self,
        actor: User,
        application: Application,
        *,
        doc_type: str,
        upload: UploadFile,
        signed_with_dsc: bool,
        signer_name: str | None,
        valid_until: date | None,
        strict: bool,
        supersedes: Document | None = None,
    ) -> tuple[Document, list[str]]:
        """Run upload validation and persist one new document version."""
        normalised_doc_type = doc_type.strip().upper()
        if not _SAFE_DOC_TYPE.fullmatch(normalised_doc_type):
            raise DocumentUploadError(422, "Document type is not valid")

        rule = self._db.scalar(
            select(RequiredDocument).where(
                RequiredDocument.application_type == application.application_type,
                RequiredDocument.doc_type == normalised_doc_type,
            )
        )
        if rule is None:
            raise DocumentUploadError(
                422,
                f"{normalised_doc_type} is not part of this application's document checklist",
            )

        data = await upload.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise DocumentUploadError(413, "Document must be 10 MB or smaller")
        if not data:
            raise DocumentUploadError(422, "The uploaded document is empty")

        media_type = self._detect_media_type(data)
        if media_type is None:
            raise DocumentUploadError(415, "Only PDF, JPG or PNG documents are accepted")

        today = self._clock.now().date()
        if strict:
            errors = self._replacement_field_errors(
                doc_type=normalised_doc_type,
                doc_code=rule.doc_code,
                signed_with_dsc=signed_with_dsc,
                signer_name=signer_name,
                valid_until=valid_until,
                today=today,
            )
            if media_type == "application/pdf":
                pdf_error = pdf_readability_error(data)
                if pdf_error is not None:
                    errors["file"] = pdf_error
            if errors:
                raise DocumentUploadError(
                    422,
                    {
                        "message": "The replacement document failed validation.",
                        "errors": errors,
                    },
                )

        original_filename = self._safe_filename(upload.filename, media_type)
        verification = verify_document(
            doc_type=normalised_doc_type,
            filename=original_filename,
            data=data,
        )
        verification_status = verification.status
        verification_reason_text = verification.reason
        verification_notes: dict[str, object] = {
            "engine": "document-check-v1",
            "reason": verification_reason_text,
            "matched_terms": list(verification.matched_terms),
            "signed_with_dsc": signed_with_dsc,
        }
        if strict:
            verification_status = DocumentVerificationStatus.PENDING
            verification_reason_text = (
                "Replacement received. Awaiting reviewer verification (APH 1.8g)."
            )
            verification_notes = {
                "engine": "document-check-v1",
                "reason": verification_reason_text,
                "automated_status": verification.status.value,
                "automated_reason": verification.reason,
                "matched_terms": list(verification.matched_terms),
                "signed_with_dsc": signed_with_dsc,
                "signer_name": signer_name,
                "valid_until": valid_until.isoformat() if valid_until else None,
            }
        elif not signed_with_dsc:
            verification_status = DocumentVerificationStatus.REJECTED
            verification_reason_text = (
                "The upload is not digitally signed (DSC). APH 1.4.6 requires every "
                "document to be DSC-signed; an unsigned document cannot be used for submission."
            )
            verification_notes["reason"] = verification_reason_text

        warnings: list[str] = []
        warning = name_mismatch_warning(
            application.institution.name,
            filename=original_filename,
            data=data,
        )
        if warning is not None:
            warnings.append(warning)

        storage_root = self._settings.storage_dir.resolve()
        relative_dir = Path(str(application.id)) / normalised_doc_type
        target = storage_root / relative_dir / f"{uuid.uuid4().hex}{_MEDIA_TYPES[media_type]}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        try:
            max_version = (
                self._db.scalar(
                    select(func.max(Document.version)).where(
                        Document.application_id == application.id,
                        Document.doc_type == normalised_doc_type,
                    )
                )
                or 0
            )
            document = Document(
                application_id=application.id,
                doc_type=normalised_doc_type,
                doc_code=rule.doc_code,
                signed_with_dsc=signed_with_dsc,
                signer_name=signer_name,
                valid_until=valid_until,
                filename=original_filename,
                content_type=media_type,
                size_bytes=len(data),
                storage_path=target.relative_to(storage_root).as_posix(),
                uploaded_by=actor.id,
                version=max_version + 1,
                verification_status=verification_status,
                verification_notes=verification_notes,
                related_deficiency_id=(
                    supersedes.related_deficiency_id if supersedes is not None else None
                ),
            )
            self._db.add(document)
            self._db.flush()
            if supersedes is not None:
                supersedes.superseded_by = document.id
                self._db.flush()
            self._audit.log(
                actor,
                (
                    "application.document.reupload"
                    if supersedes is not None
                    else "application.document.upload"
                ),
                "Document",
                document.id,
                after={
                    "application_id": str(application.id),
                    "doc_type": document.doc_type,
                    "doc_code": document.doc_code,
                    "signed_with_dsc": document.signed_with_dsc,
                    "signer_name": document.signer_name,
                    "valid_until": (
                        document.valid_until.isoformat() if document.valid_until else None
                    ),
                    "filename": document.filename,
                    "content_type": document.content_type,
                    "size_bytes": document.size_bytes,
                    "version": document.version,
                    "verification_status": document.verification_status.value,
                    "verification_reason": verification_reason_text,
                    "supersedes": str(supersedes.id) if supersedes is not None else None,
                    "related_deficiency_id": (
                        str(document.related_deficiency_id)
                        if document.related_deficiency_id is not None
                        else None
                    ),
                    "apH_clause": "APH 1.4.3" if supersedes is not None else None,
                },
            )
            self._db.flush()
        except Exception:
            self._db.rollback()
            target.unlink(missing_ok=True)
            raise

        if supersedes is None:
            self._commit()
            self._reevaluate_compliance(application)
        return document, warnings

    def _replacement_field_errors(
        self,
        *,
        doc_type: str,
        doc_code: str | None,
        signed_with_dsc: bool,
        signer_name: str | None,
        valid_until: date | None,
        today: date,
    ) -> dict[str, str]:
        """Return per-field messages the re-upload dialog can show inline."""
        errors: dict[str, str] = {}
        if not signed_with_dsc:
            errors["signed_with_dsc"] = (
                "Tick the DSC attestation. Every upload must be digitally signed "
                "(APH 1.4.3)."
            )
        if not (signer_name or "").strip():
            errors["signer_name"] = "Enter the name of the person who signed the document."
        if certificate_requires_validity(doc_type, doc_code):
            if valid_until is None:
                errors["valid_until"] = (
                    "Enter the certificate's validity date (APH Annexure-2.1)."
                )
            elif valid_until < today:
                errors["valid_until"] = (
                    "The certificate has already expired. Upload a current certificate "
                    "(APH Annexure-2.1)."
                )
        return errors

    def _respond_to_deficiency(
        self,
        actor: User,
        application: Application,
        previous: Document,
        replacement: Document,
    ) -> Deficiency | None:
        """Mark the linked deficiency responded with the replacement as evidence."""
        if replacement.related_deficiency_id is None:
            return None
        deficiency = self._db.get(Deficiency, replacement.related_deficiency_id)
        if deficiency is None or deficiency.application_id != application.id:
            return None
        deficiency.response_text = (
            f"Re-uploaded {replacement.doc_type} as version {replacement.version} "
            f"(APH 2.4)."
        )
        deficiency.response_document_id = replacement.id
        deficiency.status = DeficiencyStatus.RESPONDED
        deficiency.responded_at = self._clock.now()
        deficiency.closed_at = None
        self._audit.log(
            actor,
            "deficiency.respond",
            "Deficiency",
            deficiency.id,
            before={"status": DeficiencyStatus.OPEN.value},
            after={
                "status": deficiency.status.value,
                "response_document_id": str(replacement.id),
                "superseded_document_id": str(previous.id),
                "apH_clause": "APH 2.4",
            },
        )
        return deficiency

    def _write_reupload_event(
        self,
        actor: User,
        application: Application,
        replacement: Document,
        deficiency: Deficiency | None,
    ) -> None:
        """Record the replacement on the case timeline (APH 1.8f, 2.4)."""
        self._db.add(
            WorkflowEvent(
                application_id=application.id,
                from_status=application.status,
                to_status=application.status,
                actor_id=actor.id,
                action="reupload_document",
                comment=(
                    f"{replacement.doc_type} version {replacement.version} re-uploaded "
                    "with DSC attestation."
                ),
                details={
                    "document_id": str(replacement.id),
                    "doc_type": replacement.doc_type,
                    "version": replacement.version,
                    "related_deficiency_id": (
                        str(deficiency.id) if deficiency is not None else None
                    ),
                },
                apH_clause="APH 2.4",
                created_at=self._clock.now(),
            )
        )
        self._db.flush()

    def _notify_reupload(
        self, actor: User, application: Application, replacement: Document
    ) -> None:
        from app.services.alert_engine import notify_document_reuploaded

        notify_document_reuploaded(
            self._db,
            application=application,
            document=replacement,
            actor=actor,
            notifications=NotificationService.from_settings(self._settings),
            clock=self._clock,
        )


    def submit(
        self,
        actor: User,
        application: Application,
        *,
        request: Request | None = None,
    ) -> workflow.WorkflowResult:
        """Validate readiness, confirm TER payment and submit through the state machine."""
        self._ensure_draft(application)
        checklist = build_application_checklist(self._db, application)
        if not checklist.can_submit:
            raise SubmissionBlockedError(checklist)

        route = self._db.scalar(
            select(ApplicationTypeRoute).where(
                ApplicationTypeRoute.type == application.application_type
            )
        )
        fee_service = FeeService(self._db, self._audit, self._clock)
        if route is not None and not route.no_ter:
            fee_service.flag_late_submission(application, self._clock.now())
            quote = fee_service.quote(application)
            if quote.total_paise > 0 and not quote.is_paid:
                raise PaymentRequiredError(quote)

        service = workflow.WorkflowService(
            self._db,
            self._audit,
            self._clock,
            notifications=NotificationService.from_settings(self._settings),
            settings=self._settings,
        )
        result = service.execute(
            application,
            actor=actor,
            action=WorkflowAction.SUBMIT,
            payload=WorkflowActionRequest(),
            request=request,
        )
        self._reevaluate_compliance(application)
        return result

    def _ensure_draft(self, application: Application) -> None:
        if application.status != ApplicationStatus.DRAFT:
            raise WorkspaceError(409, "Only draft applications can be changed")

    def _reevaluate_compliance(
        self,
        application: Application,
        trigger: str = "application_update",
    ) -> None:
        """Re-run compliance monitoring after a data or submission change.

        Failures roll back the evaluation only; the caller's change is already
        committed and must not be lost, so the error is logged and re-raised
        for the API layer to surface.
        """
        try:
            evaluate_application(
                self._db,
                application,
                evaluated_at=self._clock.now(),
                trigger=trigger,
            )
        except Exception:
            self._db.rollback()
            logger.exception(
                "Compliance evaluation failed after application %s update.",
                application.reference,
            )
            raise

    def _commit(self) -> None:
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def _remove_application_files(self, application_id: uuid.UUID) -> None:
        storage_root = self._settings.storage_dir.resolve()
        application_dir = (storage_root / str(application_id)).resolve()
        if not application_dir.is_relative_to(storage_root):
            return
        import shutil

        shutil.rmtree(application_dir, ignore_errors=True)

    @staticmethod
    def _snapshot(application: Application) -> dict[str, Any]:
        return {
            "reference": application.reference,
            "application_type": application.application_type,
            "academic_year": application.academic_year,
            "status": application.status.value,
            "current_stage": application.current_stage.value,
            "submitted_at": (
                application.submitted_at.isoformat() if application.submitted_at else None
            ),
            "sla_due_at": (
                application.sla_due_at.isoformat() if application.sla_due_at else None
            ),
            "data": application.data,
        }

    @staticmethod
    def _program_snapshot(program: ApplicationProgram) -> dict[str, Any]:
        return {
            "application_id": str(program.application_id),
            "program_name": program.program_name,
            "level": program.level,
            "intake": program.intake,
            "faculty_count": program.faculty_count,
            "lab_count": program.lab_count,
        }

    @staticmethod
    def _safe_filename(raw_name: str | None, media_type: str) -> str:
        fallback = f"document{_MEDIA_TYPES[media_type]}"
        if not raw_name:
            return fallback
        name = Path(raw_name).name.strip()
        printable = "".join(character for character in name if character.isprintable())
        return printable[:255] or fallback

    @staticmethod
    def _detect_media_type(data: bytes) -> str | None:
        if data.startswith(b"%PDF-"):
            return "application/pdf"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        return None
