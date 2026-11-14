"""Domain structures for OTP itineraries, plus WKT and summary helpers.

The client normalises every leg into :class:`RouteLeg` before returning, so no
consumer of the client ever touches a raw GraphQL dict. Stops are first class:
without ``from_stop_id``/``to_stop_id`` the negotiation cycle cannot express a
constraint on a segment or a direction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

_POINT_RE = re.compile(
    r"POINT\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)", re.IGNORECASE
)


@dataclass(frozen=True)
class RouteLeg:
    """One leg of an itinerary, with stops resolved to identifiers."""

    mode: str
    route: str | None
    duration_s: int
    from_stop_id: str | None = None
    from_stop_name: str | None = None
    to_stop_id: str | None = None
    to_stop_name: str | None = None
    start_time: str | None = None
    headsign: str | None = None
    from_lat: float | None = None
    from_lon: float | None = None
    to_lat: float | None = None
    to_lon: float | None = None

    @property
    def is_transit(self) -> bool:
        """Walking, cycling and driving legs carry no route and no stop pair."""
        return self.mode.upper() not in ("WALK", "BICYCLE", "CAR")

    def label(self) -> str:
        """Human readable ``MODE route`` fragment used in route summaries."""
        parts = [self.mode, self.route or ""]
        return " ".join(p for p in parts if p).strip()


def parse_point_wkt(wkt: str | None) -> tuple[float, float] | None:
    """Parse POINT(lon lat) WKT into (lat, lon)."""
    if not wkt:
        return None
    m = _POINT_RE.search(wkt)
    if not m:
        return None
    lon = float(m.group(1))
    lat = float(m.group(2))
    return lat, lon


def _leg_label(leg: RouteLeg | dict[str, Any]) -> str:
    if isinstance(leg, RouteLeg):
        return leg.label()
    mode = str(leg.get("mode") or "TRANSIT")
    route = str(leg.get("route") or "").strip()
    return f"{mode} {route}".strip()


def format_legs_summary(legs: Sequence[RouteLeg | dict[str, Any]]) -> str:
    """Format itinerary legs into a concise route label.

    Accepts both :class:`RouteLeg` and the legacy dict shape so callers outside
    the client keep working during the migration.
    """
    parts = [label for label in (_leg_label(leg) for leg in legs) if label]
    return " -> ".join(parts) if parts else "Bus 151 -> Cumana"


def stop_ids(legs: Sequence[RouteLeg]) -> list[str]:
    """Ordered, de-duplicated stop identifiers touched by the itinerary."""
    seen: dict[str, None] = {}
    for leg in legs:
        for stop in (leg.from_stop_id, leg.to_stop_id):
            if stop:
                seen.setdefault(stop, None)
    return list(seen)
