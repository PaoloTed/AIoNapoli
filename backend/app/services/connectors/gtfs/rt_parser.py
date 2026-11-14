"""Normalization of GTFS-RT VehiclePositions and TripUpdates JSON payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_REL_MAP: dict[str, str] = {
    "SCHEDULED": "scheduled",
    "SKIPPED": "skipped",
    "CANCELED": "canceled",
    "CANCELLED": "canceled",
    "NO_DATA": "no_data",
}


def _ts_to_iso(ts_val: Any, fallback: datetime) -> str:
    if isinstance(ts_val, (int, float)) and not isinstance(ts_val, bool):
        return datetime.fromtimestamp(float(ts_val), tz=timezone.utc).isoformat()
    if isinstance(ts_val, str) and ts_val.strip():
        try:
            dt = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
            return (
                dt.replace(tzinfo=timezone.utc)
                if dt.tzinfo is None
                else dt.astimezone(timezone.utc)
            ).isoformat()
        except ValueError:
            pass
    return fallback.isoformat()


def parse_vehicle_positions(
    payload: dict[str, Any] | list[Any],
    *,
    proxy_url: str,
    primary_source_id: str = "anm",
    is_simulated: bool = False,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize GTFS-RT VehiclePositions into vehicle_positions table rows."""
    ref_now = now or datetime.now(timezone.utc)
    if isinstance(payload, list):
        entities = payload
        header_ts_iso = ref_now.isoformat()
    else:
        header = payload.get("header") or {}
        header_ts_iso = _ts_to_iso(header.get("timestamp"), ref_now)
        entities = payload.get("entity") or []

    data_ref = f"{proxy_url}?ts={header_ts_iso}"
    rows: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        veh_block = entity.get("vehicle") or {}
        pos = veh_block.get("position") or {}
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        if lat is None or lon is None:
            continue
        veh_desc = veh_block.get("vehicle") or {}
        trip_desc = veh_block.get("trip") or {}
        vehicle_id = str(veh_desc.get("id") or entity.get("id") or "").strip()
        if not vehicle_id:
            continue
        observed_iso = _ts_to_iso(veh_block.get("timestamp"), ref_now)
        rows.append(
            {
                "vehicle_id": vehicle_id,
                "route_id": trip_desc.get("route_id"),
                "trip_id": trip_desc.get("trip_id"),
                "observed_at": observed_iso,
                "latitude": float(lat),
                "longitude": float(lon),
                "bearing": float(pos["bearing"]) if pos.get("bearing") is not None else None,
                "speed_mps": float(pos["speed"]) if pos.get("speed") is not None else None,
                "zone_id": veh_block.get("zone_id"),
                "source_id": primary_source_id,
                "data_reference": data_ref,
                "is_simulated": is_simulated,
                "ingested_at": ref_now.isoformat(),
            }
        )
    return rows


def parse_trip_updates(
    payload: dict[str, Any] | list[Any],
    *,
    proxy_url: str,
    primary_source_id: str = "anm",
    is_simulated: bool = False,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize GTFS-RT TripUpdates into trip_updates table rows."""
    ref_now = now or datetime.now(timezone.utc)
    if isinstance(payload, list):
        entities = payload
        header_ts_iso = ref_now.isoformat()
    else:
        header = payload.get("header") or {}
        header_ts_iso = _ts_to_iso(header.get("timestamp"), ref_now)
        entities = payload.get("entity") or []

    data_ref = f"{proxy_url}?ts={header_ts_iso}"
    rows: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        tu = entity.get("trip_update") or {}
        trip_desc = tu.get("trip") or {}
        trip_id = str(trip_desc.get("trip_id") or "").strip()
        if not trip_id:
            continue
        route_id = trip_desc.get("route_id")
        observed_iso = _ts_to_iso(tu.get("timestamp"), ref_now)
        stop_updates = tu.get("stop_time_update") or [{}]

        for stu in stop_updates:
            rel_raw = str(stu.get("schedule_relationship") or "SCHEDULED").upper()
            rel = _REL_MAP.get(rel_raw, "scheduled")
            arr_delay = (stu.get("arrival") or {}).get("delay")
            dep_delay = (stu.get("departure") or {}).get("delay")
            if arr_delay is not None and int(arr_delay) <= -3600:
                arr_delay = None
            if dep_delay is not None and int(dep_delay) <= -3600:
                dep_delay = None
            rows.append(
                {
                    "trip_id": trip_id,
                    "route_id": route_id,
                    "stop_id": stu.get("stop_id"),
                    "stop_sequence": stu.get("stop_sequence"),
                    "arrival_delay_s": int(arr_delay) if arr_delay is not None else None,
                    "departure_delay_s": int(dep_delay) if dep_delay is not None else None,
                    "schedule_relationship": rel,
                    "observed_at": observed_iso,
                    "source_id": primary_source_id,
                    "data_reference": data_ref,
                    "is_simulated": is_simulated,
                    "ingested_at": ref_now.isoformat(),
                }
            )
    return rows
