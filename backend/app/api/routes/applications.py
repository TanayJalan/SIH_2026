"""Role-scoped application read endpoints."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.dependencies import ClockDep, CurrentUser, DbSession
from app.models.application import Application
from app.models.application_type_route import ApplicationTypeRoute
from app.models.calendar import PublicNotice
from app.models.enums import ApplicationCategory, ApplicationStatus, InstitutionClass
from app.models.institution import Institution
from app.models.required_document import RequiredDocument
from app.schemas.application import ApplicationDetailRead, ApplicationPage, ApplicationRead
from app.schemas.application_sections import ApplicationData
from app.schemas.common import ErrorResponse
from app.schemas.compliance import CompliancePreviewRead
from app.schemas.fees import ApplicationTypeRouteRead, RouteDocumentRead, RouteStepRead
from app.services.application_sections import document_label
from app.services.authorization import application_scope, can_access_application
from app.services.compliance import evaluate_compliance
from app.services.fees import ter_selector_rate

router = APIRouter(prefix="/applications", tags=["applications"])

_CLOSED_STATUSES = (
    ApplicationStatus.ACTIVE_LOA,
    ApplicationStatus.ACTIVE_EOA,
    ApplicationStatus.CANCELLED,
    ApplicationStatus.FINAL_LOD,
    ApplicationStatus.FINAL_LOR,
    ApplicationStatus.WITHDRAWN,
    # Legacy pre-APH outcomes kept for historical rows.
    ApplicationStatus.APPROVED,
    ApplicationStatus.REJECTED,
)


@router.get(
    "",
    response_model=ApplicationPage,
    summary="List applications visible to the current role",
)
def list_applications(
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    institution_id: Annotated[uuid.UUID | None, Query()] = None,
    overdue: bool = False,
    assigned_to_me: bool = False,
    sort: Literal["recent", "due"] = "recent",
) -> ApplicationPage:
    """Return a paginated list scoped by institution, assignment or region."""
    conditions = list(application_scope(current_user))
    if institution_id is not None:
        conditions.append(Application.institution_id == institution_id)
    if assigned_to_me:
        conditions.append(Application.assigned_officer_id == current_user.id)
    if overdue:
        conditions.extend(
            [
                Application.sla_due_at.is_not(None),
                Application.sla_due_at < clock.now(),
                Application.status.not_in(_CLOSED_STATUSES),
                Application.is_withdrawn.is_(False),
            ]
        )

    total = db.scalar(select(func.count()).select_from(Application).where(*conditions)) or 0

    order_by = (
        Application.sla_due_at.asc().nullslast()
        if overdue or sort == "due"
        else Application.submitted_at.desc().nullslast()
    )
    applications = db.scalars(
        select(Application)
        .options(joinedload(Application.institution))
        .where(*conditions)
        .order_by(order_by, Application.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ApplicationPage(
        items=[ApplicationRead.model_validate(item) for item in applications],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get(
    "/type-routes",
    response_model=list[ApplicationTypeRouteRead],
    summary="List application types with their steps, documents, TER and cut-off",
)
def list_type_routes(
    current_user: CurrentUser,
    db: DbSession,
    academic_year: str | None = None,
) -> list[ApplicationTypeRouteRead]:
    """Return the selector cards driven by the ``application_type_routes`` table.

    Each card shows the applicable APH steps, the required documents, the base
    TER rate for the institution's fee class and whether the Category 1 Public
    Notice cut-off applies (APH Table 2.2, 2.3).
    """
    institution_class = InstitutionClass.OTHER
    if current_user.institution_id is not None:
        institution = db.scalar(
            select(Institution).where(Institution.id == current_user.institution_id)
        )
        if institution is not None and institution.institution_class is not None:
            institution_class = institution.institution_class

    routes = db.scalars(
        select(ApplicationTypeRoute).order_by(ApplicationTypeRoute.type.asc())
    ).all()
    notices: dict[str, PublicNotice] = {}
    if academic_year is not None:
        rows = db.scalars(
            select(PublicNotice).where(PublicNotice.academic_year == academic_year)
        ).all()
        notices = {row.category.value: row for row in rows}

    result: list[ApplicationTypeRouteRead] = []
    for route in routes:
        rate = ter_selector_rate(db, route.type, institution_class)
        notice = notices.get(route.category.value)
        steps = _route_steps(route)
        documents = db.scalars(
            select(RequiredDocument)
            .where(RequiredDocument.application_type == route.type)
            .order_by(RequiredDocument.mandatory.desc(), RequiredDocument.doc_code.asc())
        ).all()
        result.append(
            ApplicationTypeRouteRead(
                type=route.type,
                label=route.label,
                category=route.category,
                year_round=route.year_round,
                cutoff_applies=route.category == ApplicationCategory.CAT1_CUTOFF,
                cutoff_on=notice.cutoff_on if notice is not None else None,
                steps=steps,
                required_documents=[
                    RouteDocumentRead(
                        doc_code=document.doc_code,
                        doc_type=document.doc_type,
                        label=document_label(document.doc_type),
                        mandatory=document.mandatory,
                        condition_expr=document.condition_expr,
                        apH_clause=document.apH_clause,
                        needs_verification=document.needs_verification,
                    )
                    for document in documents
                ],
                ter_item_code=str(rate["item_code"]) if rate else None,
                ter_label=str(rate["label"]) if rate else None,
                ter_unit=str(rate["unit"]) if rate else None,
                ter_unit_amount_paise=(
                    int(rate["unit_amount_paise"]) if rate else None
                ),
                ter_note=(
                    "No TER is due for this type (APH 2.21)."
                    if route.no_ter
                    else (
                        "Base rate before the annual increase and any late penalty; "
                        "the exact amount is computed per application."
                    )
                ),
                apH_clause=route.apH_clause,
                needs_verification=route.needs_verification,
            )
        )
    return result


def _route_steps(route: ApplicationTypeRoute) -> list[RouteStepRead]:
    """Build the applicable APH pipeline steps for one application type."""
    return [
        RouteStepRead(
            key="SELF_DISCLOSURE",
            label="Self-Disclosure",
            applies=route.requires_self_disclosure,
            description=(
                "Submit the self-disclosure and generate the Deficiency Report "
                "(APH 2.3.3b)."
            ),
            apH_clause="APH 2.3.3b",
        ),
        RouteStepRead(
            key="SCRUTINY",
            label="Scrutiny / Re-Scrutiny Committee",
            applies=route.requires_scrutiny,
            description=(
                "Documents and eligibility are examined by the Scrutiny Committee (APH 1.8)."
            ),
            apH_clause="APH 1.8",
        ),
        RouteStepRead(
            key="EVC",
            label="Expert Visit Committee (EVC)",
            applies=route.requires_evc,
            description=(
                "An Expert Visit Committee inspects the campus where the type requires it "
                "(APH 1.9)."
            ),
            apH_clause="APH 1.9",
        ),
        RouteStepRead(
            key="SHC_SAC",
            label="Standing Hearing / Appellate Committee",
            applies=route.requires_hearing_aa,
            description=(
                "A hearing before the SHC or appeal to the SAC where the type allows it "
                "(APH 2.23-2.24)."
            ),
            apH_clause="APH 2.23-2.24",
        ),
    ]


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Get an application visible to the current role",
)
def get_application(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ApplicationDetailRead:
    """Return one application or deny cross-tenant access."""
    application = db.scalar(
        select(Application)
        .options(
            joinedload(Application.institution),
            joinedload(Application.assigned_officer),
            selectinload(Application.programs),
        )
        .where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    if not can_access_application(db, current_user, application):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this application",
        )
    return ApplicationDetailRead.model_validate(application)


@router.get(
    "/{application_id}/compliance",
    response_model=CompliancePreviewRead,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
    summary="Evaluate the configured compliance rules for a case file",
)
def get_application_compliance(
    application_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    clock: ClockDep,
) -> CompliancePreviewRead:
    """Return a read-only rule evaluation of the submitted application data."""
    application = db.scalar(select(Application).where(Application.id == application_id))
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    if not can_access_application(db, current_user, application):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this application",
        )
    return evaluate_compliance(
        db,
        application,
        ApplicationData.model_validate(application.data or {}),
        evaluated_at=clock.now(),
    )
