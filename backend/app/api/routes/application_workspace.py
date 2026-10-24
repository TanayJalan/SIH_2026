"""Institution-side application draft, programme and document endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
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
from app.models.enums import Role
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
)
from app.schemas.common import ErrorResponse
from app.schemas.compliance import CompliancePreviewRead, CompliancePreviewRequest
from app.services.application_sections import (
    build_application_checklist,
    build_document_checklist,
)
from app.services.application_workspace import ApplicationWorkspaceService
from app.services.audit import AuditService
from app.services.authorization import can_access_application
from app.services.compliance import evaluate_compliance
from app.services.document_verification import verification_reason

router = APIRouter(prefix="/applications", tags=["application workspace"])

InstitutionAdminUser = Annotated[
    User,
    Depends(require_roles(Role.INSTITUTION_ADMIN)),
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


def _document_read(document: Document) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        application_id=document.application_id,
        doc_type=document.doc_type,
        filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        version=document.version,
        verification_status=document.verification_status,
        verification_reason=verification_reason(document.verification_notes),
        uploaded_by=document.uploaded_by,
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
    current_user: CurrentUser,
    db: DbSession,
) -> list[DocumentRead]:
    """Return every uploaded version, newest document type first."""
    application = _readable_application(db, current_user, application_id)
    documents = db.scalars(
        select(Document)
        .where(Document.application_id == application.id)
        .order_by(Document.doc_type.asc(), Document.version.desc())
    ).all()
    return [_document_read(document) for document in documents]


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
) -> DocumentRead:
    """Store a PDF, JPG or PNG up to 10 MB as the next version for its type."""
    application = _owned_application(db, current_user, application_id)
    document = await _workspace(db, request, audit, clock).upload_document(
        current_user,
        application,
        doc_type=doc_type,
        upload=file,
    )
    return _document_read(document)


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
