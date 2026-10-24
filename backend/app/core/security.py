"""Password hashing and JWT helpers shared by auth and seeding code."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

_MIN_PASSWORD_LENGTH = 8
_BCRYPT_ROUNDS = 12


class InvalidTokenError(Exception):
    """Raised when an access token is missing, expired or malformed."""


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A signed access token and its lifetime metadata."""

    value: str
    expires_in: int
    expires_at: datetime


def hash_password(password: str) -> str:
    """Return a bcrypt hash for ``password``.

    Raises:
        ValueError: If the password is shorter than eight characters.
    """
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {_MIN_PASSWORD_LENGTH} characters")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether ``password`` matches a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *,
    subject: uuid.UUID,
    role: str,
    institution_id: uuid.UUID | None,
    secret_key: str,
    algorithm: str,
    expires_minutes: int,
) -> AccessToken:
    """Create a signed access token containing the required identity claims."""
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "institution_id": str(institution_id) if institution_id is not None else None,
        "type": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return AccessToken(
        value=token,
        expires_in=int((expires_at - issued_at).total_seconds()),
        expires_at=expires_at,
    )


def decode_access_token(*, token: str, secret_key: str, algorithm: str) -> dict[str, Any]:
    """Validate a signed access token and return its claims.

    Raises:
        InvalidTokenError: If the signature, expiry or required claims are invalid.
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc

    if payload.get("type") != "access":
        raise InvalidTokenError("Invalid token type")
    return payload
