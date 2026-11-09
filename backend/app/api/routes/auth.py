"""Authentication endpoints."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.api.dependencies import AuditDep, CurrentUser, DbSession
from app.core.rate_limit import rate_limit_key
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse, UserProfile
from app.schemas.common import ErrorResponse
from app.services.auth import authenticate_user

logger = logging.getLogger("app.auth")

router = APIRouter(prefix="/auth", tags=["authentication"])

_RATE_LIMIT_ENTITY = uuid.UUID(int=0)


def _audit_rate_limit(
    audit: AuditDep,
    request: Request,
    email: str,
    retry_after: int,
    reason: str,
) -> None:
    """Record a throttled login without persisting the attempted password."""
    audit.log(
        None,
        "auth.rate_limited",
        "Auth",
        _RATE_LIMIT_ENTITY,
        after={
            "email": email,
            "reason": reason,
            "retry_after_seconds": retry_after,
        },
        request=request,
    )


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
    settings = request.app.state.settings
    client_ip = request.client.host if request.client else None
    limiter = request.app.state.login_rate_limiter
    limit_key = rate_limit_key(client_ip, payload.email)

    if settings.login_rate_limit_enabled:
        retry_after = limiter.check(limit_key)
        if retry_after:
            _audit_rate_limit(audit, request, payload.email, retry_after, "blocked")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed sign-in attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        blocked_for = 0
        if settings.login_rate_limit_enabled:
            blocked_for = limiter.register_failure(limit_key)
            if blocked_for:
                _audit_rate_limit(
                    audit,
                    request,
                    payload.email,
                    blocked_for,
                    "threshold_reached",
                )
                db.commit()
        logger.info(
            "login rejected",
            extra={
                "event": "login_rejected",
                "client_ip": client_ip,
                "rate_limited": bool(blocked_for),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.login_rate_limit_enabled:
        limiter.reset(limit_key)

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
