"""Decision letter endpoints: listing, PDF download and acknowledgement.

Letters are the public artefacts of the workflow. The PDF is served from the
storage directory the letter row points at, the acknowledgement records that
the institution has seen the instrument, and both actions are audited
(APH 1.10, 2.23.3, 2.24a).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.api.dependencies import AuditDep, ClockDep, CurrentUser, DbSession
from app.models.application import Application
from app.models.decision import DecisionLetter
from app.models.enums import Role
from app.schemas.common import ErrorResponse
from app.schemas.workflow import DecisionLetterRead
from app.services.authorization import can_access_application
from app.services.decision_letters import letter_path

router = APIRouter(prefix="/letters", tags=["letters"])


def _readable_letter(
    db: DbSession,
    user: CurrentUser,
    letter_id: uuid.UUID,
) -> tuple[DecisionLetter, Application]:
    """Load a letter and its application, enforcing record-level access."""
    letter = db.get(DecisionLetter, letter_id)
    if letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Letter not found")
    application = db.get(Application, letter.application_id)
    if application is None or not can_access_application(db, user, application):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You do not have access to this letter",
        )
    return letter, application


@router.get(
    "/{letter_id}",
    response_model=DecisionLetterRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Read one published decision letter",
)
def get_letter(
    letter_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> DecisionLetterRead:
    """Return the letter metadata and its full text."""
    letter, _ = _readable_letter(db, current_user, letter_id)
    read = DecisionLetterRead.model_validate(letter)
    return read.model_copy(
        update={"download_url": f"/letters/{letter.id}/download"}
    )


@router.get(
    "/{letter_id}/download",
    response_class=FileResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Download the PDF of a decision letter",
)
def download_letter(
    letter_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
) -> FileResponse:
    """Stream the rendered PDF and record the download in the audit log."""
    letter, application = _readable_letter(db, current_user, letter_id)
    try:
        path = letter_path(letter, request.app.state.settings)
    except Exception as error:  # pragma: no cover - missing configuration
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The letter PDF is missing")

    audit.log(
        current_user,
        "letter.download",
        "DecisionLetter",
        letter.id,
        after={
            "letter_number": letter.letter_number,
            "application_id": str(application.id),
        },
    )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{letter.letter_number.replace('/', '_')}.pdf",
    )


@router.post(
    "/{letter_id}/acknowledge",
    response_model=DecisionLetterRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
    summary="Acknowledge a decision letter as the institution",
)
def acknowledge_letter(
    letter_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    audit: AuditDep,
    clock: ClockDep,
) -> DecisionLetterRead:
    """Record that the institution has seen the letter.

    Only the institution the application belongs to may acknowledge, and only
    once; the timestamp is what closes the appeal window early (APH 1.11a).
    """
    letter, application = _readable_letter(db, current_user, letter_id)
    if current_user.role != Role.INSTITUTION_ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the institution can acknowledge its own letter",
        )
    if letter.acknowledged_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This letter is already acknowledged")

    letter.acknowledged_by = current_user.id
    letter.acknowledged_at = clock.now()
    audit.log(
        current_user,
        "letter.acknowledge",
        "DecisionLetter",
        letter.id,
        after={
            "letter_number": letter.letter_number,
            "application_id": str(application.id),
            "acknowledged_at": letter.acknowledged_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(letter)
    read = DecisionLetterRead.model_validate(letter)
    return read.model_copy(
        update={"download_url": f"/letters/{letter.id}/download"}
    )
