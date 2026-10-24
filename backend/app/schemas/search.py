"""Global search response schemas."""

import uuid

from pydantic import BaseModel

from app.models.enums import ApplicationStatus


class SearchApplicationItem(BaseModel):
    """An application match for the command palette."""

    id: uuid.UUID
    reference: str | None
    institution_name: str
    status: ApplicationStatus
    academic_year: str


class SearchInstitutionItem(BaseModel):
    """An institution match for the command palette."""

    id: uuid.UUID
    name: str
    state: str
    region: str


class SearchPageItem(BaseModel):
    """A page the current role can navigate to."""

    label: str
    path: str


class SearchResponse(BaseModel):
    """Grouped results returned by ``GET /search``."""

    query: str
    applications: list[SearchApplicationItem]
    institutions: list[SearchInstitutionItem]
    pages: list[SearchPageItem]
