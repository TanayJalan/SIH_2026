"""Public data exposed to the unauthenticated login screen."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Role


class PublicDemoAccount(BaseModel):
    """One seeded account for each demo role.

    Credentials are only included when ``DEMO_MODE`` is enabled. The
    application rejects demo mode in production.
    """

    role: Role
    label: str
    email: str
    password: str


class PublicStats(BaseModel):
    """Live operational figures and demo configuration for the login screen."""

    applications_in_progress: int
    average_days_to_decision: float | None
    institutions_needing_attention: int
    demo_mode: bool
    demo_accounts: list[PublicDemoAccount]
    as_of: datetime
