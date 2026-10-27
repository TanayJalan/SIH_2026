"""Institution-side application draft, programme and document endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.dependencies import (
    AuditDep,
    ClockDep,
    CurrentUser,
    DbSession,
    require_roles,
)
from app.core.config import Settings
from app.models.application import Application, ApplicationProgram
from app.models.document import Document
from app.models.enums import DocumentVerificationStatus, Role
from app.models.user import User
from app.schemas.application import (
    ApplicationChecklistRead,
    ApplicationCreate,
    ApplicationDetailRead,
    ApplicationProgramCreate,
    ApplicationProgramRead,
    ApplicationProgramUpdate,
    ApplicationSubmitResponse,
    ApplicationUpdate,
    DocumentChecklistRead,
    DocumentRead,
    DocumentRejectRequest,
    DocumentVerifyRequest,
)
from app.schemas.common import ErrorResponse
from app.schemas.compliance import CompliancePreviewRead, CompliancePreviewRequest
from app.schemas.fees import (
    DeficiencyReportRead,
    FeePaymentRequest,
    FeePaymentResultRead,
    FeeQuoteRead,
    RefundRequest,
    RefundResultRead,
    ReopenRequest,
    ReopenResultRead,
    SecurityDepositQuoteRead,
)
from app.services.alert_engine import NotificationService
from app.services.application_sections import (
    build_application_checklist,
    build_document_checklist,
)
from app.services.application_workspace import ApplicationWorkspaceService
from app.services.audit import AuditService
from app.services.authorization import can_access_application
from app.services.compliance import evaluate_compliance
from app.services.deficiency_report import (
    build_deficiency_report,
    render_deficiency_report_pdf,
)
from app.services.document_review import (
    DocumentReviewError,
    DocumentReviewService,
    document_allowed_actions,
    replacement_block_reason,
    reupload_count,
)
from app.services.document_shells import build_document_shell, shell_codes
from app.services.document_verification import verification_reason
from app.services.fees import FeeService

router = APIRouter(prefix="/applications", tags=["application workspace"])

InstitutionAdminUser = Annotated[
    User,
    Depends(require_roles(Role.INSTITUTION_ADMIN)),
]
ReviewerUser = Annotated[
    User,
    Depends(
        require_roles(
            Role.SCRUTINY_COMMITTEE_MEMBER,
            Role.REGULATION_BUREAU_OFFICER,
        )
    ),
]


def _load_application(db: Session, application_id: uuid.UUID) -> Application | None:
    return db.scalar(
        select(Application)
        .options(
            joinedload(Application.institution),
            selectinload(Application.programs),
        )
        .where(Application.id == application_id)
    )


def _readable_application(db: Session, user: User, application_id: uuid.UUID) -> Application:
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if not can_access_application(db, user, application):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have access to this application",
        )
    return application


def _owned_application(db: Session, user: User, application_id: uuid.UUID) -> Application:
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if user.institution_id is None or application.institution_id != user.institution_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have access to this application",
        )
    return application


def _workspace(
    db: Session,
    request: Request,
    audit: AuditService,
    clock: ClockDep,
) -> ApplicationWorkspaceService:
    settings: Settings = request.app.state.settings
    return ApplicationWorkspaceService(db, audit, settings, clock)


def _document_read(
    document: Document,
    *,
    db: Session,
    application: Application,
    actor: User,
    settings: Settings,
) -> DocumentRead:
    deficiency = document.related_deficiency
    return DocumentRead(
        id=document.id,
        application_id=document.application_id,
        doc_type=document.doc_type,
        doc_code=document.doc_code,
        signed_with_dsc=document.signed_with_dsc,
        signer_name=document.signer_name,
        valid_until=document.valid_until,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        version=document.version,
        is_latest=document.superseded_by is None,
        verification_status=document.verification_status,
        verification_reason=verification_reason(document.verification_notes),
        rejection_reason_code=document.rejection_reason_code,
        rejection_comment=document.rejection_comment,
        rejected_by=document.rejected_by,
        rejected_by_name=(
            document.rejector.name if document.rejector is not None else None
        ),
        rejected_at=document.rejected_at,
        apH_clause=document.apH_clause,
        superseded_by=document.superseded_by,
        related_deficiency_id=document.related_deficiency_id,
        deficiency_status=deficiency.status.value if deficiency is not None else None,
        deficiency_due_date=deficiency.due_date if deficiency is not None else None,
        reupload_count=reupload_count(db, document),
        max_reuploads=settings.max_reuploads_per_document,
        allowed_actions=document_allowed_actions(
            db, application, actor, document, settings
        ),
        replacement_block_reason=(
            replacement_block_reason(db, application, document, settings)
            if actor.role == Role.INSTITUTION_ADMIN
            else None
        ),
        uploaded_by=document.uploaded_by,
        uploaded_by_name=(
            document.uploader.name if document.uploader is not None else None
        ),
        created_at=document.created_at,
        download_url=(
            f"/applications/{document.application_id}/documents/{document.id}/download"
        ),
    )


def _stored_document_path(settings: Settings, storage_path: str) -> Path:
    storage_root = settings.storage_dir.resolve()
    path = (storage_root / storage_path).resolve()
    if not path.is_relative_to(storage_root) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document file not found")
    return path


@router.post(
    "",
    response_model=ApplicationDetailRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Create an application draft for the current institution",
)
def create_application(
    payload: ApplicationCreate,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ApplicationDetailRead:
    """Create a draft owned by the signed-in institution administrator."""
    workspace = _workspace(db, request, audit, clock)
    application = workspace.create_draft(current_user, payload)
    loaded = _load_application(db, application.id)
    if loaded is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Draft could not be loaded")
    return ApplicationDetailRead.model_validate(loaded)


@router.patch(
    "/{application_id}",
    response_model=ApplicationDetailRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Update draft sections",
)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ApplicationDetailRead:
    """Merge supplied form sections into a draft without changing other fields."""
    application = _owned_application(db, current_user, application_id)
    workspace = _workspace(db, request, audit, clock)
    workspace.update_data(current_user, application, payload)
    loaded = _load_application(db, application.id)
    if loaded is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Draft could not be loaded")
    return ApplicationDetailRead.model_validate(loaded)


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Delete a draft",
)
def delete_application(
    application_id: uuid.UUID,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> None:
    """Delete one draft and its stored files."""
    application = _owned_application(db, current_user, application_id)
    _workspace(db, request, audit, clock).delete_draft(current_user, application)


@router.get(
    "/{application_id}/checklist",
    response_model=ApplicationChecklistRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Get section and document completeness for an application",
)
def get_application_checklist(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApplicationChecklistRead:
    """Return all missing fields and documents used by the wizard sidebar."""
    application = _readable_application(db, current_user, application_id)
    return build_application_checklist(db, application)


@router.get(
    "/{application_id}/documents/checklist",
    response_model=DocumentChecklistRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Get the required-document checklist and upload status",
)
def get_document_checklist(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> DocumentChecklistRead:
    """Return database-driven document rules with current upload status."""
    application = _readable_application(db, current_user, application_id)
    return build_document_checklist(db, application)


@router.post(
    "/{application_id}/compliance/preview",
    response_model=CompliancePreviewRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Evaluate configured compliance rules against unsaved draft values",
)
def preview_compliance(
    application_id: uuid.UUID,
    payload: CompliancePreviewRequest,
    current_user: InstitutionAdminUser,
    db: DbSession,
    clock: ClockDep,
) -> CompliancePreviewRead:
    """Return a live, read-only rule preview for the institution form."""
    application = _owned_application(db, current_user, application_id)
    return evaluate_compliance(
        db,
        application,
        payload.data,
        evaluated_at=clock.now(),
    )


@router.get(
    "/{application_id}/documents",
    response_model=list[DocumentRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List document versions for an application",
)
def list_documents(
    application_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    only_to_recheck: bool = False,
) -> list[DocumentRead]:
    """Return every uploaded version, newest document type first.

    ``only_to_recheck`` is the Re-Scrutiny view: it keeps only the latest version
    of each type that a reviewer rejected or that the institution re-uploaded and
    is waiting for verification (APH 1.8g).
    """
    application = _readable_application(db, current_user, application_id)
    settings: Settings = request.app.state.settings
    documents = db.scalars(
        select(Document)
        .where(Document.application_id == application.id)
        .order_by(Document.doc_type.asc(), Document.version.desc())
    ).all()
    if only_to_recheck:
        documents = [
            document
            for document in documents
            if document.superseded_by is None
            and (
                document.verification_status == DocumentVerificationStatus.REJECTED
                or (
                    document.version > 1
                    and document.verification_status == DocumentVerificationStatus.PENDING
                )
            )
        ]
    return [
        _document_read(
            document,
            db=db,
            application=application,
            actor=current_user,
            settings=settings,
        )
        for document in documents
    ]


@router.get(
    "/{application_id}/documents/{document_id}/versions",
    response_model=list[DocumentRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List every version of one document",
)
def list_document_versions(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
) -> list[DocumentRead]:
    """Return the full history of a document so earlier files stay downloadable."""
    application = _readable_application(db, current_user, application_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.application_id == application.id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    settings: Settings = request.app.state.settings
    versions = db.scalars(
        select(Document)
        .where(
            Document.application_id == application.id,
            Document.doc_type == document.doc_type,
        )
        .order_by(Document.version.desc())
    ).all()
    return [
        _document_read(
            version,
            db=db,
            application=application,
            actor=current_user,
            settings=settings,
        )
        for version in versions
    ]


@router.post(
    "/{application_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Upload a document version",
)
async def upload_document(
    application_id: uuid.UUID,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
    doc_type: Annotated[str, Form(min_length=1, max_length=100)],
    file: Annotated[UploadFile, File()],
    signed_with_dsc: Annotated[bool, Form()] = False,
    signer_name: Annotated[str | None, Form(max_length=255)] = None,
    valid_until: Annotated[date | None, Form()] = None,
) -> DocumentRead:
    """Store a PDF, JPG or PNG up to 10 MB as the next version for its type."""
    application = _owned_application(db, current_user, application_id)
    document = await _workspace(db, request, audit, clock).upload_document(
        current_user,
        application,
        doc_type=doc_type,
        upload=file,
        signed_with_dsc=signed_with_dsc,
        signer_name=signer_name,
        valid_until=valid_until,
    )
    return _document_read(
        document,
        db=db,
        application=application,
        actor=current_user,
        settings=request.app.state.settings,
    )


@router.post(
    "/{application_id}/documents/{document_id}/reupload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Replace a rejected or flagged document",
)
async def reupload_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
    file: Annotated[UploadFile, File()],
    signed_with_dsc: Annotated[bool, Form()] = False,
    signer_name: Annotated[str | None, Form(max_length=255)] = None,
    valid_until: Annotated[date | None, Form()] = None,
) -> DocumentRead:
    """Create version N+1 for a rejected/flagged document inside a compliance window."""
    application = _load_application(db, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.application_id == application.id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    replacement, warnings = await _workspace(db, request, audit, clock).reupload_document(
        current_user,
        application,
        document,
        upload=file,
        signed_with_dsc=signed_with_dsc,
        signer_name=signer_name,
        valid_until=valid_until,
    )
    read = _document_read(
        replacement,
        db=db,
        application=application,
        actor=current_user,
        settings=request.app.state.settings,
    )
    read.warnings = warnings
    return read


@router.post(
    "/{application_id}/documents/{document_id}/reject",
    response_model=DocumentRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Reject a document and ask the institution for a replacement",
)
def reject_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentRejectRequest,
    request: Request,
    current_user: ReviewerUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> DocumentRead:
    """Reject one document, link a deficiency and notify the institution (APH 1.8f)."""
    application = _readable_application(db, current_user, application_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.application_id == application.id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    settings: Settings = request.app.state.settings
    service = DocumentReviewService(
        db,
        audit,
        clock,
        settings,
        notifications=NotificationService.from_settings(settings),
    )
    try:
        rejected, _ = service.reject(current_user, application, document, payload)
    except DocumentReviewError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return _document_read(
        rejected,
        db=db,
        application=application,
        actor=current_user,
        settings=settings,
    )


@router.post(
    "/{application_id}/documents/{document_id}/verify",
    response_model=DocumentRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Mark a re-uploaded document as verified",
)
def verify_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentVerifyRequest,
    request: Request,
    current_user: ReviewerUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> DocumentRead:
    """Verify a replacement so Re-Scrutiny can close the listed deficiency (APH 1.8g)."""
    application = _readable_application(db, current_user, application_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.application_id == application.id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    settings: Settings = request.app.state.settings
    service = DocumentReviewService(
        db,
        audit,
        clock,
        settings,
        notifications=NotificationService.from_settings(settings),
    )
    try:
        verified = service.verify(current_user, application, document, payload)
    except DocumentReviewError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return _document_read(
        verified,
        db=db,
        application=application,
        actor=current_user,
        settings=settings,
    )


@router.get(
    "/{application_id}/documents/{document_id}/download",
    response_class=FileResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Download a document version",
)
def download_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
) -> FileResponse:
    """Stream a stored document after checking application access."""
    application = _readable_application(db, current_user, application_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.application_id == application.id,
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    settings: Settings = request.app.state.settings
    path = _stored_document_path(settings, document.storage_path)
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.filename,
    )


@router.get(
    "/{application_id}/programs",
    response_model=list[ApplicationProgramRead],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List programmes on an application",
)
def list_programs(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[ApplicationProgramRead]:
    """Return programmes in creation order."""
    application = _readable_application(db, current_user, application_id)
    programs = db.scalars(
        select(ApplicationProgram)
        .where(ApplicationProgram.application_id == application.id)
        .order_by(ApplicationProgram.created_at.asc())
    ).all()
    return [ApplicationProgramRead.model_validate(program) for program in programs]


@router.post(
    "/{application_id}/programs",
    response_model=ApplicationProgramRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Add a programme to a draft",
)
def add_program(
    application_id: uuid.UUID,
    payload: ApplicationProgramCreate,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ApplicationProgramRead:
    """Add a programme requested in the application."""
    application = _owned_application(db, current_user, application_id)
    program = _workspace(db, request, audit, clock).add_program(
        current_user, application, payload
    )
    return ApplicationProgramRead.model_validate(program)


@router.patch(
    "/{application_id}/programs/{program_id}",
    response_model=ApplicationProgramRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Edit a programme on a draft",
)
def update_program(
    application_id: uuid.UUID,
    program_id: uuid.UUID,
    payload: ApplicationProgramUpdate,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ApplicationProgramRead:
    """Update any supplied programme fields."""
    application = _owned_application(db, current_user, application_id)
    program = db.scalar(
        select(ApplicationProgram).where(
            ApplicationProgram.id == program_id,
            ApplicationProgram.application_id == application.id,
        )
    )
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    updated = _workspace(db, request, audit, clock).update_program(
        current_user, application, program, payload
    )
    return ApplicationProgramRead.model_validate(updated)


@router.delete(
    "/{application_id}/programs/{program_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Delete a programme from a draft",
)
def delete_program(
    application_id: uuid.UUID,
    program_id: uuid.UUID,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> None:
    """Remove a programme from a draft."""
    application = _owned_application(db, current_user, application_id)
    program = db.scalar(
        select(ApplicationProgram).where(
            ApplicationProgram.id == program_id,
            ApplicationProgram.application_id == application.id,
        )
    )
    if program is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    _workspace(db, request, audit, clock).delete_program(current_user, application, program)


@router.post(
    "/{application_id}/submit",
    response_model=ApplicationSubmitResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
    summary="Submit a complete draft",
)
def submit_application(
    application_id: uuid.UUID,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ApplicationSubmitResponse:
    """Validate completeness, set the SLA due date and submit the draft."""
    application = _owned_application(db, current_user, application_id)
    _workspace(db, request, audit, clock).submit(
        current_user,
        application,
        request=request,
    )
    loaded = _load_application(db, application.id)
    if loaded is None or loaded.submitted_at is None or loaded.sla_due_at is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Submission completed but the application could not be loaded",
        )
    return ApplicationSubmitResponse(
        application=ApplicationDetailRead.model_validate(loaded),
        submitted_at=loaded.submitted_at,
        sla_due_at=loaded.sla_due_at,
    )


def _fee_service(db: Session, audit: AuditService, clock: ClockDep) -> FeeService:
    """Build the fee service for the current request."""
    return FeeService(db, audit, clock)


@router.get(
    "/{application_id}/fee",
    response_model=FeeQuoteRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Quote the TER, late penalty and extra committee charges",
)
def get_fee_quote(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
    extra_scrutiny: bool = False,
    extra_evc_mode: str | None = None,
) -> FeeQuoteRead:
    """Return the computed fee position for the application (APH Table 2.1)."""
    application = _readable_application(db, current_user, application_id)
    fee_service = _fee_service(db, audit, clock)
    fee_service.flag_late_submission(application, clock.now())
    return fee_service.quote(
        application,
        extra_scrutiny=extra_scrutiny,
        extra_evc_mode=extra_evc_mode,
    )


@router.post(
    "/{application_id}/fee/pay",
    response_model=FeePaymentResultRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Pay the TER through the simulated gateway",
)
def pay_application_fee(
    application_id: uuid.UUID,
    payload: FeePaymentRequest,
    request: Request,
    current_user: InstitutionAdminUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> FeePaymentResultRead:
    """Record one immutable FeeTransaction per quotation line and stamp the receipt."""
    application = _owned_application(db, current_user, application_id)
    fee_service = _fee_service(db, audit, clock)
    fee_service.flag_late_submission(application, clock.now())
    return fee_service.pay_ter(
        current_user,
        application,
        request=request,
    )


@router.post(
    "/{application_id}/fee/refund",
    response_model=RefundResultRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Record a TER refund for a documented reason",
)
def refund_application_fee(
    application_id: uuid.UUID,
    payload: RefundRequest,
    request: Request,
    current_user: Annotated[
        User,
        Depends(
            require_roles(Role.INSTITUTION_ADMIN, Role.REGULATION_BUREAU_OFFICER)
        ),
    ],
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> RefundResultRead:
    """Refund TER minus the APH deduction; it is never netted into a later payment."""
    application = _readable_application(db, current_user, application_id)
    return _fee_service(db, audit, clock).refund(
        current_user,
        application,
        payload,
        request=request,
    )


@router.get(
    "/{application_id}/security-deposit-quote",
    response_model=SecurityDepositQuoteRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Quote the Table 1.4 Security Deposit and penalty window",
)
def get_security_deposit_quote(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
    as_of: date | None = None,
) -> SecurityDepositQuoteRead:
    """Return the deposit per programme, doubled when the campus is leased (APH 2.25f)."""
    application = _readable_application(db, current_user, application_id)
    return _fee_service(db, audit, clock).security_deposit_quote(application, as_of=as_of)


@router.post(
    "/{application_id}/reopen",
    response_model=ReopenResultRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    summary="Reopen a submitted application once (Regulation Bureau)",
)
def reopen_application(
    application_id: uuid.UUID,
    payload: ReopenRequest,
    request: Request,
    current_user: Annotated[
        User, Depends(require_roles(Role.REGULATION_BUREAU_OFFICER))
    ],
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> ReopenResultRead:
    """Collect a fresh TER and late penalty, then unlock the application once (APH 2.3.3d-e)."""
    application = _readable_application(db, current_user, application_id)
    return _fee_service(db, audit, clock).reopen(
        current_user,
        application,
        payload,
        request=request,
    )


@router.get(
    "/{application_id}/deficiency-report",
    response_model=DeficiencyReportRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Generate the printable Deficiency Report or a Nil Deficiency banner",
)
def get_deficiency_report(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    include_not_assessed: bool = True,
) -> DeficiencyReportRead:
    """Evaluate the current application version and list deficiencies with clauses."""
    application = _readable_application(db, current_user, application_id)
    return build_deficiency_report(
        db,
        application,
        evaluated_at=clock.now(),
        include_not_assessed=include_not_assessed,
    )


@router.get(
    "/{application_id}/deficiency-report.pdf",
    responses={
        status.HTTP_200_OK: {"content": {"application/pdf": {}}},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Download the Deficiency Report as a PDF",
)
def download_deficiency_report_pdf(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    include_not_assessed: bool = True,
) -> StreamingResponse:
    """Render the Deficiency Report to PDF for the case file (APH 2.3.3b)."""
    application = _readable_application(db, current_user, application_id)
    report = build_deficiency_report(
        db,
        application,
        evaluated_at=clock.now(),
        include_not_assessed=include_not_assessed,
    )
    buffer = render_deficiency_report_pdf(report)
    filename = f"deficiency-report-{application.portal_application_no or application.id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{application_id}/document-shells",
    response_model=dict[str, str],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="List downloadable document shells",
)
def list_document_shells(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Return the document codes that have a generated printable shell."""
    _readable_application(db, current_user, application_id)
    return shell_codes()


@router.get(
    "/{application_id}/document-shells/{doc_code}",
    response_class=Response,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Download a printable document shell",
)
def download_document_shell(
    application_id: uuid.UUID,
    doc_code: str,
    current_user: CurrentUser,
    db: DbSession,
) -> Response:
    """Generate the Affidavit 2, Format 3 or Certificate shell as printable HTML."""
    application = _readable_application(db, current_user, application_id)
    try:
        shell = build_document_shell(application, doc_code)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document shell not found") from exc
    return Response(
        content=shell.content,
        media_type=shell.media_type,
        headers={"Content-Disposition": f'attachment; filename="{shell.filename}"'},
    )
