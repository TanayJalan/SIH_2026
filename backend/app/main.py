"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.routes import dev
from app.core.clock import SimulatedClock
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.services.application_workspace import WorkspaceError
from app.services.fees import FeeError
from app.services.scheduler import ComplianceScheduler
from app.services.workflow import WorkflowError

logger = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    clock = SimulatedClock()
    compliance_scheduler = ComplianceScheduler(
        enabled=resolved_settings.compliance_monitor_enabled,
        hour=resolved_settings.compliance_monitor_hour,
        environment=resolved_settings.environment,
        clock=clock,
        settings=resolved_settings,
        alert_scan_enabled=resolved_settings.alert_scan_enabled,
        alert_scan_interval_minutes=resolved_settings.alert_scan_interval_minutes,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "application started",
            extra={"event": "startup", "environment": resolved_settings.environment},
        )
        compliance_scheduler.start()
        yield
        compliance_scheduler.shutdown()
        logger.info("application stopped", extra={"event": "shutdown"})

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.clock = clock

    @app.exception_handler(WorkspaceError)
    async def _workspace_error_handler(_: Request, exc: WorkspaceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(WorkflowError)
    async def _workflow_error_handler(_: Request, exc: WorkflowError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(FeeError)
    async def _fee_error_handler(_: Request, exc: FeeError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    app.include_router(api_router)
    if resolved_settings.debug:
        app.include_router(dev.router)
    return app


app = create_app()
