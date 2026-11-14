"""Explicit content accessors returning None when a field is absent (D-02)."""

from __future__ import annotations

from app.domain.models.finding import Finding


def density(finding: Finding) -> float | None:
    """Return normalized density in 0..1 or None if missing."""
    value = finding.content.get("density")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def zone_id(finding: Finding) -> str | None:
    """Return operational zone identifier or None if missing."""
    value = finding.content.get("zone_id")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None


def heavy_rain(finding: Finding) -> bool | None:
    """Return heavy_rain boolean flag or None if missing."""
    value = finding.content.get("heavy_rain")
    if not isinstance(value, bool):
        return None
    return value


def congestion(finding: Finding) -> float | None:
    """Return normalized congestion in 0..1 or None if missing."""
    value = finding.content.get("congestion")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def expected_attendance(finding: Finding) -> int | None:
    """Return expected attendance integer or None if missing."""
    value = finding.content.get("expected_attendance")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value

