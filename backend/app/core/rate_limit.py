"""In-process login throttling.

The MVP runs a single Uvicorn process (or a small number of workers) without
Redis or Celery, so login throttling is kept in process memory. The limiter
counts *failed* attempts in a sliding window per key and blocks the key for a
short period once the threshold is crossed.

Keys are ``"<client-ip>|<email>"``: this slows down password spraying against a
single account without letting one user's failures lock out every account
behind the same NAT. For a multi-process or multi-host deployment, move the
state to Redis - see ``docs/ROADMAP.md`` and ``docs/SECURITY.md``.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class _Bucket:
    """Failures and block expiry for one ``client-ip|email`` key."""

    failures: list[float] = field(default_factory=list)
    blocked_until: float = 0.0


class LoginRateLimiter:
    """Sliding-window failure counter with a temporary block.

    The limiter is thread-safe because Uvicorn may run sync endpoints in a
    worker thread pool. ``time_source`` is injectable so tests can advance time
    without sleeping.
    """

    def __init__(
        self,
        *,
        max_attempts: int,
        window_seconds: int,
        block_seconds: int,
        max_keys: int = 10_000,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_attempts < 1 or window_seconds < 1 or block_seconds < 1:
            raise ValueError("rate-limit values must be positive")
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._block_seconds = block_seconds
        self._max_keys = max_keys
        self._time_source = time_source
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int:
        """Return seconds to wait when ``key`` is blocked, otherwise ``0``."""
        now = self._time_source()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return 0
            if bucket.blocked_until > now:
                return max(1, math.ceil(bucket.blocked_until - now))
            if bucket.blocked_until:
                # Block expired: start a clean window.
                bucket.blocked_until = 0.0
                bucket.failures.clear()
            self._prune(bucket, now)
            if len(bucket.failures) >= self._max_attempts:
                bucket.blocked_until = now + self._block_seconds
                bucket.failures.clear()
                return self._block_seconds
            if not bucket.failures:
                self._buckets.pop(key, None)
            return 0

    def register_failure(self, key: str) -> int:
        """Record one failed attempt and return block seconds if now blocked."""
        now = self._time_source()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._evict_if_full()
                bucket = _Bucket()
                self._buckets[key] = bucket
            if bucket.blocked_until > now:
                return max(1, math.ceil(bucket.blocked_until - now))
            self._prune(bucket, now)
            bucket.failures.append(now)
            if len(bucket.failures) >= self._max_attempts:
                bucket.blocked_until = now + self._block_seconds
                bucket.failures.clear()
                return self._block_seconds
            return 0

    def reset(self, key: str) -> None:
        """Clear the failures for ``key`` after a successful login."""
        with self._lock:
            self._buckets.pop(key, None)

    def clear(self) -> None:
        """Drop all state. Used by tests and on a demo reset."""
        with self._lock:
            self._buckets.clear()

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self._window_seconds
        bucket.failures = [stamp for stamp in bucket.failures if stamp >= cutoff]

    def _evict_if_full(self) -> None:
        if len(self._buckets) < self._max_keys:
            return
        oldest = next(iter(self._buckets), None)
        if oldest is not None:
            self._buckets.pop(oldest, None)


def rate_limit_key(client_ip: str | None, email: str) -> str:
    """Build the stable key used for one source/account pair."""
    return f"{client_ip or 'unknown'}|{email.strip().lower()}"
