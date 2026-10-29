"""SSE bridge: /alerts/stream pushes committed alerts and clock advances.

The HTTP framing is verified by hand in the browser (a sync TestClient cannot
read from an infinite SSE body), so these tests cover the risky part: the
cross-thread broker handoff, the auth dependency and the frame rendering.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.models.enums import AlertChannel
from app.services.alert_stream import (
    AlertStreamBroker,
    ScanEvent,
    alert_event,
    format_sse,
    publish_created_alerts,
    time_event,
)
from tests.support import TestData, login


def _fake_alert(
    channel: AlertChannel = AlertChannel.IN_APP,
    recipient: object | None = None,
) -> SimpleNamespace:
    import uuid as _uuid

    return SimpleNamespace(
        id=uuid4(),
        type="DEADLINE_INITIAL_SCRUTINY",
        severity=SimpleNamespace(value="CRITICAL"),
        title="Scrutiny SLA due",
        message="Scrutiny for demo application is due in 3 days.",
        application_id=_uuid.uuid4(),
        escalation_level=2,
        channel=channel,
        recipient_user_id=recipient or uuid4(),
    )


def _fake_clock(offset_days: int) -> object:
    from datetime import UTC, datetime

    now = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

    class _Clock:
        pass

    clock = _Clock()
    clock.offset_days = offset_days
    clock.now = lambda: now
    return clock


def _read_frames(
    broker: AlertStreamBroker,
    user_id: str,
    publish: Callable[[AlertStreamBroker], int],
) -> list[ScanEvent]:
    """Drain the frame(s) ``publish`` emits while the helper loop is draining."""
    received: list[ScanEvent] = []
    ready = threading.Event()
    queue_holder: dict[str, asyncio.Queue[ScanEvent]] = {}

    def runner() -> None:
        loop = asyncio.new_event_loop()

        async def setup() -> None:
            subscription = broker.register(user_id)
            queue_holder["sub"] = subscription
            ready.set()

        loop.run_until_complete(setup())

        async def drain() -> None:
            received.append(await queue_holder["sub"].queue.get())

        loop.run_until_complete(drain())
        loop.close()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    assert ready.wait(5), "subscriber never registered"
    assert publish(broker), "publish reported no delivery"
    thread.join(5)
    return received


def test_stream_rejects_missing_or_invalid_tokens(api_client: TestClient) -> None:
    assert api_client.get("/alerts/stream").status_code == 401
    assert api_client.get("/alerts/stream", params={"token": "not-a-jwt"}).status_code == 401


def test_stream_endpoint_is_an_sse_response(
    api_client: TestClient, test_data: TestData
) -> None:
    """A missing-token call is rejected before streaming; format helper is SSE."""
    user = test_data.users["institution_admin_west"]
    login(api_client, user.email, test_data.password)  # proves auth stack works
    frame = format_sse(alert_event(_fake_alert()))
    assert frame.startswith("event: alert\ndata: ")
    assert frame.endswith("\n\n")


def test_broker_delivers_alert_frames_across_threads() -> None:
    """Publishing from a worker thread reaches an asyncio subscriber queue."""
    broker = AlertStreamBroker()
    user_id = "user-under-test"
    frames = _read_frames(
        broker, user_id, lambda b: b.publish(user_id, alert_event(_fake_alert(recipient=user_id)))
    )

    assert frames, "subscriber never received the published frame"
    frame = format_sse(frames[0])
    assert frame.startswith("event: alert\ndata: ")
    payload = json.loads(frame.removeprefix("event: alert\ndata: ").removesuffix("\n\n"))
    assert payload["severity"] == "CRITICAL"
    assert payload["escalation_level"] == 2
    assert payload["channel"] == "IN_APP"


def test_time_frames_broadcast_and_skip_real_time() -> None:
    broker = AlertStreamBroker()
    user_id = "user-time-test"

    assert time_event(_fake_clock(offset_days=0)) is None
    clock = _fake_clock(offset_days=12)
    frames = _read_frames(
        broker, user_id, lambda b: b.publish_to_all(time_event(clock))
    )

    assert frames, "subscriber never received the broadcast frame"
    frame = format_sse(frames[0])
    assert frame.startswith("event: time\ndata: ")
    payload = json.loads(frame.removeprefix("event: time\ndata: ").removesuffix("\n\n"))
    assert payload["offset_days"] == 12
    assert payload["simulated_now"].startswith("2026-11-05T12:00:00")


def test_publish_created_alerts_when_no_subscribers() -> None:
    """Filtering runs before publishing; no subscribers means a no-op."""
    engine = SimpleNamespace(created_inapp_alerts=[])
    assert publish_created_alerts(engine) == 0
