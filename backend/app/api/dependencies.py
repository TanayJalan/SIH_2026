"""Reusable API dependencies for authentication, roles and services."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.clock import SimulatedClock
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.audit import AuditService

DbSession = Annotated[Session, Depends(get_db)]
_bearer_scheme = HTTPBearer(auto_error=False)


def get_clock(request: Request) -> SimulatedClock:
    """Return the process-wide simulated clock held by the app."""
    return request.app.state.clock


ClockDep = Annotated[SimulatedClock, Depends(get_clock)]


def get_audit_service(db: DbSession) -> AuditService:
    """Provide an audit service bound to the request's database session."""
    return AuditService(db)


AuditDep = Annotated[AuditService, Depends(get_audit_service)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: DbSession,
) -> User:
    """Resolve and validate the active user from a Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    settings = request.app.state.settings
    try:
        payload = decode_access_token(
            token=credentials.credentials,
            secret_key=settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        user_id = uuid.UUID(str(payload.get("sub")))
    except (InvalidTokenError, TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = db.scalar(select(User).options(joinedload(User.institution)).where(User.id == user_id))
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Return a dependency that allows only the supplied roles.

    The dependency returns the authenticated user so routes can reuse the
    identity without performing a second lookup.
    """
    allowed = frozenset(roles)

    def _check_role(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _check_role
