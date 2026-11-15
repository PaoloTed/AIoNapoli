"""Injectable clock abstractions for deterministic execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Clock protocol returning timezone-aware datetimes."""

    def now(self) -> datetime:
        """Return current datetime."""
        ...


class SystemClock:
    """System clock defaulting to Europe/Rome timezone."""

    def __init__(self, tz_name: str = "Europe/Rome") -> None:
        self._tz = ZoneInfo(tz_name)

    def now(self) -> datetime:
        return datetime.now(tz=self._tz)


class FixedClock:
    """Deterministic fixed clock for tests and replay."""

    def __init__(self, fixed_dt: datetime) -> None:
        if fixed_dt.tzinfo is None:
            fixed_dt = fixed_dt.replace(tzinfo=timezone.utc)
        self._fixed_dt = fixed_dt

    def now(self) -> datetime:
        return self._fixed_dt
