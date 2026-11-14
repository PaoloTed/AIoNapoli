"""Relational (PostgreSQL / SQLite) implementation of SourceRepository and AuditStore."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.migrations import is_sqlite_connection
from app.domain.models.decision import Decision
from app.domain.models.finding import Finding
from app.utils.canonical import canonical_json


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _as_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return _parse_dt(value).isoformat()
    return _parse_dt(str(value)).isoformat()


class PostgresSourceRepository:
    """SQL repository supporting both PostgreSQL (psycopg) and SQLite connections."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._sqlite = is_sqlite_connection(conn)

    def _ph(self, count: int) -> str:
        token = "?" if self._sqlite else "%s"
        return ", ".join(token for _ in range(count))

    def _p(self) -> str:
        return "?" if self._sqlite else "%s"

    def _row_to_dict(self, cur: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {k: row[k] for k in row.keys()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [self._row_to_dict(cur, r) for r in rows]

    def upsert_zones(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        p = self._p()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO zones (zone_id, name, geometry)
                VALUES ({p}, {p}, {p})
                ON CONFLICT (zone_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    geometry = EXCLUDED.geometry
                """,
                (row["zone_id"], row["name"], row.get("geometry")),
            )
        self._conn.commit()
        return len(rows)

    def get_zones(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT zone_id, name, geometry FROM zones ORDER BY zone_id")

    def upsert_stops(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        p = self._p()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO stops (
                    stop_id, stop_name, zone_id, geometry,
                    source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT (stop_id) DO UPDATE SET
                    stop_name = EXCLUDED.stop_name,
                    zone_id = EXCLUDED.zone_id,
                    geometry = EXCLUDED.geometry,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["stop_id"],
                    row["stop_name"],
                    row["zone_id"],
                    row["geometry"],
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_stops(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if zone_id is not None:
            return self._fetchall(
                f"SELECT * FROM stops WHERE zone_id = {p} ORDER BY stop_id", (zone_id,)
            )
        return self._fetchall("SELECT * FROM stops ORDER BY stop_id")

    def upsert_routes(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        p = self._p()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO routes (
                    route_id, route_short_name, route_type,
                    source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT (route_id) DO UPDATE SET
                    route_short_name = EXCLUDED.route_short_name,
                    route_type = EXCLUDED.route_type,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["route_id"],
                    row.get("route_short_name"),
                    int(row["route_type"]),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_routes(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM routes ORDER BY route_id")

    def upsert_trips(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        p = self._p()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO trips (
                    trip_id, route_id, service_id,
                    source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT (trip_id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    service_id = EXCLUDED.service_id,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["trip_id"],
                    row["route_id"],
                    row["service_id"],
                    row["source_id"],
                    row.get("data_reference", ""),
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_trips(self, route_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if route_id is not None:
            return self._fetchall(
                f"SELECT * FROM trips WHERE route_id = {p} ORDER BY trip_id", (route_id,)
            )
        return self._fetchall("SELECT * FROM trips ORDER BY trip_id")

    def upsert_stop_times(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        p = self._p()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO stop_times (
                    trip_id, stop_id, stop_sequence, arrival_time, departure_time,
                    source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                    stop_id = EXCLUDED.stop_id,
                    arrival_time = EXCLUDED.arrival_time,
                    departure_time = EXCLUDED.departure_time,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["trip_id"],
                    row["stop_id"],
                    int(row["stop_sequence"]),
                    row.get("arrival_time"),
                    row.get("departure_time"),
                    row["source_id"],
                    row.get("data_reference", ""),
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_stop_times(self, trip_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if trip_id is not None:
            return self._fetchall(
                f"SELECT * FROM stop_times WHERE trip_id = {p} ORDER BY trip_id, stop_sequence",
                (trip_id,),
            )
        return self._fetchall("SELECT * FROM stop_times ORDER BY trip_id, stop_sequence")

    def upsert_service_alerts(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO service_alerts (
                    alert_id, route_id, stop_id, severity, valid_from, valid_to,
                    source_id, confidence, title, body, zone_id, is_simulated,
                    data_reference, ingested_at
                )
                VALUES ({self._ph(14)})
                ON CONFLICT (source_id, alert_id) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    stop_id = EXCLUDED.stop_id,
                    severity = EXCLUDED.severity,
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to,
                    confidence = EXCLUDED.confidence,
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    zone_id = EXCLUDED.zone_id,
                    is_simulated = EXCLUDED.is_simulated,
                    data_reference = EXCLUDED.data_reference
                """,
                (
                    row["alert_id"],
                    row.get("route_id"),
                    row.get("stop_id"),
                    row["severity"],
                    _as_iso(row["valid_from"]),
                    _as_iso(row["valid_to"]) if row.get("valid_to") is not None else None,
                    row["source_id"],
                    float(row["confidence"]),
                    row["title"],
                    row.get("body"),
                    row.get("zone_id"),
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    row["data_reference"],
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_active_service_alerts(self, now: datetime | None = None) -> list[dict[str, Any]]:
        items = self._fetchall("SELECT * FROM service_alerts ORDER BY source_id, alert_id")
        if now is None:
            return items
        ref_now = _parse_dt(now)
        return [
            r for r in items if r.get("valid_to") is None or _parse_dt(r["valid_to"]) >= ref_now
        ]

    def upsert_events(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO events (
                    event_id, name, zone_id, geofence, expected_attendance,
                    window_start, window_end, source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({self._ph(11)})
                ON CONFLICT (event_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    zone_id = EXCLUDED.zone_id,
                    geofence = EXCLUDED.geofence,
                    expected_attendance = EXCLUDED.expected_attendance,
                    window_start = EXCLUDED.window_start,
                    window_end = EXCLUDED.window_end,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["event_id"],
                    row["name"],
                    row["zone_id"],
                    row["geofence"],
                    int(row["expected_attendance"]),
                    _as_iso(row["window_start"]),
                    _as_iso(row["window_end"]),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", True)))
                    if self._sqlite
                    else bool(row.get("is_simulated", True)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_events(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if zone_id is not None:
            return self._fetchall(
                f"SELECT * FROM events WHERE zone_id = {p} ORDER BY event_id", (zone_id,)
            )
        return self._fetchall("SELECT * FROM events ORDER BY event_id")

    def upsert_weather_snapshots(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO weather_snapshots (
                    snapshot_at, forecast_at, zone_id, precipitation_mm, alert_level,
                    heavy_rain, expected_impact, source_id, data_reference,
                    is_simulated, ingested_at
                )
                VALUES ({self._ph(11)})
                ON CONFLICT (source_id, zone_id, forecast_at) DO UPDATE SET
                    snapshot_at = EXCLUDED.snapshot_at,
                    precipitation_mm = EXCLUDED.precipitation_mm,
                    alert_level = EXCLUDED.alert_level,
                    heavy_rain = EXCLUDED.heavy_rain,
                    expected_impact = EXCLUDED.expected_impact,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    _as_iso(row["snapshot_at"]),
                    _as_iso(row["forecast_at"]),
                    row.get("zone_id"),
                    row.get("precipitation_mm"),
                    row.get("alert_level"),
                    int(bool(row.get("heavy_rain", False)))
                    if self._sqlite
                    else bool(row.get("heavy_rain", False)),
                    row.get("expected_impact"),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_latest_weather(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if zone_id is not None:
            return self._fetchall(
                f"SELECT * FROM v_weather_latest WHERE zone_id = {p} ORDER BY source_id",
                (zone_id,),
            )
        return self._fetchall("SELECT * FROM v_weather_latest ORDER BY source_id, zone_id")

    def upsert_occupancy_estimates(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO occupancy_estimates (
                    vehicle_id, line, occupancy_pct, observed_at,
                    source_id, data_reference, is_simulated, ingested_at
                )
                VALUES ({self._ph(8)})
                ON CONFLICT (vehicle_id, line, observed_at) DO UPDATE SET
                    occupancy_pct = EXCLUDED.occupancy_pct,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["vehicle_id"],
                    row["line"],
                    float(row["occupancy_pct"]),
                    _as_iso(row["observed_at"]),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", True)))
                    if self._sqlite
                    else bool(row.get("is_simulated", True)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_latest_occupancy(self, line: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if line is not None:
            return self._fetchall(
                f"SELECT * FROM v_occupancy_latest WHERE line = {p} ORDER BY vehicle_id",
                (line,),
            )
        return self._fetchall("SELECT * FROM v_occupancy_latest ORDER BY line, vehicle_id")

    def upsert_vehicle_positions(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO vehicle_positions (
                    vehicle_id, route_id, trip_id, observed_at, latitude, longitude,
                    bearing, speed_mps, zone_id, source_id, data_reference,
                    is_simulated, ingested_at
                )
                VALUES ({self._ph(13)})
                ON CONFLICT (vehicle_id, observed_at) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    trip_id = EXCLUDED.trip_id,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    bearing = EXCLUDED.bearing,
                    speed_mps = EXCLUDED.speed_mps,
                    zone_id = EXCLUDED.zone_id,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["vehicle_id"],
                    row.get("route_id"),
                    row.get("trip_id"),
                    _as_iso(row["observed_at"]),
                    float(row["latitude"]),
                    float(row["longitude"]),
                    row.get("bearing"),
                    row.get("speed_mps"),
                    row.get("zone_id"),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_fresh_vehicle_positions(
        self,
        now: datetime,
        max_age_s: int = 90,
        route_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ref_now = _parse_dt(now)
        cutoff = ref_now - timedelta(seconds=max_age_s)
        rows = self._fetchall("SELECT * FROM vehicle_positions ORDER BY vehicle_id, observed_at")
        latest_by_vehicle: dict[str, dict[str, Any]] = {}
        for row in rows:
            if route_id is not None and row.get("route_id") != route_id:
                continue
            obs = _parse_dt(row["observed_at"])
            if obs < cutoff:
                continue
            vid = str(row["vehicle_id"])
            prev = latest_by_vehicle.get(vid)
            if prev is None or obs >= _parse_dt(prev["observed_at"]):
                latest_by_vehicle[vid] = row
        return [latest_by_vehicle[v] for v in sorted(latest_by_vehicle.keys())]

    def upsert_trip_updates(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cur = self._conn.cursor()
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO trip_updates (
                    trip_id, route_id, stop_id, stop_sequence, arrival_delay_s, departure_delay_s,
                    schedule_relationship, observed_at, source_id, data_reference,
                    is_simulated, ingested_at
                )
                VALUES ({self._ph(12)})
                ON CONFLICT (trip_id, stop_id, observed_at) DO UPDATE SET
                    route_id = EXCLUDED.route_id,
                    stop_sequence = EXCLUDED.stop_sequence,
                    arrival_delay_s = EXCLUDED.arrival_delay_s,
                    departure_delay_s = EXCLUDED.departure_delay_s,
                    schedule_relationship = EXCLUDED.schedule_relationship,
                    source_id = EXCLUDED.source_id,
                    data_reference = EXCLUDED.data_reference,
                    is_simulated = EXCLUDED.is_simulated
                """,
                (
                    row["trip_id"],
                    row.get("route_id"),
                    row.get("stop_id"),
                    row.get("stop_sequence"),
                    row.get("arrival_delay_s"),
                    row.get("departure_delay_s"),
                    row["schedule_relationship"],
                    _as_iso(row["observed_at"]),
                    row["source_id"],
                    row["data_reference"],
                    int(bool(row.get("is_simulated", False)))
                    if self._sqlite
                    else bool(row.get("is_simulated", False)),
                    _as_iso(row.get("ingested_at", datetime.now(timezone.utc))),
                ),
            )
        self._conn.commit()
        return len(rows)

    def get_latest_trip_updates(self, route_id: str | None = None) -> list[dict[str, Any]]:
        p = self._p()
        if route_id is not None:
            return self._fetchall(
                f"SELECT * FROM v_trip_updates_latest WHERE route_id = {p} ORDER BY trip_id",
                (route_id,),
            )
        return self._fetchall("SELECT * FROM v_trip_updates_latest ORDER BY trip_id")

    def record_ingestion_run(self, row: dict[str, Any]) -> None:
        cur = self._conn.cursor()
        cur.execute(
            f"""
            INSERT INTO ingestion_runs (
                connector, started_at, finished_at, rows_written, is_simulated, outcome, detail
            )
            VALUES ({self._ph(7)})
            """,
            (
                row["connector"],
                _as_iso(row["started_at"]),
                _as_iso(row["finished_at"]),
                int(row["rows_written"]),
                int(bool(row["is_simulated"])) if self._sqlite else bool(row["is_simulated"]),
                row["outcome"],
                row.get("detail"),
            ),
        )
        self._conn.commit()

    def get_ingestion_runs(self) -> list[dict[str, Any]]:
        return self._fetchall("SELECT * FROM ingestion_runs ORDER BY run_id")


class PostgresAuditStore:
    """SQL AuditStore implementation supporting both PostgreSQL and SQLite."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._sqlite = is_sqlite_connection(conn)

    def _ph(self, count: int) -> str:
        token = "?" if self._sqlite else "%s"
        return ", ".join(token for _ in range(count))

    def _p(self) -> str:
        return "?" if self._sqlite else "%s"

    def _row_to_dict(self, cur: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {k: row[k] for k in row.keys()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

    def save_finding(self, finding: Finding, finding_ref: str) -> None:
        cur = self._conn.cursor()
        payload_json = canonical_json(finding)
        cur.execute(
            f"""
            INSERT INTO findings (
                finding_ref, agent, type, severity, is_simulated, payload, received_at
            )
            VALUES ({self._ph(7)})
            ON CONFLICT (finding_ref) DO NOTHING
            """,
            (
                finding_ref,
                finding.agent.value,
                finding.type.value,
                finding.severity.value,
                int(finding.is_simulated) if self._sqlite else finding.is_simulated,
                payload_json,
                finding.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def get_finding(self, finding_ref: str) -> Finding | None:
        cur = self._conn.cursor()
        p = self._p()
        cur.execute(f"SELECT payload FROM findings WHERE finding_ref = {p}", (finding_ref,))
        row = cur.fetchone()
        if row is None:
            return None
        row_dict = self._row_to_dict(cur, row)
        payload = row_dict["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return Finding.model_validate(payload)

    def list_findings(self) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM findings ORDER BY finding_ref")
        return [self._row_to_dict(cur, r) for r in cur.fetchall()]

    def save_decision(self, decision: Decision, decision_id: str) -> None:
        cur = self._conn.cursor()
        payload_json = canonical_json(decision)
        cur.execute(
            f"""
            INSERT INTO decisions (
                decision_id, trigger_rule, conflict_detected, payload, created_at
            )
            VALUES ({self._ph(5)})
            ON CONFLICT (decision_id) DO NOTHING
            """,
            (
                decision_id,
                decision.trigger.rule_id.value,
                int(decision.conflict.detected) if self._sqlite else decision.conflict.detected,
                payload_json,
                decision.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        cur = self._conn.cursor()
        p = self._p()
        cur.execute(f"SELECT * FROM decisions WHERE decision_id = {p}", (decision_id,))
        row = cur.fetchone()
        if row is None:
            return None
        d = self._row_to_dict(cur, row)
        if isinstance(d.get("payload"), str):
            d["payload"] = json.loads(d["payload"])
        return d

    def list_decisions(self) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM decisions ORDER BY decision_id")
        rows = [self._row_to_dict(cur, r) for r in cur.fetchall()]
        for r in rows:
            if isinstance(r.get("payload"), str):
                r["payload"] = json.loads(r["payload"])
        return rows
