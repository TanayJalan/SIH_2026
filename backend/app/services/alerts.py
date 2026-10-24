"""Workflow integration hook for the rule-driven alert engine.

The workflow calls :func:`notify` for every event it records. When a
:class:`~app.services.alert_engine.NotificationService` is supplied by the
request layer, this hook creates status-change and inspection alerts without
coupling transition logic to delivery details.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.workflow import WorkflowEvent

logger = logging.getLogger("app.alerts")


def notify(
    event: WorkflowEvent,
    *,
    db: Any = None,
    application: Any = None,
    actor: Any = None,
    notifications: Any = None,
    clock: Any = None,
) -> None:
    """Raise notifications for a workflow event.

    Direct service use without a notification service keeps the old logging
    behaviour, which keeps the workflow state machine independently testable.
    """
    logger.info(
        "workflow alert",
        extra={
            "event": "workflow.alert",
            "workflow_event_id": str(event.id),
            "application_id": str(event.application_id),
            "action": event.action,
            "from_status": event.from_status.value if event.from_status else None,
            "to_status": event.to_status.value,
        },
    )
    if db is None or application is None or notifications is None or clock is None:
        return

    try:
        from app.services.alert_engine import notify_workflow_event

        notify_workflow_event(db, event, application, actor, notifications, clock)
    except Exception:
        # A notification failure must never roll back an approved transition.
        db.rollback()
        logger.exception(
            "workflow alert delivery failed",
            extra={
                "event": "workflow.alert.failed",
                "workflow_event_id": str(event.id),
                "application_id": str(event.application_id),
            },
        )
