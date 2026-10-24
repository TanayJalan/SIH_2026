"""Authentication service functions."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password, verify_password
from app.models.user import User

# A valid bcrypt hash used to keep unknown-email login attempts on the same
# computational path as known emails, reducing account-enumeration timing cues.
_DUMMY_PASSWORD_HASH = hash_password("invalid-password-used-for-timing-only")


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    """Return the active user matching ``email`` and ``password``, if any."""
    normalised_email = email.strip().lower()
    user = db.scalar(
        select(User)
        .options(joinedload(User.institution))
        .where(func.lower(User.email) == normalised_email)
    )

    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    password_matches = verify_password(password, user.password_hash)
    if not password_matches or not user.is_active:
        return None
    return user
