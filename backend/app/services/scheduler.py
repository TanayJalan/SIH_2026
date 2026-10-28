"""APScheduler wiring for compliance monitoring and alert scans.

APScheduler task queue (no Redis/Celery). The scheduler starts with the
application lifespan and is disabled in the test environment.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.clock import SimulatedClock
from app.core.config import Settings

logger = logging.getLogger("app.scheduler")


class ComplianceScheduler:
    """Own the nightly compliance job and the periodic alert scan."""

    def __init__(
        self,
        *,
        enabled: bool,
        hour: int,
        environment: str,
        clock: SimulatedClock,
        settings: Settings,
        alert_scan_enabled: bool,
        alert_scan_interval_minutes: int,
    ) -> None:
        self._compliance_enabled = enabled and environment != "test"
        self._alert_scan_enabled = alert_scan_enabled and environment != "test"
        self._hour = hour
        self._clock = clock
        self._settings = settings
        self._alert_scan_interval_minutes = alert_scan_interval_minutes
        self._scheduler = BackgroundScheduler(timezone="UTC")

    @property
    def running(self) -> bool:
        """Whether either scheduled job is active."""
        return self._scheduler.running

    def start(self) -> None:
        """Schedule enabled jobs and start the scheduler (idempotent)."""
        if not self._compliance_enabled and not self._alert_scan_enabled:
            logger.info(
                "Scheduled jobs disabled; compliance and alert scans not scheduled.",
            )
            return

        if self._compliance_enabled:
            self._scheduler.add_job(
                run_nightly,
                trigger="cron",
                hour=self._hour,
                minute=0,
                id="nightly-compliance-evaluation",
                replace_existing=True,
            )
        if self._alert_scan_enabled:
            self._scheduler.add_job(
                run_alert_scan_job,
                trigger="interval",
                minutes=self._alert_scan_interval_minutes,
                id="periodic-alert-scan",
                replace_existing=True,
                kwargs={"clock": self._clock, "settings": self._settings},
            )
        self._scheduler.start()
        logger.info(
            "Scheduler started (compliance nightly=%s, alert scan every %d min).",
            "yes" if self._compliance_enabled else "no",
            self._alert_scan_interval_minutes,
        )

    def shutdown(self) -> None:
        """Stop the scheduler if it is running."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)


def run_nightly() -> None:
    """Job entry point executed by APScheduler."""
    from app.services.compliance import run_nightly_evaluation

    try:
        run_nightly_evaluation()
    except Exception:
        logger.exception("Nightly compliance evaluation failed.")


def run_alert_scan_job(*, clock: SimulatedClock, settings: Settings) -> None:
    """Job entry point for the 15-minute alert and workflow clock scan."""
    from app.db.session import SessionLocal
    from app.services.alert_engine import run_alert_scan
    from app.services.workflow_jobs import sweep

    try:
        result = run_alert_scan(clock=clock, settings=settings)
        logger.info(
            "Alert scan completed",
            extra={
                "event": "alert.scan.completed",
                "alerts_created": result.alerts_created,
                "escalations": result.escalations,
                "notifications_sent": result.notifications_sent,
            },
        )
    except Exception:
        logger.exception("Periodic alert scan failed.")
        return

    try:
        with SessionLocal() as db:
            advanced = sweep(db, clock, settings=settings)
        logger.info(
            "Workflow clock sweep completed",
            extra={"event": "workflow.sweep.completed", "advanced": advanced},
        )
    except Exception:
        logger.exception("Periodic workflow clock sweep failed.")
