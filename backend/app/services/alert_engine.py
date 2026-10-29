"""Rule-driven alert delivery, acknowledgement and escalation.

The scheduler, workflow notifier and compliance monitor all call this module.
Alert rules are database rows; this service only knows how to evaluate them,
render their templates, enforce idempotency with dedupe keys, and route a
notification through the configured channels.

Escalation is deliberately an overlay on the primary workflow: the application
keeps its status while ``is_escalated`` is set and a ``WorkflowEvent`` with the
``escalate`` action records the chain step.
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.clock import SimulatedClock
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.alert import Alert, AlertRule
from app.models.application import Application
from app.models.deadline import DeadlineRule, Timer
from app.models.deficiency import Deficiency
from app.models.document import Document
from app.models.enums import (
    AlertChannel,
    AlertStatus,
    AlertTrigger,
    ApplicationStatus,
    DeficiencyStatus,
    InspectionStatus,
    Role,
    Severity,
    TimerStatus,
)
from app.models.inspection import Inspection
from app.models.institution import Institution
from app.models.sla import SLAConfig
from app.models.user import User
from app.models.workflow import WorkflowEvent
from app.services.alert_stream import publish_clock, publish_created_alerts
from app.services.alert_triggers import first_rule_for_handler, rules_for_handler
from app.services.audit import AuditService
from app.services.deadlines import refresh_timer_status

_ESCALATION_CHAIN = (
    Role.REGULATION_BUREAU_OFFICER,
    Role.REGIONAL_OFFICER,
    Role.SUPER_ADMIN,
)
"""Escalation order for an unacknowledged or SLA-breached alert."""

logger = logging.getLogger("app.alerts")

TERMINAL_STATUSES = {
    ApplicationStatus.ACTIVE_LOA,
    ApplicationStatus.ACTIVE_EOA,
    ApplicationStatus.CANCELLED,
    ApplicationStatus.FINAL_LOD,
    ApplicationStatus.FINAL_LOR,
    ApplicationStatus.WITHDRAWN,
    # Legacy pre-APH outcomes kept for historical rows.
    ApplicationStatus.APPROVED,
    ApplicationStatus.REJECTED,
}
SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}

# Statutory clocks that get their own warning and expiry triggers instead of
# the stage-SLA one. The tuple is
# ``(deadline_rules.code, warning trigger, expiry trigger, keep for terminal)``;
# the engine handler is the catalogue ``handler_key`` (see
# ``alert_trigger_catalogue``).
_TIMER_ALERTS = (
    (
        "APPEAL_WINDOW",
        AlertTrigger.APPEAL_WINDOW_CLOSING,
        AlertTrigger.APPEAL_EXPIRED,
        False,
    ),
    (
        "SECURITY_DEPOSIT",
        AlertTrigger.DEPOSIT_DUE,
        AlertTrigger.DEPOSIT_OVERDUE,
        False,
    ),
    (
        "LOA_VALIDITY",
        None,
        AlertTrigger.LOA_EXPIRED,
        True,
    ),
)
_EXPIRY_TITLES = {
    AlertTrigger.APPEAL_EXPIRED: "Appeal window expired: {institution}",
    AlertTrigger.DEPOSIT_OVERDUE: "Security Deposit overdue: {institution}",
    AlertTrigger.LOA_EXPIRED: "LoA expired: {institution}",
}
SEVERITY_RAISED = {
    Severity.LOW: Severity.MEDIUM,
    Severity.MEDIUM: Severity.HIGH,
    Severity.HIGH: Severity.CRITICAL,
    Severity.CRITICAL: Severity.CRITICAL,
}
CHANNEL_ORDER = (AlertChannel.IN_APP, AlertChannel.EMAIL, AlertChannel.SMS)
TRIGGER_TITLES = {
    AlertTrigger.DEADLINE_APPROACHING: "Deadline approaching",
    AlertTrigger.SLA_BREACHED: "SLA breached",
    AlertTrigger.DEFICIENCY_DUE: "Deficiency response due",
    AlertTrigger.DEFICIENCY_OVERDUE: "Deficiency response overdue",
    AlertTrigger.DOCUMENT_EXPIRING: "Document expiring",
    AlertTrigger.COMPLIANCE_RED: "Compliance RED",
    AlertTrigger.APPLICATION_STATUS_CHANGED: "Application status updated",
    AlertTrigger.INSPECTION_SCHEDULED: "Inspection scheduled",
}


@dataclass(slots=True)
class AlertScanResult:
    """Summary of one periodic alert scan."""

    alerts_created: int
    escalations: int
    notifications_sent: int
    scanned_at: datetime


class NotificationProvider(ABC):
    """Deliver one alert through one external channel."""

    channel: AlertChannel

    @abstractmethod
    def deliver(self, alert: Alert, recipient: User) -> bool:
        """Attempt delivery and return whether it succeeded."""


class InAppProvider(NotificationProvider):
    """The in-app channel is represented by the Alert row itself."""

    channel = AlertChannel.IN_APP

    def deliver(self, alert: Alert, recipient: User) -> bool:
        return True


class EmailProvider(NotificationProvider):
    """Send alert email through a plain SMTP relay such as Mailpit."""

    channel = AlertChannel.EMAIL

    def __init__(self, *, host: str, port: int, sender: str, timeout: float = 5.0) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._timeout = timeout

    def deliver(self, alert: Alert, recipient: User) -> bool:
        if not self._host or not recipient.email:
            return False

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = recipient.email
        message["Subject"] = alert.title
        message.set_content(alert.message)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                client.send_message(message)
            return True
        except (OSError, smtplib.SMTPException):
            logger.exception(
                "Alert email delivery failed",
                extra={
                    "event": "alert.email.failed",
                    "alert_id": str(alert.id),
                    "recipient": recipient.email,
                },
            )
            return False


class SmsProvider(NotificationProvider):
    """Mock SMS provider used by the prototype.

    A production integration would replace this class behind the same
    :class:`NotificationProvider` interface.
    """

    channel = AlertChannel.SMS

    def deliver(self, alert: Alert, recipient: User) -> bool:
        logger.info(
            "Mock SMS alert",
            extra={
                "event": "alert.sms.mock",
                "alert_id": str(alert.id),
                "recipient": recipient.email,
                "sms_body": alert.message,
            },
        )
        return True


class NotificationService:
    """Route an alert to the providers configured for each channel."""

    def __init__(
        self,
        providers: dict[AlertChannel, NotificationProvider],
        *,
        enabled: bool = True,
    ) -> None:
        self._providers = providers
        self.enabled = enabled

    @classmethod
    def from_settings(cls, settings: Settings) -> NotificationService:
        """Build the default provider registry from application settings."""
        providers: dict[AlertChannel, NotificationProvider] = {
            AlertChannel.IN_APP: InAppProvider()
        }
        enabled = settings.notifications_enabled
        if enabled:
            providers[AlertChannel.EMAIL] = EmailProvider(
                host=settings.smtp_host,
                port=settings.smtp_port,
                sender=settings.smtp_from,
            )
            providers[AlertChannel.SMS] = SmsProvider()
        return cls(providers, enabled=enabled)

    def deliver(self, alert: Alert, recipient: User) -> bool:
        """Send one alert through its channel, returning success state."""
        provider = self._providers.get(alert.channel)
        if provider is None:
            logger.warning(
                "No provider configured for alert channel %s",
                alert.channel.value,
            )
            return False
        return provider.deliver(alert, recipient)


class _TemplateValues(dict[str, str]):
    """Leave unknown placeholders visible instead of failing a scan."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render_template(template: str, values: dict[str, str]) -> str:
    """Render an alert template with safe placeholder handling."""
    try:
        return template.format_map(_TemplateValues(values))
    except (ValueError, IndexError):
        logger.warning("Malformed alert template; returning it unchanged.")
        return template


def _humanise(value: str) -> str:
    words = value.lower().replace("_", " ")
    return words[:1].upper() + words[1:]


def _format_due(value: date | datetime | None) -> str:
    if value is None:
        return "not set"
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


class AlertEngine:
    """Evaluate alert rules and apply dedupe, delivery and escalation."""

    def __init__(
        self,
        db: Session,
        clock: SimulatedClock,
        *,
        settings: Settings | None = None,
        notifications: NotificationService | None = None,
        now: datetime | None = None,
    ) -> None:
        self._db = db
        self._clock = clock
        self._settings = settings or get_settings()
        self._notifications = notifications or NotificationService.from_settings(self._settings)
        self._audit = AuditService(db)
        self._now_override = now
        self.created_alerts = 0
        self.escalations = 0
        self._created: list[Alert] = []

    @property
    def created_inapp_alerts(self) -> list[Alert]:
        """Rows this scan created on the user-facing IN_APP channel.

        The SSE bridge publishes only these; EMAIL/SMS rows are delivery
        records and must not reach the browser.
        """
        return [alert for alert in self._created if alert.channel == AlertChannel.IN_APP]

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def scan(self) -> AlertScanResult:
        """Run every periodic trigger once and return a summary."""
        started_at = self._now()
        self._scan_deadlines()
        self._scan_timers()
        self._scan_slas()
        self._scan_deficiencies()
        self._scan_documents()
        self._scan_inspections()
        self._escalate()
        self._db.flush()
        return AlertScanResult(
            alerts_created=self.created_alerts,
            escalations=self.escalations,
            notifications_sent=0,
            scanned_at=started_at,
        )

    def deliver_pending(self, alerts: Iterable[Alert] | None = None) -> int:
        """Deliver outbound rows that are still pending.

        Delivery happens after the creating transaction commits so a failed
        SMTP call cannot roll back the in-app notification.
        """
        if not self._notifications.enabled:
            return 0

        if alerts is None:
            pending = self._db.scalars(
                select(Alert)
                .where(
                    Alert.channel != AlertChannel.IN_APP,
                    Alert.status == AlertStatus.PENDING,
                )
                .order_by(Alert.created_at.asc())
                .limit(200)
            ).all()
        else:
            pending = [
                alert
                for alert in alerts
                if alert.channel != AlertChannel.IN_APP
                and alert.status == AlertStatus.PENDING
            ]

        sent = 0
        for alert in pending:
            recipient = alert.recipient
            if recipient is None:
                recipient = self._db.get(User, alert.recipient_user_id)
            if recipient is None:
                continue
            if self._notifications.deliver(alert, recipient):
                alert.status = AlertStatus.SENT
                alert.sent_at = self._now()
                sent += 1
        self._db.flush()
        return sent

    # ------------------------------------------------------------------
    # Rule-driven creation
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        return self._now_override or self._clock.now()

    def _rules(self, trigger: AlertTrigger) -> list[AlertRule]:
        """Return active rules mapped to the handler for ``trigger``.

        The catalogue join lets several statutory trigger codes share one
        engine handler without a code change.
        """
        return rules_for_handler(self._db, trigger.value)

    def _rule_channels(self, rule: AlertRule | None) -> list[AlertChannel]:
        channels: list[AlertChannel] = []
        for raw in rule.channel_list if rule is not None else []:
            try:
                channel = AlertChannel(raw)
            except ValueError:
                continue
            if channel not in channels:
                channels.append(channel)
        if AlertChannel.IN_APP not in channels:
            channels.insert(0, AlertChannel.IN_APP)
        return channels

    def _create_alert(
        self,
        *,
        rule: AlertRule | None,
        trigger: AlertTrigger | None,
        recipients: Sequence[User],
        context: dict[str, str],
        dedupe_base: str,
        title: str,
        application: Application | None = None,
        message: str | None = None,
        severity: Severity | None = None,
        channels: Sequence[AlertChannel] | None = None,
        type_override: str | None = None,
        escalation_level: int = 0,
        parent_alert_id: uuid.UUID | None = None,
    ) -> list[Alert]:
        """Create one row per recipient and channel, skipping known dedupe keys."""
        if not recipients:
            return []

        resolved_severity = severity or (rule.severity if rule is not None else Severity.MEDIUM)
        resolved_message = message
        if resolved_message is None and rule is not None:
            resolved_message = render_template(rule.template, context)
        resolved_message = resolved_message or title
        resolved_type = type_override or (
            rule.trigger_type
            if rule is not None
            else (trigger.value if trigger is not None else "ALERT")
        )
        selected_channels = list(channels or self._rule_channels(rule))
        if new := [channel for channel in selected_channels if channel not in CHANNEL_ORDER]:
            logger.warning("Ignoring unsupported alert channels: %s", new)
            selected_channels = [
                channel for channel in selected_channels if channel in CHANNEL_ORDER
            ]
        if AlertChannel.IN_APP not in selected_channels:
            selected_channels.insert(0, AlertChannel.IN_APP)
        if not self._notifications.enabled:
            selected_channels = [AlertChannel.IN_APP]

        now = self._now()
        created: list[Alert] = []
        seen_recipients: set[uuid.UUID] = set()
        for recipient in recipients:
            if recipient.id in seen_recipients:
                continue
            seen_recipients.add(recipient.id)
            for channel in CHANNEL_ORDER:
                if channel not in selected_channels:
                    continue
                dedupe_key = f"{dedupe_base}:{recipient.id}:{channel.value}"[:255]
                existing = self._db.scalar(
                    select(Alert.id).where(Alert.dedupe_key == dedupe_key)
                )
                if existing is not None:
                    continue

                alert = Alert(
                    recipient_user_id=recipient.id,
                    application_id=application.id if application is not None else None,
                    rule_id=rule.id if rule is not None else None,
                    parent_alert_id=parent_alert_id,
                    type=resolved_type,
                    severity=resolved_severity,
                    title=title[:255],
                    message=resolved_message,
                    channel=channel,
                    status=AlertStatus.PENDING,
                    sent_at=now if channel == AlertChannel.IN_APP else None,
                    escalation_level=escalation_level,
                    dedupe_key=dedupe_key,
                )
                self._db.add(alert)
                self._db.flush()
                self._audit.log(
                    None,
                    "alert.create",
                    "Alert",
                    alert.id,
                    after={
                        "type": alert.type,
                        "severity": alert.severity.value,
                        "channel": alert.channel.value,
                        "recipient_user_id": str(alert.recipient_user_id),
                        "application_id": (
                            str(alert.application_id) if alert.application_id else None
                        ),
                        "dedupe_key": alert.dedupe_key,
                        "escalation_level": alert.escalation_level,
                    },
                )
                self.created_alerts += 1
                self._created.append(alert)
                created.append(alert)
        return created

    # ------------------------------------------------------------------
    # Periodic scans
    # ------------------------------------------------------------------

    def _scan_deadlines(self) -> None:
        rules = self._rules(AlertTrigger.DEADLINE_APPROACHING)
        if not rules:
            return
        applications = self._db.scalars(
            select(Application)
            .options(
                joinedload(Application.institution),
                joinedload(Application.assigned_officer),
            )
            .where(
                Application.sla_due_at.is_not(None),
                Application.is_withdrawn.is_(False),
                Application.status.not_in(TERMINAL_STATUSES),
            )
        ).unique().all()
        today = self._now().date()
        for application in applications:
            if application.sla_due_at is None:
                continue
            days_until = (application.sla_due_at.date() - today).days
            if days_until < 0:
                continue
            rule = self._window_rule(rules, days_until)
            if rule is None:
                continue
            recipients = self._initial_recipients(application)
            context = self._context(
                application=application,
                due_date=application.sla_due_at,
                days_remaining=days_until,
            )
            title = f"Deadline approaching: {context['institution']} (T-{rule.days_before})"
            self._create_alert(
                rule=rule,
                trigger=AlertTrigger.DEADLINE_APPROACHING,
                recipients=recipients,
                context=context,
                dedupe_base=(
                    f"deadline:{application.id}:{rule.days_before}:"
                    f"{application.sla_due_at.date().isoformat()}"
                ),
                title=title,
                application=application,
            )

    def _scan_timers(self) -> None:
        """Warn, then expire, the statutory clocks started by workflow events.

        The appeal window (APH 1.11a), the Security Deposit clock (APH 2.25f)
        and LoA validity (APH 1.10b) are ``Timer`` rows, not the stage SLA.
        Warnings go to the institution that has to act; an expired clock goes
        to the Regulation Bureau officer and the Regional Officer, and records
        one ``timer_expire`` event. The workflow sweep then applies the final
        status change through the normal state machine.
        """
        today = self._now().date()
        for rule_code, warning_trigger, expiry_trigger, keep_for_terminal in _TIMER_ALERTS:
            timers = self._db.scalars(
                select(Timer)
                .join(DeadlineRule, DeadlineRule.id == Timer.deadline_rule_id)
                .options(
                    joinedload(Timer.application).joinedload(Application.institution),
                    joinedload(Timer.application).joinedload(
                        Application.assigned_officer
                    ),
                )
                .where(
                    DeadlineRule.code == rule_code,
                    Timer.status.in_((TimerStatus.PENDING, TimerStatus.DUE)),
                )
            ).unique().all()
            if not timers:
                continue
            warning_rules = (
                self._rules(warning_trigger) if warning_trigger is not None else []
            )
            expiry_rules = self._rules(expiry_trigger)
            for timer in timers:
                application = timer.application
                if application is None or application.is_withdrawn:
                    continue
                if keep_for_terminal:
                    # An ACTIVE_LOA application is terminal for SLA purposes but
                    # its two-academic-year clock is still running.
                    if application.status != ApplicationStatus.ACTIVE_LOA:
                        continue
                elif application.status in TERMINAL_STATUSES:
                    continue

                refresh_timer_status(timer, self._now())
                days_until = (timer.due_at.date() - today).days
                if timer.status == TimerStatus.BREACHED:
                    self._expire_timer(
                        timer,
                        application,
                        rule_code=rule_code,
                        trigger=expiry_trigger,
                        rules=expiry_rules,
                    )
                    continue
                if not warning_rules or warning_trigger is None:
                    continue
                rule = self._window_rule(warning_rules, days_until)
                if rule is None:
                    continue
                if self._timer_fired(timer, f"WARN-{rule.days_before}"):
                    continue
                recipients = (
                    self._institution_admin_recipients(application)
                    or self._initial_recipients(application)
                )
                context = self._context(
                    application=application,
                    due_date=timer.due_at,
                    days_remaining=days_until,
                )
                title = (
                    "Appeal window closing: "
                    f"{context['application_reference']}"
                    if warning_trigger is AlertTrigger.APPEAL_WINDOW_CLOSING
                    else f"Security Deposit due: {context['institution']}"
                )
                created = self._create_alert(
                    rule=rule,
                    trigger=warning_trigger,
                    recipients=recipients,
                    context=context,
                    dedupe_base=(
                        f"{warning_trigger.value.lower()}:{timer.id}:"
                        f"{rule.days_before}:{timer.due_at.date().isoformat()}"
                    ),
                    title=title,
                    application=application,
                )
                if created:
                    level = f"WARN-{rule.days_before}"
                    self._record_timer_warning(
                        timer,
                        application,
                        rule_code=rule_code,
                        trigger=warning_trigger,
                        level=level,
                    )
                    self._mark_timer_fired(
                        timer,
                        level,
                        warning_trigger,
                    )

    def _expire_timer(
        self,
        timer: Timer,
        application: Application,
        *,
        rule_code: str,
        trigger: AlertTrigger,
        rules: Sequence[AlertRule],
    ) -> None:
        """Mark ``timer`` breached and emit the expiry alert and event once."""
        timer.status = TimerStatus.BREACHED
        if self._timer_fired(timer, "EXPIRED"):
            return
        now = self._now()
        self._audit.log(
            None,
            "timer.expire",
            "Timer",
            timer.id,
            before={"status": TimerStatus.DUE.value},
            after={
                "application_id": str(application.id),
                "deadline_rule": rule_code,
                "status": TimerStatus.BREACHED.value,
                "due_at": timer.due_at.isoformat(),
            },
        )
        self._db.add(
            WorkflowEvent(
                application_id=application.id,
                from_status=application.status,
                to_status=application.status,
                actor_id=None,
                action="timer_expire",
                comment=f"Statutory clock {rule_code} expired.",
                apH_clause=timer.deadline_rule.apH_clause,
                details={
                    "timer_id": str(timer.id),
                    "deadline_rule": rule_code,
                    "due_at": timer.due_at.isoformat(),
                },
                created_at=now,
            )
        )
        self._db.flush()

        rule = rules[0] if rules else None
        if rule is not None:
            context = self._context(
                application=application,
                due_date=timer.due_at,
                days_remaining=0,
            )
            title = _EXPIRY_TITLES[trigger].format(
                institution=context["institution"]
            )
            self._create_alert(
                rule=rule,
                trigger=trigger,
                recipients=self._oversight_recipients(application),
                context=context,
                dedupe_base=(
                    f"{trigger.value.lower()}:{timer.id}:expired:"
                    f"{timer.due_at.date().isoformat()}"
                ),
                title=title,
                application=application,
            )
        self._mark_timer_fired(timer, "EXPIRED", trigger)

    def _record_timer_warning(
        self,
        timer: Timer,
        application: Application,
        *,
        rule_code: str,
        trigger: AlertTrigger,
        level: str,
    ) -> None:
        """Record a warning step as a ``WorkflowEvent`` and an audit row.

        Warnings do not change the application status, but they are statutory
        steps of the clock, so the same who/what/when trail as an expiry is
        kept. The timer's ``fired_levels`` history makes the write idempotent.
        """
        self._audit.log(
            None,
            "timer.warn",
            "Timer",
            timer.id,
            after={
                "application_id": str(application.id),
                "deadline_rule": rule_code,
                "level": level,
                "trigger": trigger.value,
                "due_at": timer.due_at.isoformat(),
            },
        )
        self._db.add(
            WorkflowEvent(
                application_id=application.id,
                from_status=application.status,
                to_status=application.status,
                actor_id=None,
                action="timer_warn",
                comment=f"Statutory clock {rule_code} warning ({level}).",
                apH_clause=timer.deadline_rule.apH_clause,
                details={
                    "timer_id": str(timer.id),
                    "deadline_rule": rule_code,
                    "level": level,
                    "trigger": trigger.value,
                    "due_at": timer.due_at.isoformat(),
                },
                created_at=self._now(),
            )
        )
        self._db.flush()

    @staticmethod
    def _timer_fired(timer: Timer, level: str) -> bool:
        """Return whether ``level`` has already produced its alert/event."""
        return any(
            str(item.get("level")) == level
            for item in (timer.fired_levels or [])
            if isinstance(item, dict)
        )

    def _mark_timer_fired(
        self,
        timer: Timer,
        level: str,
        trigger: AlertTrigger,
    ) -> None:
        """Append a fired level to the timer's JSON history."""
        levels = [
            item for item in (timer.fired_levels or []) if isinstance(item, dict)
        ]
        levels.append(
            {
                "level": level,
                "trigger": trigger.value,
                "at": self._now().isoformat(),
            }
        )
        timer.fired_levels = levels

    def _oversight_recipients(self, application: Application) -> list[User]:
        """Return the Regulation Bureau officer and Regional Officer.

        Expiry is an oversight event, so it reaches the Bureau and the region
        rather than the institution. A super admin is the final fallback when
        no regional officer is configured.
        """
        recipients = [
            *self._users_for_role(application, Role.REGULATION_BUREAU_OFFICER),
            *self._users_for_role(application, Role.REGIONAL_OFFICER),
        ]
        if not recipients:
            recipients = self._users_for_role(application, Role.SUPER_ADMIN)
        return list({user.id: user for user in recipients}.values())

    def _scan_slas(self) -> None:
        rules = self._rules(AlertTrigger.SLA_BREACHED)
        if not rules:
            return
        rule = rules[0]
        now = self._now()
        applications = self._db.scalars(
            select(Application)
            .options(
                joinedload(Application.institution),
                joinedload(Application.assigned_officer),
            )
            .where(
                Application.sla_due_at.is_not(None),
                Application.sla_due_at < now,
                Application.is_withdrawn.is_(False),
                Application.status.not_in(TERMINAL_STATUSES),
            )
        ).unique().all()
        for application in applications:
            if application.sla_due_at is None:
                continue
            context = self._context(
                application=application,
                due_date=application.sla_due_at,
                days_remaining=(application.sla_due_at.date() - now.date()).days,
            )
            self._create_alert(
                rule=rule,
                trigger=AlertTrigger.SLA_BREACHED,
                recipients=self._initial_recipients(application),
                context=context,
                dedupe_base=(
                    f"sla_breached:{application.id}:"
                    f"{application.sla_due_at.isoformat()}"
                ),
                title=f"SLA breached: {context['institution']}",
                application=application,
            )

    def _scan_deficiencies(self) -> None:
        due_rules = self._rules(AlertTrigger.DEFICIENCY_DUE)
        overdue_rules = self._rules(AlertTrigger.DEFICIENCY_OVERDUE)
        if not due_rules and not overdue_rules:
            return
        deficiencies = self._db.scalars(
            select(Deficiency)
            .options(
                joinedload(Deficiency.application).joinedload(Application.institution),
                joinedload(Deficiency.application).joinedload(Application.assigned_officer),
            )
            .where(Deficiency.status == DeficiencyStatus.OPEN)
        ).unique().all()
        today = self._now().date()
        for deficiency in deficiencies:
            application = deficiency.application
            if application is None or self._is_inactive(application):
                continue
            days_until = (deficiency.due_date - today).days
            context = self._context(
                application=application,
                due_date=deficiency.due_date,
                days_remaining=days_until,
                deficiency=deficiency,
            )
            recipients = self._institution_admin_recipients(
                application
            ) or self._initial_recipients(application)
            if days_until < 0 and overdue_rules:
                rule = overdue_rules[0]
                self._create_alert(
                    rule=rule,
                    trigger=AlertTrigger.DEFICIENCY_OVERDUE,
                    recipients=recipients,
                    context=context,
                    dedupe_base=(
                        f"deficiency_overdue:{deficiency.id}:"
                        f"{deficiency.due_date.isoformat()}"
                    ),
                    title=f"Deficiency response overdue: {context['institution']}",
                    application=application,
                )
            elif days_until >= 0 and due_rules:
                rule = self._due_rule(due_rules, days_until)
                if rule is None:
                    continue
                self._create_alert(
                    rule=rule,
                    trigger=AlertTrigger.DEFICIENCY_DUE,
                    recipients=recipients,
                    context=context,
                    dedupe_base=(
                        f"deficiency_due:{deficiency.id}:"
                        f"{deficiency.due_date.isoformat()}:{rule.days_before}"
                    ),
                    title=f"Deficiency response due: {context['institution']}",
                    application=application,
                )

    def _scan_documents(self) -> None:
        rules = self._rules(AlertTrigger.DOCUMENT_EXPIRING)
        if not rules:
            return
        documents = self._db.scalars(
            select(Document)
            .options(
                joinedload(Document.application).joinedload(Application.institution),
                joinedload(Document.application).joinedload(Application.assigned_officer),
            )
            .where(Document.expiry_date.is_not(None))
        ).unique().all()
        today = self._now().date()
        for document in documents:
            if document.expiry_date is None:
                continue
            application = document.application
            if application is None or self._is_inactive(application):
                continue
            days_until = (document.expiry_date - today).days
            if days_until < 0:
                continue
            rule = self._window_rule(rules, days_until)
            if rule is None:
                continue
            context = self._context(
                application=application,
                due_date=document.expiry_date,
                days_remaining=days_until,
                document=document,
            )
            self._create_alert(
                rule=rule,
                trigger=AlertTrigger.DOCUMENT_EXPIRING,
                recipients=(
                    self._institution_admin_recipients(application)
                    or self._initial_recipients(application)
                ),
                context=context,
                dedupe_base=(
                    f"document_expiring:{document.id}:"
                    f"{document.expiry_date.isoformat()}:{rule.days_before}"
                ),
                title=f"Document expiring: {context['institution']}",
                application=application,
            )

    def _scan_inspections(self) -> None:
        rules = self._rules(AlertTrigger.INSPECTION_SCHEDULED)
        if not rules:
            return
        rule = rules[0]
        now = self._now()
        inspections = self._db.scalars(
            select(Inspection)
            .options(
                joinedload(Inspection.application).joinedload(Application.institution),
                joinedload(Inspection.application).joinedload(Application.assigned_officer),
                joinedload(Inspection.committee_member),
            )
            .where(
                Inspection.status == InspectionStatus.SCHEDULED,
                Inspection.scheduled_on >= now,
            )
        ).unique().all()
        for inspection in inspections:
            application = inspection.application
            if application is None or self._is_inactive(application):
                continue
            committee = inspection.committee_member
            recipients = (
                [committee]
                if committee is not None and committee.is_active
                else self._initial_recipients(application)
            )
            context = self._context(
                application=application,
                due_date=inspection.scheduled_on,
                inspection=inspection,
            )
            self._create_alert(
                rule=rule,
                trigger=AlertTrigger.INSPECTION_SCHEDULED,
                recipients=recipients,
                context=context,
                dedupe_base=f"inspection_scheduled:{inspection.id}",
                title=f"Inspection scheduled: {context['institution']}",
                application=application,
            )

    # ------------------------------------------------------------------
    # Escalation chain
    # ------------------------------------------------------------------

    def _escalate(self) -> None:
        applications = self._db.scalars(
            select(Application)
            .options(joinedload(Application.institution))
            .where(
                Application.is_withdrawn.is_(False),
                Application.status.not_in(TERMINAL_STATUSES),
            )
        ).unique().all()
        now = self._now()
        for application in applications:
            config = self._db.scalar(
                select(SLAConfig).where(SLAConfig.stage == application.current_stage)
            )
            if config is None:
                continue

            initial_alerts = self._db.scalars(
                select(Alert)
                .join(User, Alert.recipient_user_id == User.id)
                .options(joinedload(Alert.recipient))
                .where(
                    Alert.application_id == application.id,
                    Alert.escalation_level == 0,
                    Alert.channel == AlertChannel.IN_APP,
                    Alert.status != AlertStatus.ACKED,
                    User.role.not_in(
                        (
                            Role.REGULATION_BUREAU_OFFICER,
                            Role.REGIONAL_OFFICER,
                            Role.SUPER_ADMIN,
                        )
                    ),
                )
                .order_by(Alert.created_at.asc())
            ).all()
            if not initial_alerts:
                continue

            breached = (
                application.sla_due_at is not None and application.sla_due_at <= now
            )
            matured = [
                alert
                for alert in initial_alerts
                if alert.created_at
                + timedelta(days=max(config.escalation_after_days, 0))
                <= now
            ]
            qualifying = list({alert.id: alert for alert in [*matured, *initial_alerts]}.values())
            if not breached:
                qualifying = matured
            if not qualifying:
                continue

            existing_levels = self._db.scalars(
                select(Alert)
                .where(
                    Alert.application_id == application.id,
                    Alert.escalation_level >= 1,
                )
                .order_by(Alert.escalation_level.asc(), Alert.created_at.asc())
            ).all()
            highest_level = max((alert.escalation_level for alert in existing_levels), default=0)
            if highest_level >= len(_ESCALATION_CHAIN):
                continue
            next_level = highest_level + 1

            if highest_level == 0:
                source = max(
                    qualifying,
                    key=lambda alert: (
                        SEVERITY_RANK[alert.severity],
                        -alert.created_at.timestamp(),
                    ),
                )
            else:
                source = next(
                    (
                        alert
                        for alert in existing_levels
                        if alert.escalation_level == highest_level
                        and alert.channel == AlertChannel.IN_APP
                    ),
                    None,
                )
                if source is None:
                    source = next(
                        (
                            alert
                            for alert in existing_levels
                            if alert.escalation_level == highest_level
                        ),
                        None,
                    )
                if source is None or source.status == AlertStatus.ACKED:
                    continue
                if not breached and source.created_at + timedelta(
                    days=max(config.escalation_after_days, 0)
                ) > now:
                    continue

            target_role: Role | None = None
            recipients: list[User] = []
            for role in _ESCALATION_CHAIN[next_level - 1 :]:
                recipients = self._users_for_role(application, role)
                if recipients:
                    target_role = role
                    break
            if target_role is None or not recipients:
                continue
            escalation = self._create_escalation(
                application=application,
                source=source,
                level=next_level,
                target_role=target_role,
                recipients=recipients,
            )
            self._mark_application_escalated(
                application,
                escalation=escalation,
                source=source,
                level=next_level,
                target_role=target_role,
                reason="sla_breached" if breached else "unacknowledged",
            )

    def _create_escalation(
        self,
        *,
        application: Application,
        source: Alert,
        level: int,
        target_role: Role,
        recipients: Sequence[User],
    ) -> list[Alert]:
        rule = self._db.get(AlertRule, source.rule_id) if source.rule_id else None
        channels = self._rule_channels(rule)
        context = self._context(application=application)
        role_label = _humanise(target_role.value)
        title = f"Escalation ({role_label}): {source.title}"
        message = (
            f"{source.title} was not acknowledged in time. The application "
            f"({context['application_reference']}) for {context['institution']} "
            f"has been escalated to the {role_label}."
        )
        created = self._create_alert(
            rule=rule,
            trigger=None,
            recipients=recipients,
            context=context,
            dedupe_base=f"escalation:{application.id}:{level}",
            title=title,
            application=application,
            message=message,
            severity=SEVERITY_RAISED[source.severity],
            channels=channels,
            type_override="ESCALATION",
            escalation_level=level,
            parent_alert_id=source.id,
        )
        if created:
            self.escalations += 1
        return created

    def _mark_application_escalated(
        self,
        application: Application,
        *,
        escalation: Sequence[Alert],
        source: Alert,
        level: int,
        target_role: Role,
        reason: str,
    ) -> None:
        if not escalation:
            return
        was_escalated = application.is_escalated
        application.is_escalated = True
        now = self._now()
        event = WorkflowEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=application.status,
            actor_id=None,
            action="escalate",
            comment=f"Alert escalated to the {_humanise(target_role.value)}",
            apH_clause="DEMO",
            details={
                "alert_id": str(escalation[0].id),
                "source_alert_id": str(source.id),
                "level": level,
                "target_role": target_role.value,
                "reason": reason,
            },
            created_at=now,
        )
        self._db.add(event)
        self._db.flush()
        self._audit.log(
            None,
            "alert.escalate",
            "Application",
            application.id,
            before={"is_escalated": was_escalated},
            after={
                "is_escalated": True,
                "level": level,
                "target_role": target_role.value,
                "alert_id": str(escalation[0].id),
            },
        )

    # ------------------------------------------------------------------
    # Rule matching and recipients
    # ------------------------------------------------------------------

    @staticmethod
    def _window_rule(rules: Sequence[AlertRule], days_until: int) -> AlertRule | None:
        """Pick the single threshold window containing ``days_until``."""
        ordered = sorted(rules, key=lambda rule: rule.days_before)
        for index, rule in enumerate(ordered):
            lower = ordered[index - 1].days_before if index > 0 else -1
            if lower < days_until <= rule.days_before:
                return rule
        return None

    @staticmethod
    def _due_rule(rules: Sequence[AlertRule], days_until: int) -> AlertRule | None:
        """Pick the most specific due-window rule for a non-negative day count."""
        matches = [rule for rule in rules if days_until <= rule.days_before]
        if not matches:
            return None
        return min(matches, key=lambda rule: rule.days_before)

    @staticmethod
    def _is_inactive(application: Application) -> bool:
        return application.is_withdrawn or application.status in TERMINAL_STATUSES

    def _initial_recipients(self, application: Application) -> list[User]:
        officer = application.assigned_officer
        if officer is not None and officer.is_active:
            return [officer]
        admin = self._institution_admin(application)
        if admin:
            return [admin]
        regional = self._users_for_role(application, Role.REGIONAL_OFFICER)
        if regional:
            return regional[:1]
        return self._users_for_role(application, Role.SUPER_ADMIN)[:1]

    def _institution_admin(self, application: Application) -> User | None:
        return self._db.scalar(
            select(User)
            .where(
                User.role == Role.INSTITUTION_ADMIN,
                User.institution_id == application.institution_id,
                User.is_active.is_(True),
            )
            .order_by(User.created_at.asc())
            .limit(1)
        )

    def _institution_admin_recipients(self, application: Application) -> list[User]:
        """Return every active institution administrator for the applicant.

        Letters, the Deficiency Report and the statutory clocks go to the
        institution's representatives, not only to the first account created.
        """
        return list(
            self._db.scalars(
                select(User)
                .where(
                    User.role == Role.INSTITUTION_ADMIN,
                    User.institution_id == application.institution_id,
                    User.is_active.is_(True),
                )
                .order_by(User.created_at.asc())
            ).all()
        )

    def _users_for_role(self, application: Application, role: Role) -> list[User]:
        query = select(User).where(User.role == role, User.is_active.is_(True))
        if role == Role.REGIONAL_OFFICER:
            region = application.institution.region
            if region is not None:
                query = query.where(User.region == region)
        elif role == Role.INSTITUTION_ADMIN:
            query = query.where(User.institution_id == application.institution_id)
        return list(
            self._db.scalars(query.order_by(User.created_at.asc())).all()
        )

    def _context(
        self,
        *,
        application: Application | None = None,
        institution: Institution | None = None,
        due_date: date | datetime | None = None,
        days_remaining: int | None = None,
        deficiency: Deficiency | None = None,
        document: Document | None = None,
        inspection: Inspection | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        institution = institution or (
            application.institution if application is not None else None
        )
        values = {
            "institution": institution.name if institution is not None else "the institution",
            "application_id": str(application.id) if application is not None else "not set",
            "application_reference": (
                application.reference
                if application is not None and application.reference
                else (str(application.id)[:8] if application is not None else "not set")
            ),
            "due_date": _format_due(due_date),
            "days_remaining": str(days_remaining if days_remaining is not None else ""),
            "status": (
                _humanise(application.status.value)
                if application is not None
                else "not set"
            ),
            "stage": (
                _humanise(application.current_stage.value)
                if application is not None
                else "not set"
            ),
            "deficiency": (
                deficiency.description if deficiency is not None else "not set"
            ),
            "document": document.filename if document is not None else "not set",
            "inspection_date": _format_due(
                inspection.scheduled_on if inspection is not None else None
            ),
        }
        if extra:
            values.update(extra)
        return values


def _compliance_recipients(
    db: Session, institution: Institution | None
) -> list[User]:
    """Regional officers for the institution plus every active super admin."""
    recipients: list[User] = []
    if institution is not None and institution.region:
        recipients.extend(
            db.scalars(
                select(User).where(
                    User.role == Role.REGIONAL_OFFICER,
                    User.region == institution.region,
                    User.is_active.is_(True),
                )
            ).all()
        )
    recipients.extend(
        db.scalars(
            select(User).where(
                User.role == Role.SUPER_ADMIN,
                User.is_active.is_(True),
            )
        ).all()
    )
    return recipients


def create_compliance_red_alerts(
    db: Session,
    *,
    institution: Institution | None,
    application: Application | None,
    score: float,
    failed_count: int,
    failed_critical_count: int,
    evaluated_at: datetime,
) -> int:
    """Create the rule-driven COMPLIANCE_RED alerts for one red flip.

    The alert type remains ``COMPLIANCE_RAG_RED`` for compatibility with the
    existing compliance monitor and audit history.
    """
    if institution is None:
        return 0
    rule = first_rule_for_handler(db, AlertTrigger.COMPLIANCE_RED.value)
    if rule is None:
        logger.warning("No active COMPLIANCE_RED alert rule is configured.")
        return 0

    engine = AlertEngine(
        db,
        SimulatedClock(),
        settings=get_settings(),
        now=evaluated_at,
    )
    context = engine._context(  # noqa: SLF001 - shared rule context helper
        application=application,
        institution=institution,
        extra={
            "score": f"{score:.1f}",
            "failed_count": str(failed_count),
            "failed_critical_count": str(failed_critical_count),
        },
    )
    created = engine._create_alert(  # noqa: SLF001
        rule=rule,
        trigger=AlertTrigger.COMPLIANCE_RED,
        recipients=_compliance_recipients(db, institution),
        context=context,
        dedupe_base=f"compliance_red:{institution.id}:{evaluated_at.isoformat()}",
        title=f"Compliance RED: {institution.name}",
        application=application,
        type_override="COMPLIANCE_RAG_RED",
    )
    return len(created)


def notify_deposit_step(
    db: Session,
    application: Application,
    clock: SimulatedClock,
    *,
    settings: Settings | None = None,
    notifications: NotificationService | None = None,
) -> int:
    """Alert the institution and Bureau after a Security Deposit ladder step.

    The workflow event and audit row are written by the state machine; this
    helper adds the rule-driven notification. The dedupe key contains the
    applied percentage and the resulting status, so the 10%, 20% and withdrawal
    steps each fire once even though the periodic scan runs repeatedly.
    """
    data = application.data if isinstance(application.data, dict) else {}
    percent = int(data.get("deposit_penalty_percent") or 0)
    withdrawn = application.status == ApplicationStatus.WITHDRAWN
    engine = AlertEngine(
        db,
        clock,
        settings=settings,
        notifications=notifications,
    )
    rule = first_rule_for_handler(db, AlertTrigger.DEPOSIT_PENALTY.value)
    if rule is None:
        return 0

    recipients = [
        *engine._institution_admin_recipients(application),  # noqa: SLF001
        *engine._users_for_role(  # noqa: SLF001
            application, Role.REGULATION_BUREAU_OFFICER
        ),
    ]
    recipients = list({user.id: user for user in recipients}.values())
    context = engine._context(  # noqa: SLF001
        application=application,
        extra={
            "penalty_percent": str(percent),
            "outcome": "withdrawn" if withdrawn else "penalty",
        },
    )
    if withdrawn:
        title = f"Approval withdrawn for unpaid Security Deposit: {context['institution']}"
    else:
        title = (
            f"Security Deposit penalty {percent}%: {context['institution']}"
        )
    created = engine._create_alert(  # noqa: SLF001
        rule=rule,
        trigger=AlertTrigger.DEPOSIT_PENALTY,
        recipients=recipients,
        context=context,
        dedupe_base=(
            f"deposit_penalty:{application.id}:{percent}:"
            f"{application.status.value}"
        ),
        title=title,
        application=application,
    )
    if not created:
        return 0
    db.commit()
    engine.deliver_pending(created)
    db.commit()
    return len(created)


def notify_workflow_event(
    db: Session,
    event: WorkflowEvent,
    application: Application,
    actor: User | None,
    notifications: NotificationService,
    clock: SimulatedClock,
) -> int:
    """Create rule-driven alerts for a status change or scheduled inspection."""
    engine = AlertEngine(db, clock, notifications=notifications)
    created: list[Alert] = []

    inspection_id = (event.details or {}).get("inspection_id")
    scheduled = event.to_status in {
        ApplicationStatus.EVC_CONSTITUTED,
        ApplicationStatus.RANDOM_EVC,
    }
    if scheduled:
        if inspection_id:
            try:
                parsed_id = uuid.UUID(str(inspection_id))
            except ValueError:
                parsed_id = None
            if parsed_id is not None:
                inspection = db.get(Inspection, parsed_id)
                if inspection is not None:
                    rule = engine._rules(
                        AlertTrigger.INSPECTION_SCHEDULED
                    )[0:1]  # noqa: SLF001
                    if rule:
                        committee = inspection.committee_member
                        recipients = (
                            [committee]
                            if committee is not None and committee.is_active
                            else engine._initial_recipients(application)  # noqa: SLF001
                        )
                        context = engine._context(  # noqa: SLF001
                            application=application,
                            due_date=inspection.scheduled_on,
                            inspection=inspection,
                        )
                        created = engine._create_alert(  # noqa: SLF001
                            rule=rule[0],
                            trigger=AlertTrigger.INSPECTION_SCHEDULED,
                            recipients=recipients,
                            context=context,
                            dedupe_base=f"inspection_scheduled:{inspection.id}",
                            title=f"Inspection scheduled: {context['institution']}",
                            application=application,
                        )
    elif event.from_status is not None and event.from_status != event.to_status:
        if event.action == "assign_scrutiny":
            # Assignment is recorded on the submit notification rather than
            # producing a second, noisy status alert.
            pass
        else:
            rules = engine._rules(AlertTrigger.APPLICATION_STATUS_CHANGED)  # noqa: SLF001
            if rules:
                letter_number = (event.details or {}).get("letter_number")
                # Letters and the automatic Deficiency Report belong to the
                # institution, not to the reviewing officer.
                institution_action = event.action in {
                    "communicate_deficiency",
                    "run_self_disclosure_check",
                    "issue_letter",
                    "issue_loa",
                    "issue_eoa",
                    "issue_lod",
                    "issue_lor",
                } or bool(letter_number)
                if institution_action:
                    recipients = (
                        engine._institution_admin_recipients(  # noqa: SLF001
                            application
                        )
                        or engine._initial_recipients(application)  # noqa: SLF001
                    )
                else:
                    recipients = engine._initial_recipients(application)  # noqa: SLF001
                context = engine._context(  # noqa: SLF001
                    application=application,
                    extra={
                        "from_status": _humanise(event.from_status.value),
                        "status_code": event.to_status.value,
                        "action": event.action or "",
                    },
                )
                title = (
                    f"Decision letter issued: {letter_number}"
                    if letter_number
                    else f"Status updated: {context['application_reference']}"
                )
                created = engine._create_alert(  # noqa: SLF001
                    rule=rules[0],
                    trigger=AlertTrigger.APPLICATION_STATUS_CHANGED,
                    recipients=recipients,
                    context=context,
                    dedupe_base=f"status_changed:{event.id}",
                    title=title,
                    application=application,
                )

    if not created:
        return 0
    db.commit()
    engine.deliver_pending(created)
    db.commit()
    return len(created)


def _document_recipients(
    application: Application, *, reviewer: bool
) -> list[User]:
    """Return the institution admins or the assigned reviewer for a document alert."""
    if reviewer:
        officer = application.assigned_officer
        if officer is not None and officer.is_active:
            return [officer]
        return list(
            {
                user.id: user
                for user in (
                    application.institution.users
                    if application.institution is not None
                    else []
                )
                if user.role == Role.SCRUTINY_COMMITTEE_MEMBER and user.is_active
            }.values()
        )
    return [user for user in application.institution.users if user.role == Role.INSTITUTION_ADMIN]


def notify_document_rejected(
    db: Session,
    *,
    application: Application,
    document: Document,
    actor: User,
    notifications: NotificationService,
    clock: SimulatedClock,
) -> int:
    """Tell the institution that a reviewer rejected a document (APH 1.8f)."""
    engine = AlertEngine(db, clock, notifications=notifications)
    recipients = _document_recipients(application, reviewer=False)
    if not recipients:
        return 0
    deficiency = (
        db.get(Deficiency, document.related_deficiency_id)
        if document.related_deficiency_id is not None
        else None
    )
    due = deficiency.due_date if deficiency is not None else None
    reason = (
        document.rejection_reason_code.value
        if document.rejection_reason_code is not None
        else "OTHER"
    )
    title = f"Document rejected: {application.institution.name}"
    message = (
        f"{document.doc_type} version {document.version} was rejected by {actor.name}. "
        f"Reason: {reason}. "
        f"{document.rejection_comment or ''} Re-upload a compliant version"
        + (f" by {_format_due(due)}" if due is not None else "")
        + " (APH 1.8f, 2.4)."
    )
    created = engine._create_alert(  # noqa: SLF001 - reuse the shared alert engine
        rule=first_rule_for_handler(db, "DOCUMENT_REJECTED"),
        trigger=None,
        recipients=recipients,
        context=engine._context(  # noqa: SLF001
            application=application, due_date=due, document=document
        ),
        dedupe_base=f"document_rejected:{document.id}:{document.version}",
        title=title,
        message=message,
        type_override="DOCUMENT_REJECTED",
        severity=Severity.HIGH,
        channels=[AlertChannel.IN_APP, AlertChannel.EMAIL],
        application=application,
    )
    if created:
        engine.deliver_pending(created)
        db.commit()
    return len(created)


def notify_document_reuploaded(
    db: Session,
    *,
    application: Application,
    document: Document,
    actor: User,
    notifications: NotificationService,
    clock: SimulatedClock,
) -> int:
    """Tell the reviewer that the institution re-uploaded a document (APH 2.4)."""
    engine = AlertEngine(db, clock, notifications=notifications)
    recipients = _document_recipients(application, reviewer=True)
    if not recipients:
        return 0
    title = f"Document re-uploaded: {application.institution.name}"
    message = (
        f"{actor.name} re-uploaded {document.doc_type} as version {document.version} "
        "after a rejection. Review the replacement (APH 1.8g, 2.4)."
    )
    created = engine._create_alert(  # noqa: SLF001 - reuse the shared alert engine
        rule=first_rule_for_handler(db, "DOCUMENT_REUPLOADED"),
        trigger=None,
        recipients=recipients,
        context=engine._context(  # noqa: SLF001
            application=application, document=document
        ),
        dedupe_base=f"document_reuploaded:{document.id}",
        title=title,
        message=message,
        type_override="DOCUMENT_REUPLOADED",
        severity=Severity.MEDIUM,
        channels=[AlertChannel.IN_APP, AlertChannel.EMAIL],
        application=application,
    )
    if created:
        engine.deliver_pending(created)
        db.commit()
    return len(created)


def run_alert_scan(
    *,
    clock: SimulatedClock | None = None,
    settings: Settings | None = None,
    deliver: bool = True,
) -> AlertScanResult:
    """Run one periodic scan in its own database session.

    ``deliver=False`` is used by the stepwise DEBUG time simulation so email
    is sent once after the whole replay, not from every intermediate day.
    """
    clock = clock or SimulatedClock()
    settings = settings or get_settings()
    with SessionLocal() as db:
        engine = AlertEngine(db, clock, settings=settings)
        result = engine.scan()
        # Only publish after the commit: subscribers must never be told about
        # rows that a rollback could still discard.
        db.commit()
        sent = engine.deliver_pending() if deliver else 0
        db.commit()
        publish_created_alerts(engine)
        publish_clock(clock)
        return AlertScanResult(
            alerts_created=result.alerts_created,
            escalations=result.escalations,
            notifications_sent=sent,
            scanned_at=result.scanned_at,
        )


def acknowledge_alert(
    db: Session,
    alert: Alert,
    actor: User,
    *,
    now: datetime,
) -> Alert:
    """Mark an in-app alert acknowledged and record the audit entry."""
    if alert.status == AlertStatus.ACKED:
        return alert
    before = {
        "status": alert.status.value,
        "acknowledged_at": (
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None
        ),
    }
    alert.status = AlertStatus.ACKED
    alert.acknowledged_at = now
    alert.acknowledged_by_id = actor.id
    db.flush()
    AuditService(db).log(
        actor,
        "alert.acknowledge",
        "Alert",
        alert.id,
        before=before,
        after={
            "status": alert.status.value,
            "acknowledged_at": now.isoformat(),
            "acknowledged_by_id": str(actor.id),
        },
    )
    return alert


def utc_now() -> datetime:
    """Small injectable helper used by API routes and tests."""
    return datetime.now(UTC)
