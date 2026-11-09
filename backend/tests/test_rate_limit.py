"""Unit tests for the in-process login rate limiter."""

from __future__ import annotations

from app.core.rate_limit import LoginRateLimiter, rate_limit_key


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _limiter(clock: _Clock) -> LoginRateLimiter:
    return LoginRateLimiter(
        max_attempts=3,
        window_seconds=60,
        block_seconds=120,
        time_source=clock,
    )


def test_limiter_blocks_after_threshold_and_expires() -> None:
    clock = _Clock()
    limiter = _limiter(clock)

    for _ in range(2):
        assert limiter.register_failure("ip|user") == 0
    assert limiter.register_failure("ip|user") == 120
    assert limiter.check("ip|user") == 120

    clock.now += 120
    assert limiter.check("ip|user") == 0
    assert limiter.register_failure("ip|user") == 0


def test_limiter_prunes_failures_outside_the_window() -> None:
    clock = _Clock()
    limiter = _limiter(clock)

    assert limiter.register_failure("ip|user") == 0
    clock.now += 61
    assert limiter.register_failure("ip|user") == 0
    assert limiter.register_failure("ip|user") == 0
    # The first failure has aged out, so the third attempt does not block.
    assert limiter.check("ip|user") == 0


def test_successful_login_resets_the_bucket() -> None:
    clock = _Clock()
    limiter = _limiter(clock)

    limiter.register_failure("ip|user")
    limiter.register_failure("ip|user")
    limiter.reset("ip|user")
    assert limiter.check("ip|user") == 0
    assert limiter.register_failure("ip|user") == 0


def test_keys_are_per_source_and_normalised_email() -> None:
    assert rate_limit_key("10.0.0.1", " User@Example.EDU ") == "10.0.0.1|user@example.edu"
    assert rate_limit_key(None, "a@b") == "unknown|a@b"


def test_invalid_constructor_values_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        LoginRateLimiter(max_attempts=0, window_seconds=60, block_seconds=60)
