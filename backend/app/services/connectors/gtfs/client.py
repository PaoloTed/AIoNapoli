"""Static GTFS loader for stops, routes, trips, and stop_times."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories.base import SourceRepository


class GtfsStaticClient:
    """Loads GTFS static tables from CSV fixtures or GTFS zip archives."""

    def __init__(self, repository: SourceRepository, source_id: str = "anm") -> None:
        self._repo = repository
        self.source_id = source_id

    def load_from_zones_seed(self, csv_path: str | Path | None = None) -> int:
        """Seed normalized stops, routes, trips, and stop_times from curated seed."""
        repo_root = Path(__file__).resolve().parents[5]
        target = (
            Path(csv_path)
            if csv_path is not None
            else repo_root / "database" / "seed" / "zones.csv"
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        total = 0

        if target.exists():
            zones: list[dict[str, Any]] = []
            stops: list[dict[str, Any]] = []
            with target.open(encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    zones.append(
                        {
                            "zone_id": row["zone_id"],
                            "name": row["name"],
                            "geometry": row["polygon_wkt"],
                        }
                    )
                    stops.append(
                        {
                            "stop_id": row["stop_id"],
                            "stop_name": row["stop_name"],
                            "zone_id": row["zone_id"],
                            "geometry": f"POINT({row['lon']} {row['lat']})",
                            "source_id": self.source_id,
                            "data_reference": f"seed:{target.name}",
                            "is_simulated": False,
                            "ingested_at": now_iso,
                        }
                    )
            total += self._repo.upsert_zones(zones)
            total += self._repo.upsert_stops(stops)

        routes = [
            {
                "route_id": "L2",
                "route_short_name": "Linea 2",
                "route_type": 1,
                "source_id": "fs",
                "data_reference": "gtfs_static:fs_passante",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "route_id": "R2",
                "route_short_name": "R2",
                "route_type": 3,
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "route_id": "151",
                "route_short_name": "151",
                "route_type": 3,
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
        ]
        total += self._repo.upsert_routes(routes)

        trips = [
            {
                "trip_id": "TRIP_R2_01",
                "route_id": "R2",
                "service_id": "WEEKDAY",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "trip_id": "TRIP_151_01",
                "route_id": "151",
                "service_id": "WEEKDAY",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
        ]
        total += self._repo.upsert_trips(trips)

        stop_times = [
            {
                "trip_id": "TRIP_R2_01",
                "stop_id": "STOP_GAR_01",
                "stop_sequence": 1,
                "arrival_time": "17:00:00",
                "departure_time": "17:02:00",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "trip_id": "TRIP_R2_01",
                "stop_id": "STOP_MUN_01",
                "stop_sequence": 2,
                "arrival_time": "17:15:00",
                "departure_time": "17:16:00",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "trip_id": "TRIP_151_01",
                "stop_id": "STOP_GAR_01",
                "stop_sequence": 1,
                "arrival_time": "17:05:00",
                "departure_time": "17:06:00",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
            {
                "trip_id": "TRIP_151_01",
                "stop_id": "STOP_FUO_01",
                "stop_sequence": 2,
                "arrival_time": "17:25:00",
                "departure_time": "17:26:00",
                "source_id": self.source_id,
                "data_reference": "gtfs_static:anm",
                "is_simulated": False,
                "ingested_at": now_iso,
            },
        ]
        total += self._repo.upsert_stop_times(stop_times)
        return total

    def load_from_zip_bytes(self, zip_bytes: bytes, data_reference: str) -> int:
        """Parse routes and stops from a GTFS zip archive bytes buffer."""
        now_iso = datetime.now(timezone.utc).isoformat()
        total = 0
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            if "stops.txt" in names:
                reader = csv.DictReader(io.StringIO(zf.read("stops.txt").decode("utf-8-sig")))
                rows = [
                    {
                        "stop_id": r["stop_id"],
                        "stop_name": r["stop_name"],
                        "zone_id": r.get("zone_id") or "Z_NAPOLI",
                        "geometry": f"POINT({r['stop_lon']} {r['stop_lat']})",
                        "source_id": self.source_id,
                        "data_reference": data_reference,
                        "is_simulated": False,
                        "ingested_at": now_iso,
                    }
                    for r in reader
                ]
                total += self._repo.upsert_stops(rows)
            if "routes.txt" in names:
                reader = csv.DictReader(io.StringIO(zf.read("routes.txt").decode("utf-8-sig")))
                rows = [
                    {
                        "route_id": r["route_id"],
                        "route_short_name": r.get("route_short_name"),
                        "route_type": int(r.get("route_type", 3)),
                        "source_id": self.source_id,
                        "data_reference": data_reference,
                        "is_simulated": False,
                        "ingested_at": now_iso,
                    }
                    for r in reader
                ]
                total += self._repo.upsert_routes(rows)
        return total
