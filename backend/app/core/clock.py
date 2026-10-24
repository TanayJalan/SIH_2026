"""Simulated time for demo flows.

The application reads time through :class:`SimulatedClock` so the DEBUG-only
demo control can move deadlines forward without changing the server clock.
The offset is process-local and intentionally not persisted.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class SimulatedClock:
    """A UTC clock with an adjustable forward offset."""

    _offset: timedelta = field(default_factory=timedelta)

    @property
    def offset_days(self) -> int:
        """Return the whole-day offset currently applied."""
        return self._offset.days

    def now(self) -> datetime:
        """Return the current simulated UTC time."""
        return datetime.now(UTC) + self._offset

    def advance(self, days: int) -> None:
        """Move the simulated clock forward by ``days``."""
        if days < 0:
            raise ValueError("days must not be negative")
        self._offset += timedelta(days=days)

    def reset(self) -> None:
        """Remove the simulated offset."""
        self._offset = timedelta(0)
