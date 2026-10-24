"""Health-check response schemas."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness response."""

    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(HealthResponse):
    """Readiness response including dependency status."""

    database: Literal["ok"]
