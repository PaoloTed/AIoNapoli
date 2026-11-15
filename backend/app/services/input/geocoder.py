"""Geocoder with 5-stage resolution and strict Naples bounding box (05_agente_input.md §3)."""

from __future__ import annotations

import re
from typing import Literal

from app.domain.models.trip_request import TripLocation

# Naples bounding box: lat in [40.75, 40.95], lon in [14.10, 14.40]
NAPLES_LAT_MIN = 40.75
NAPLES_LAT_MAX = 40.95
NAPLES_LON_MIN = 14.10
NAPLES_LON_MAX = 14.40

_COORD_RE = re.compile(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")

# Known zones dictionary (05_agente_input.md §3.2)
ZONES_DICT: dict[
    str, tuple[float, float, Literal["zone", "stop", "poi", "address", "coordinate"]]
] = {
    "bagnoli": (40.8135, 14.1634, "zone"),
    "fuorigrotta": (40.8259, 14.1912, "zone"),
    "centro": (40.8522, 14.2724, "zone"),
    "chiaia": (40.8350, 14.2320, "zone"),
    "vomero": (40.8450, 14.2310, "zone"),
    "posillipo": (40.8050, 14.2050, "zone"),
    "toledo": (40.8430, 14.2490, "address"),
    "via toledo": (40.8430, 14.2490, "address"),
    "garibaldi": (40.8522, 14.2724, "stop"),
    "piazza garibaldi": (40.8522, 14.2724, "stop"),
    "stazione centrale": (40.8522, 14.2724, "stop"),
    "plebiscito": (40.8358, 14.2488, "poi"),
    "piazza plebiscito": (40.8358, 14.2488, "poi"),
    "piazza del plebiscito": (40.8358, 14.2488, "poi"),
    "via coroglio": (40.8062, 14.1755, "address"),
    "campi flegrei": (40.8259, 14.1912, "stop"),
    "mostra d'oltremare": (40.8240, 14.1880, "poi"),
    "mann": (40.8536, 14.2505, "poi"),
    "museo archeologico": (40.8536, 14.2505, "poi"),
    "museo archeologico nazionale": (40.8536, 14.2505, "poi"),
    "maschio angioino": (40.8385, 14.2527, "poi"),
    "castel nuovo": (40.8385, 14.2527, "poi"),
    "capodimonte": (40.8670, 14.2504, "poi"),
    "stadio maradona": (40.8279, 14.1930, "poi"),
}


def is_in_naples_bounds(lat: float, lon: float) -> bool:
    """Validate that coordinates fall strictly within the metropolitan area of Naples."""
    return NAPLES_LAT_MIN <= lat <= NAPLES_LAT_MAX and NAPLES_LON_MIN <= lon <= NAPLES_LON_MAX


class Geocoder:
    """Resolves raw place names or coordinates into TripLocation with caching."""

    def __init__(
        self, custom_dictionary: dict[str, tuple[float, float, str]] | None = None
    ) -> None:
        self._dict = {**ZONES_DICT}
        if custom_dictionary:
            for k, v in custom_dictionary.items():
                self._dict[k.lower().strip()] = (v[0], v[1], v[2])  # type: ignore[assignment]
        self._cache: dict[str, TripLocation | None] = {}

    def resolve(self, raw_text: str) -> TripLocation | None:
        cleaned = raw_text.strip()
        norm_key = cleaned.lower()

        if norm_key in self._cache:
            return self._cache[norm_key]

        # Stage 1: Explicit coordinates
        m_coord = _COORD_RE.search(cleaned)
        if m_coord:
            lat = float(m_coord.group(1))
            lon = float(m_coord.group(2))
            if is_in_naples_bounds(lat, lon):
                loc = TripLocation(
                    label=cleaned,
                    lat=lat,
                    lon=lon,
                    kind="coordinate",
                    resolved_by="dictionary",
                )
                self._cache[norm_key] = loc
                return loc

        # Stage 2 & 3: Known zones and POIs dictionary
        if norm_key in self._dict:
            lat, lon, kind = self._dict[norm_key]
            if is_in_naples_bounds(lat, lon):
                loc = TripLocation(
                    label=cleaned.title(),
                    lat=lat,
                    lon=lon,
                    kind=kind,
                    resolved_by="dictionary",
                )
                self._cache[norm_key] = loc
                return loc

        # Stage 4: Substring match in dictionary
        for dict_key, (lat, lon, kind) in self._dict.items():
            if dict_key in norm_key or norm_key in dict_key:
                if is_in_naples_bounds(lat, lon):
                    loc = TripLocation(
                        label=dict_key.title(),
                        lat=lat,
                        lon=lon,
                        kind=kind,
                        resolved_by="dictionary",
                    )
                    self._cache[norm_key] = loc
                    return loc

        self._cache[norm_key] = None
        return None
