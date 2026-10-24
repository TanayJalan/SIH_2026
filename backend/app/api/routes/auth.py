"""Authentication endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.dependencies import AuditDep, CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse, UserProfile
from app.schemas.common import ErrorResponse
from app.services.auth import authenticate_user

logger = logging.getLogger("app.auth")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
    summary="Authenticate and issue a JWT access token",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: DbSession,
    audit: AuditDep,
) -> TokenResponse:
    """Validate credentials, record the login and return an eight-hour token."""
    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        logger.info("login rejected", extra={"event": "login_rejected"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = request.app.state.settings
    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        institution_id=user.institution_id,
        secret_key=settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )

    audit.log(
        user,
        "auth.login",
        "User",
        user.id,
        after={
            "email": user.email,
            "role": user.role.value,
            "institution_id": str(user.institution_id) if user.institution_id else None,
        },
        request=request,
    )
    db.commit()

    return TokenResponse(
        access_token=token.value,
        expires_in=token.expires_in,
        user=UserProfile.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserProfile,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
    summary="Return the authenticated user",
)
def me(current_user: CurrentUser) -> UserProfile:
    """Return the profile for the current Bearer token."""
    return UserProfile.model_validate(current_user)
