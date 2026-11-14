"""In-memory repository and audit store implementations with optional fixture seeding."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class InMemorySourceRepository:
    """Thread-safe/deterministic in-memory implementation of SourceRepository."""

    def __init__(self, *, load_fixtures: bool = True) -> None:
        self._zones: dict[str, dict[str, Any]] = {}
        self._stops: dict[str, dict[str, Any]] = {}
        self._routes: dict[str, dict[str, Any]] = {}
        self._trips: dict[str, dict[str, Any]] = {}
        self._stop_times: dict[tuple[str, int], dict[str, Any]] = {}
        self._service_alerts: dict[tuple[str, str], dict[str, Any]] = {}
        self._events: dict[str, dict[str, Any]] = {}
        self._weather: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._occupancy: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._vehicle_positions: dict[tuple[str, str], dict[str, Any]] = {}
        self._trip_updates: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._ingestion_runs: list[dict[str, Any]] = []
        if load_fixtures:
            self._seed_defaults()

    def _seed_defaults(self) -> None:
        zones_csv = _repo_root() / "database" / "seed" / "zones.csv"
        if zones_csv.exists():
            with zones_csv.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                zones_rows: list[dict[str, Any]] = []
                stops_rows: list[dict[str, Any]] = []
                for row in reader:
                    zones_rows.append(
                        {
                            "zone_id": row["zone_id"],
                            "name": row["name"],
                            "geometry": row["polygon_wkt"],
                        }
                    )
                    stops_rows.append(
                        {
                            "stop_id": row["stop_id"],
                            "stop_name": row["stop_name"],
                            "zone_id": row["zone_id"],
                            "geometry": f"POINT({row['lon']} {row['lat']})",
                            "source_id": "anm",
                            "data_reference": "seed:zones.csv",
                            "is_simulated": False,
                            "ingested_at": "2026-11-14T08:00:00+00:00",
                        }
                    )
                self.upsert_zones(zones_rows)
                self.upsert_stops(stops_rows)

        self.upsert_routes(
            [
                {
                    "route_id": "L2",
                    "route_short_name": "Linea 2",
                    "route_type": 1,
                    "source_id": "anm",
                    "data_reference": "seed:routes",
                    "is_simulated": False,
                    "ingested_at": "2026-11-14T08:00:00+00:00",
                },
                {
                    "route_id": "R2",
                    "route_short_name": "R2",
                    "route_type": 3,
                    "source_id": "anm",
                    "data_reference": "seed:routes",
                    "is_simulated": False,
                    "ingested_at": "2026-11-14T08:00:00+00:00",
                },
                {
                    "route_id": "151",
                    "route_short_name": "151",
                    "route_type": 3,
                    "source_id": "anm",
                    "data_reference": "seed:routes",
                    "is_simulated": False,
                    "ingested_at": "2026-11-14T08:00:00+00:00",
                },
            ]
        )

    def upsert_zones(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self._zones[str(row["zone_id"])] = dict(row)
        return len(rows)

    def get_zones(self) -> list[dict[str, Any]]:
        return [dict(self._zones[k]) for k in sorted(self._zones.keys())]

    def upsert_stops(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self._stops[str(row["stop_id"])] = dict(row)
        return len(rows)

    def get_stops(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        items = [dict(self._stops[k]) for k in sorted(self._stops.keys())]
        if zone_id is not None:
            return [r for r in items if r.get("zone_id") == zone_id]
        return items

    def upsert_routes(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self._routes[str(row["route_id"])] = dict(row)
        return len(rows)

    def get_routes(self) -> list[dict[str, Any]]:
        return [dict(self._routes[k]) for k in sorted(self._routes.keys())]

    def upsert_trips(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self._trips[str(row["trip_id"])] = dict(row)
        return len(rows)

    def get_trips(self, route_id: str | None = None) -> list[dict[str, Any]]:
        items = [dict(self._trips[k]) for k in sorted(self._trips.keys())]
        if route_id is not None:
            return [r for r in items if r.get("route_id") == route_id]
        return items

    def upsert_stop_times(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (str(row["trip_id"]), int(row["stop_sequence"]))
            self._stop_times[key] = dict(row)
        return len(rows)

    def get_stop_times(self, trip_id: str | None = None) -> list[dict[str, Any]]:
        items = [dict(self._stop_times[k]) for k in sorted(self._stop_times.keys())]
        if trip_id is not None:
            return [r for r in items if r.get("trip_id") == trip_id]
        return items

    def upsert_service_alerts(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (str(row["source_id"]), str(row["alert_id"]))
            self._service_alerts[key] = dict(row)
        return len(rows)

    def get_active_service_alerts(self, now: datetime | None = None) -> list[dict[str, Any]]:
        items = [dict(self._service_alerts[k]) for k in sorted(self._service_alerts.keys())]
        if now is None:
            return items
        ref_now = _parse_dt(now)
        active: list[dict[str, Any]] = []
        for r in items:
            valid_to = r.get("valid_to")
            if valid_to is None or _parse_dt(valid_to) >= ref_now:
                active.append(r)
        return active

    def upsert_events(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            self._events[str(row["event_id"])] = dict(row)
        return len(rows)

    def get_events(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        items = [dict(self._events[k]) for k in sorted(self._events.keys())]
        if zone_id is not None:
            return [r for r in items if r.get("zone_id") == zone_id]
        return items

    def upsert_weather_snapshots(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (
                str(row["source_id"]),
                str(row.get("zone_id") or ""),
                str(row["forecast_at"]),
            )
            self._weather[key] = dict(row)
        return len(rows)

    def get_latest_weather(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        latest_by_group: dict[tuple[str, str], dict[str, Any]] = {}
        for k in sorted(self._weather.keys()):
            row = self._weather[k]
            if zone_id is not None and row.get("zone_id") != zone_id:
                continue
            group = (str(row["source_id"]), str(row.get("zone_id") or ""))
            prev = latest_by_group.get(group)
            if prev is None or _parse_dt(row["forecast_at"]) >= _parse_dt(prev["forecast_at"]):
                latest_by_group[group] = dict(row)
        return [latest_by_group[g] for g in sorted(latest_by_group.keys())]

    def upsert_occupancy_estimates(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (str(row["vehicle_id"]), str(row["line"]), str(row["observed_at"]))
            self._occupancy[key] = dict(row)
        return len(rows)

    def get_latest_occupancy(self, line: str | None = None) -> list[dict[str, Any]]:
        latest_by_group: dict[tuple[str, str], dict[str, Any]] = {}
        for k in sorted(self._occupancy.keys()):
            row = self._occupancy[k]
            if line is not None and row.get("line") != line:
                continue
            group = (str(row["vehicle_id"]), str(row["line"]))
            prev = latest_by_group.get(group)
            if prev is None or _parse_dt(row["observed_at"]) >= _parse_dt(prev["observed_at"]):
                latest_by_group[group] = dict(row)
        return [latest_by_group[g] for g in sorted(latest_by_group.keys())]

    def upsert_vehicle_positions(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (str(row["vehicle_id"]), str(row["observed_at"]))
            self._vehicle_positions[key] = dict(row)
        return len(rows)

    def get_fresh_vehicle_positions(
        self,
        now: datetime,
        max_age_s: int = 90,
        route_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ref_now = _parse_dt(now)
        cutoff = ref_now - timedelta(seconds=max_age_s)
        latest_by_vehicle: dict[str, dict[str, Any]] = {}
        for k in sorted(self._vehicle_positions.keys()):
            row = self._vehicle_positions[k]
            if route_id is not None and row.get("route_id") != route_id:
                continue
            obs = _parse_dt(row["observed_at"])
            if obs < cutoff:
                continue
            vid = str(row["vehicle_id"])
            prev = latest_by_vehicle.get(vid)
            if prev is None or obs >= _parse_dt(prev["observed_at"]):
                latest_by_vehicle[vid] = dict(row)
        return [latest_by_vehicle[v] for v in sorted(latest_by_vehicle.keys())]

    def upsert_trip_updates(self, rows: list[dict[str, Any]]) -> int:
        for row in rows:
            key = (
                str(row["trip_id"]),
                str(row.get("stop_id") or ""),
                str(row["observed_at"]),
            )
            self._trip_updates[key] = dict(row)
        return len(rows)

    def get_latest_trip_updates(self, route_id: str | None = None) -> list[dict[str, Any]]:
        latest_by_group: dict[tuple[str, str], dict[str, Any]] = {}
        for k in sorted(self._trip_updates.keys()):
            row = self._trip_updates[k]
            if route_id is not None and row.get("route_id") != route_id:
                continue
            group = (str(row["trip_id"]), str(row.get("stop_id") or ""))
            prev = latest_by_group.get(group)
            if prev is None or _parse_dt(row["observed_at"]) >= _parse_dt(prev["observed_at"]):
                latest_by_group[group] = dict(row)
        return [latest_by_group[g] for g in sorted(latest_by_group.keys())]

    def record_ingestion_run(self, row: dict[str, Any]) -> None:
        entry = dict(row)
        entry.setdefault("run_id", len(self._ingestion_runs) + 1)
        self._ingestion_runs.append(entry)

    def get_ingestion_runs(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._ingestion_runs]


class InMemoryAuditStore:
    """In-memory append-only/idempotent audit store for Findings and Decisions."""

    def __init__(self) -> None:
        self._findings: dict[str, dict[str, Any]] = {}
        self._decisions: dict[str, dict[str, Any]] = {}

    def save_finding(self, finding: Finding, finding_ref: str) -> None:
        if finding_ref not in self._findings:
            self._findings[finding_ref] = {
                "finding_ref": finding_ref,
                "agent": finding.agent.value,
                "type": finding.type.value,
                "severity": finding.severity.value,
                "is_simulated": finding.is_simulated,
                "payload": json.loads(canonical_json(finding)),
                "received_at": finding.timestamp.isoformat(),
            }

    def get_finding(self, finding_ref: str) -> Finding | None:
        row = self._findings.get(finding_ref)
        if row is None:
            return None
        return Finding.model_validate(row["payload"])

    def list_findings(self) -> list[dict[str, Any]]:
        return [dict(self._findings[k]) for k in sorted(self._findings.keys())]

    def save_decision(self, decision: Decision, decision_id: str) -> None:
        if decision_id not in self._decisions:
            self._decisions[decision_id] = {
                "decision_id": decision_id,
                "trigger_rule": decision.trigger.rule_id.value,
                "conflict_detected": decision.conflict.detected,
                "payload": json.loads(canonical_json(decision)),
                "created_at": decision.timestamp.isoformat(),
            }

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        row = self._decisions.get(decision_id)
        return dict(row) if row is not None else None

    def list_decisions(self) -> list[dict[str, Any]]:
        return [dict(self._decisions[k]) for k in sorted(self._decisions.keys())]
