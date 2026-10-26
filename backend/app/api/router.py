"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import (
    alert_rules,
    alerts,
    application_workspace,
    applications,
    audit_logs,
    auth,
    committees,
    compliance_admin,
    health,
    letters,
    public,
    search,
    workflow,
    workflow_definition,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(auth.router)
api_router.include_router(applications.router)
api_router.include_router(application_workspace.router)
api_router.include_router(workflow.router)
api_router.include_router(workflow_definition.router)
api_router.include_router(letters.router)
api_router.include_router(compliance_admin.router)
api_router.include_router(alert_rules.router)
api_router.include_router(alerts.router)
api_router.include_router(audit_logs.router)
api_router.include_router(search.router)
api_router.include_router(committees.router)
