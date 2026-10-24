"""Liveness and readiness endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.health import HealthResponse, ReadinessResponse

logger = logging.getLogger("app.health")

router = APIRouter(tags=["system"])

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health(request: Request) -> HealthResponse:
    """Return 200 while the API process is serving requests."""
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    summary="Readiness probe",
)
def readiness(
    request: Request,
    db: DatabaseSession,
) -> ReadinessResponse:
    """Return 200 only when the database is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("database readiness check failed", extra={"event": "db_unavailable"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    settings = request.app.state.settings
    return ReadinessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        database="ok",
    )
