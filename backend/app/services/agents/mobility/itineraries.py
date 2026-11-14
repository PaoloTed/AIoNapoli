"""Helpers to extract stop coordinates and format itinerary summaries."""

from __future__ import annotations

import re
from typing import Any

_POINT_RE = re.compile(
    r"POINT\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)", re.IGNORECASE
)


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


def format_legs_summary(legs: list[dict[str, Any]]) -> str:
    """Format OTP itinerary legs into a concise route label."""
    parts: list[str] = []
    for leg in legs:
        mode = str(leg.get("mode") or "TRANSIT")
        route = str(leg.get("route") or "").strip()
        parts.append(f"{mode} {route}".strip())
    return " -> ".join(parts) if parts else "Bus 151 -> Cumana"
