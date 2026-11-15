#!/usr/bin/env python3
"""Compare an OTP itinerary's feed-scoped IDs with the persisted GTFS schema.

Usage:
    python infra/otp/verify_persisted_itinerary.py \
      --artifact /path/to/baseline-a.json \
      --database-url postgresql://... --schema gtfs_eav

The OTP feed prefix is read from each ``gtfsId``; it is never assumed to be
"1". The database is queried through the backend repository, not raw tables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.session import get_postgres_connection
from app.repositories.postgres import PostgresSourceRepository
from app.services.agents.mobility.gtfs_ids import parse_otp_id


def _transit_legs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    connection = (payload.get("data") or {}).get("planConnection") or {}
    edges = connection.get("edges") or []
    if not edges:
        raise SystemExit("artifact senza itinerari")
    legs: list[dict[str, Any]] = []
    for edge in edges:
        for leg in (edge.get("node") or {}).get("legs") or []:
            if leg.get("transitLeg"):
                legs.append(leg)
    if not legs:
        raise SystemExit("artifact senza leg di trasporto pubblico")
    return legs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--schema", default="gtfs_eav")
    parser.add_argument("--dataset-key", default="eav")
    args = parser.parse_args()

    payload = json.loads(args.artifact.read_text(encoding="utf-8"))
    legs = _transit_legs(payload)

    conn = get_postgres_connection(args.database_url)
    repo = PostgresSourceRepository(
        conn,
        gtfs_schema=args.schema,
        gtfs_dataset_key=args.dataset_key,
    )
    try:
        routes = {str(row["route_id"]): row for row in repo.get_routes()}
        stops = {str(row["stop_id"]): row for row in repo.get_stops()}
        checks: list[dict[str, Any]] = []
        for leg in legs:
            feed_id, route_id = parse_otp_id(str(leg["route"]["gtfsId"]))
            _, trip_id = parse_otp_id(str(leg["trip"]["gtfsId"]))
            _, from_stop_id = parse_otp_id(str(leg["from"]["stop"]["gtfsId"]))
            _, to_stop_id = parse_otp_id(str(leg["to"]["stop"]["gtfsId"]))

            route = routes.get(route_id)
            trip = next(
                (row for row in repo.get_trips(route_id) if str(row["trip_id"]) == trip_id),
                None,
            )
            stop_times = repo.get_stop_times(trip_id)
            checks.append(
                {
                    "otp_feed_id": feed_id,
                    "otp_route_id": str(leg["route"]["gtfsId"]),
                    "persisted_route_id": route_id,
                    "route_match": route is not None,
                    "route_short_name": route.get("route_short_name") if route else None,
                    "otp_trip_id": str(leg["trip"]["gtfsId"]),
                    "persisted_trip_id": trip_id,
                    "trip_match": trip is not None,
                    "otp_from_stop_id": str(leg["from"]["stop"]["gtfsId"]),
                    "persisted_from_stop_id": from_stop_id,
                    "from_stop_match": from_stop_id in stops,
                    "from_stop_name": stops[from_stop_id]["stop_name"]
                    if from_stop_id in stops
                    else None,
                    "otp_to_stop_id": str(leg["to"]["stop"]["gtfsId"]),
                    "persisted_to_stop_id": to_stop_id,
                    "to_stop_match": to_stop_id in stops,
                    "to_stop_name": stops[to_stop_id]["stop_name"]
                    if to_stop_id in stops
                    else None,
                    "stop_times_count": len(stop_times),
                    "first_stop_time": stop_times[0] if stop_times else None,
                    "last_stop_time": stop_times[-1] if stop_times else None,
                    "otp_start": (leg.get("start") or {}).get("scheduledTime"),
                    "otp_end": (leg.get("end") or {}).get("scheduledTime"),
                }
            )
        print(json.dumps(checks, indent=2, ensure_ascii=False, default=str))
        return 0 if all(
            check["route_match"] and check["trip_match"] and check["from_stop_match"]
            and check["to_stop_match"]
            for check in checks
        ) else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
