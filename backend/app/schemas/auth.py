"""Authentication request and response schemas."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Role
from app.schemas.institution import InstitutionSummary


class LoginRequest(BaseModel):
    """Email and password submitted to the login endpoint."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(
        min_length=1,
        max_length=128,
        json_schema_extra={"format": "password"},
    )

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("a valid email address is required")
        return email


class UserProfile(BaseModel):
    """Authenticated user details exposed to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: Role
    institution_id: uuid.UUID | None
    institution: InstitutionSummary | None
    region: str | None
    is_active: bool


class TokenResponse(BaseModel):
    """JWT access token and the authenticated user."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserProfile
