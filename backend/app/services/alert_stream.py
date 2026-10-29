"""In-process SSE broker for live alert and simulated-clock events.

The alert scans run in APScheduler worker threads (and the DEBUG
time-simulation route), while SSE subscribers are asyncio tasks in the
server's event loop. The broker therefore records each subscriber's running
loop and hands events over with ``call_soon_threadsafe``, so a publisher in
any thread can enqueue without touching the loop directly.

Only events that are already committed to the database are published: if the
publish itself fails, the subscriber simply misses the push and the next
poll picks the rows up.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.models.alert import Alert

if TYPE_CHECKING:
    from app.services.alert_engine import AlertEngine

logger = logging.getLogger("app.alerts.stream")

# Bound per subscriber so a slow consumer cannot accumulate unbounded state.
_QUEUE_LIMIT = 128


@dataclass(frozen=True)
class ScanEvent:
    """One SSE frame: an event name and a JSON-serialisable payload."""

    event: str
    payload: dict[str, Any]


def format_sse(event: ScanEvent) -> str:
    """Render one event as a Server-Sent Events frame."""
    data = json.dumps(event.payload, separators=(",", ":"), default=str)
    return f"event: {event.event}\ndata: {data}\n\n"


def alert_event(alert: Alert) -> ScanEvent:
    """Build the ``alert`` frame for one committed in-app alert row."""
    return ScanEvent(
        event="alert",
        payload={
            "id": str(alert.id),
            "type": alert.type,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "application_id": (
                str(alert.application_id) if alert.application_id is not None else None
            ),
            "escalation_level": alert.escalation_level,
            "channel": alert.channel.value,
        },
    )


def time_event(clock: Any, *, force: bool = False) -> ScanEvent | None:
    """Build the ``time`` frame for a simulated clock, or ``None`` in real time.

    The demo clock is the only consumer: a running offset tells the browser
    that every countdown and deadline view may have drifted forward. Pass
    ``force=True`` when the offset just returned to zero so subscribers learn
    the replay is over.
    """
    offset_days = getattr(clock, "offset_days", 0)
    if not offset_days and not force:
        return None
    now = clock.now()
    return ScanEvent(
        event="time",
        payload={
            "simulated_now": now.isoformat() if isinstance(now, datetime) else str(now),
            "offset_days": offset_days,
        },
    )


class AlertStreamBroker:
    """Fan out committed scan events to per-user asyncio queues."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_Subscriber]] = {}
        self._lock = threading.Lock()

    def register(self, user_id: str) -> _Subscriber:
        """Subscribe one connection for the user; call from the event loop."""
        subscriber = _Subscriber()
        with self._lock:
            self._subscribers.setdefault(user_id, []).append(subscriber)
        return subscriber

    def unregister(self, user_id: str, subscriber: _Subscriber) -> None:
        """Drop a subscription; safe to call after the client disconnected."""
        with self._lock:
            subscribers = self._subscribers.get(user_id)
            if subscribers is None:
                return
            try:
                subscribers.remove(subscriber)
            except ValueError:
                pass
            if not subscribers:
                self._subscribers.pop(user_id, None)

    def publish(self, user_id: str, event: ScanEvent) -> int:
        """Deliver an event to every live connection of one user."""
        with self._lock:
            targets = list(self._subscribers.get(user_id, ()))
        published = 0
        for subscriber in targets:
            if subscriber.offer(event):
                published += 1
        return published

    def publish_to_all(self, event: ScanEvent) -> int:
        """Broadcast an event to every connected user."""
        with self._lock:
            users = [(user_id, list(subs)) for user_id, subs in self._subscribers.items()]
        published = 0
        for _user_id, subscribers in users:
            for subscriber in subscribers:
                if subscriber.offer(event):
                    published += 1
        return published


class _Subscriber:
    """A single SSE connection: its loop and a bounded event queue."""

    __slots__ = ("loop", "queue")

    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.queue: asyncio.Queue[ScanEvent] = asyncio.Queue(maxsize=_QUEUE_LIMIT)

    def offer(self, event: ScanEvent) -> bool:
        """Push one event onto the queue from any thread, without blocking."""
        try:
            self.loop.call_soon_threadsafe(self._put, event)
            return True
        except RuntimeError:  # pragma: no cover - loop shut down mid-publish
            return False

    def _put(self, event: ScanEvent) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            # Slow SSE consumer: drop instead of blocking the scan thread.
            logger.warning("alert stream queue full; dropping event %s", event.event)


_broker: AlertStreamBroker | None = None
_broker_lock = threading.Lock()


def get_alert_stream_broker() -> AlertStreamBroker:
    """Return the process-wide broker singleton."""
    global _broker
    with _broker_lock:
        if _broker is None:
            _broker = AlertStreamBroker()
        return _broker


def publish_created_alerts(engine: AlertEngine) -> int:
    """Publish the in-app alert rows a committed scan created.

    In-app rows are the user's inbox entries and drive the toast and the bell
    count. EMAIL/SMS rows are delivery records and never stream. Call this
    only after the transaction that created the alerts committed.
    """
    broker = get_alert_stream_broker()
    published = 0
    for alert in engine.created_inapp_alerts:
        published += broker.publish(str(alert.recipient_user_id), alert_event(alert))
    if published:
        logger.debug("alert stream published %d events", published)
    return published


def publish_clock(clock: Any, *, force: bool = False) -> int:
    """Broadcast a simulated-time event, or nothing when the clock is real."""
    event = time_event(clock, force=force)
    if event is None:
        return 0
    return get_alert_stream_broker().publish_to_all(event)
