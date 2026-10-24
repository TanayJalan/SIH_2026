"""Common API response schemas."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error payload."""

    detail: str
