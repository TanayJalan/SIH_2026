"""Global command-palette search across visible records and pages."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import joinedload

from app.api.dependencies import CurrentUser, DbSession
from app.models.application import Application
from app.models.enums import Role
from app.models.institution import Institution
from app.schemas.search import (
    SearchApplicationItem,
    SearchInstitutionItem,
    SearchPageItem,
    SearchResponse,
)
from app.services.authorization import application_scope, institution_scope

router = APIRouter(tags=["search"])

_RESULT_LIMIT = 6

_APPLICATIONS_LABELS: dict[Role, str] = {
    Role.INSTITUTION_ADMIN: "My applications",
    Role.REGULATION_BUREAU_OFFICER: "Regulation Bureau queue",
    Role.SCRUTINY_COMMITTEE_MEMBER: "Scrutiny queue",
    Role.EVC_MEMBER: "Assigned EVC visits",
    Role.REGIONAL_OFFICER: "Regional applications",
    Role.SHC_MEMBER: "SHC hearings",
    Role.SAC_MEMBER: "SAC appeals",
    Role.EXECUTIVE_COMMITTEE_MEMBER: "EC agenda",
    Role.COMPLAINT_SCRUTINY_MEMBER: "Complaint scrutiny",
    Role.SUPER_ADMIN: "All applications",
}


def _like_pattern(query: str) -> str:
    """Build an escaped contains pattern for case-insensitive SQL matching."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _pages_for_role(role: Role) -> list[SearchPageItem]:
    """Return the role-specific pages exposed to command-palette search."""
    pages = [
        SearchPageItem(label="Overview", path="/"),
        SearchPageItem(label=_APPLICATIONS_LABELS[role], path="/applications"),
        SearchPageItem(label="Alerts", path="/alerts"),
    ]
    if role in {Role.REGIONAL_OFFICER, Role.REGULATION_BUREAU_OFFICER, Role.SUPER_ADMIN}:
        pages.append(SearchPageItem(label="Audit logs", path="/audit-logs"))
    if role in {Role.REGIONAL_OFFICER, Role.SUPER_ADMIN}:
        pages.append(SearchPageItem(label="Compliance admin", path="/compliance-admin"))
    if role == Role.SUPER_ADMIN:
        pages.append(SearchPageItem(label="Alert rules", path="/alert-rules"))
    pages.append(SearchPageItem(label="My profile", path="/profile"))
    return pages


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search applications, institutions and pages visible to the current role",
)
def search(
    current_user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(max_length=100)] = "",
) -> SearchResponse:
    """Return grouped, role-scoped search results for the command palette."""
    query = q.strip()
    needle = query.casefold()

    pages = [
        page
        for page in _pages_for_role(current_user.role)
        if not needle or needle in page.label.casefold() or needle in page.path
    ]

    if not query:
        return SearchResponse(
            query=query,
            applications=[],
            institutions=[],
            pages=pages,
        )

    pattern = _like_pattern(query)
    application_matches = db.scalars(
        select(Application)
        .options(joinedload(Application.institution))
        .where(
            *application_scope(current_user),
            or_(
                Application.data["reference"].astext.ilike(pattern, escape="\\"),
                Application.institution.has(Institution.name.ilike(pattern, escape="\\")),
                cast(Application.id, String).ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Application.submitted_at.desc().nullslast(), Application.created_at.desc())
        .limit(_RESULT_LIMIT)
    ).all()

    institution_matches = db.scalars(
        select(Institution)
        .where(
            *institution_scope(current_user),
            or_(
                Institution.name.ilike(pattern, escape="\\"),
                Institution.aicte_id.ilike(pattern, escape="\\"),
                Institution.state.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Institution.name)
        .limit(_RESULT_LIMIT)
    ).all()

    return SearchResponse(
        query=query,
        applications=[
            SearchApplicationItem(
                id=application.id,
                reference=application.reference,
                institution_name=application.institution.name,
                status=application.status,
                academic_year=application.academic_year,
            )
            for application in application_matches
        ],
        institutions=[
            SearchInstitutionItem(
                id=institution.id,
                name=institution.name,
                state=institution.state,
                region=institution.region,
            )
            for institution in institution_matches
        ],
        pages=pages,
    )
