"""Unit conversions with a single source of truth (D-15)."""

from __future__ import annotations


def occupancy_to_density(occupancy_pct: float) -> float:
    """Convert occupancy percentage (0..100) into normalized density (0..1)."""
    if isinstance(occupancy_pct, bool) or not isinstance(occupancy_pct, (int, float)):
        raise ValueError("occupancy_pct deve essere numerico")
    if occupancy_pct < 0.0 or occupancy_pct > 100.0:
        raise ValueError("occupancy_pct deve essere compreso tra 0 e 100")
    return round(float(occupancy_pct) / 100.0, 4)

