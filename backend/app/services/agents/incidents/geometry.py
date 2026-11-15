"""Encoded polyline decoding and metric geometry helpers for incident checks."""

from __future__ import annotations

import math
from typing import Any


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google/OTP encoded polyline into ``(lat, lon)`` pairs."""
    if not isinstance(encoded, str) or not encoded:
        return []
    points: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(encoded)
    while index < length:
        result = 0
        shift = 0
        while True:
            if index >= length:
                return points
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else result >> 1
        lat += delta_lat

        result = 0
        shift = 0
        while True:
            if index >= length:
                return points
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lon = ~(result >> 1) if result & 1 else result >> 1
        lon += delta_lon
        points.append((lat / 1e5, lon / 1e5))
    return points


def leg_polyline(leg: dict[str, Any]) -> tuple[list[tuple[float, float]], str]:
    """Return a usable line and an explicit provenance label."""
    geometry = leg.get("geometry")
    if isinstance(geometry, str) and geometry.strip():
        decoded = decode_polyline(geometry)
        if len(decoded) >= 2:
            return decoded, "otp_polyline"
    start = leg.get("from_lat"), leg.get("from_lon")
    end = leg.get("to_lat"), leg.get("to_lon")
    if all(isinstance(value, (int, float)) for value in (*start, *end)):
        return [(float(start[0]), float(start[1])), (float(end[0]), float(end[1]))], "endpoints"
    return [], "missing"


def line_wkt(points: list[tuple[float, float]]) -> str | None:
    if len(points) < 2:
        return None
    values = ", ".join(f"{lon:.7f} {lat:.7f}" for lat, lon in points)
    return f"LINESTRING({values})"


def point_wkt(lat: float, lon: float) -> str:
    return f"POINT({lon:.7f} {lat:.7f})"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def point_to_segment_m(
    lat: float,
    lon: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Planar approximation in metres, adequate for short urban segments."""
    scale_x = 111320.0 * math.cos(math.radians(lat))
    scale_y = 110540.0
    px, py = lon * scale_x, lat * scale_y
    ax, ay = start[1] * scale_x, start[0] * scale_y
    bx, by = end[1] * scale_x, end[0] * scale_y
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return haversine_m(lat, lon, start[0], start[1])
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_polyline_m(lat: float, lon: float, points: list[tuple[float, float]]) -> float:
    if not points:
        return float("inf")
    if len(points) == 1:
        return haversine_m(lat, lon, points[0][0], points[0][1])
    return min(
        point_to_segment_m(lat, lon, points[index], points[index + 1])
        for index in range(len(points) - 1)
    )


__all__ = [
    "decode_polyline",
    "distance_to_polyline_m",
    "haversine_m",
    "leg_polyline",
    "line_wkt",
    "point_wkt",
]
