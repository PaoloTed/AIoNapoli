#!/usr/bin/env python3
"""Verify OTP legs against the correct persisted GTFS dataset.

Unlike the single-feed verifier, this script does not assume that feed ``1``
is EAV. It reads the agencies exposed by each OTP feed, matches them to
``public.gtfs_datasets.agency_ids``, and only then resolves route/trip/stop
IDs in the corresponding schema.

Usage:
    python infra/otp/verify_multi_dataset_itinerary.py \
      --artifact /path/to/routing.json \
      --database-url postgresql://... \
      --datasets eav:gtfs_eav,anm:gtfs_anm
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.db.session import get_postgres_connection
from app.repositories.postgres import PostgresSourceRepository
from app.services.agents.mobility.gtfs_ids import parse_otp_id


def _parse_datasets(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        key, schema = token.split(":", 1)
        pairs.append((key.strip(), schema.strip()))
    return pairs


def _all_edges(payload: dict[str, Any]) -> list[dict[str, Any]]:
    connection = (payload.get("data") or {}).get("planConnection") or {}
    edges = connection.get("edges") or []
    if not edges:
        raise SystemExit("artifact senza itinerari")
    return edges


def _feed_agencies(edges: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for edge in edges:
        for leg in (edge.get("node") or {}).get("legs") or []:
            route = leg.get("route") or {}
            route_gtfs_id = route.get("gtfsId")
            agency_gtfs_id = (route.get("agency") or {}).get("gtfsId")
            if not route_gtfs_id or not agency_gtfs_id:
                continue
            feed_id, _ = parse_otp_id(str(route_gtfs_id))
            _, agency_id = parse_otp_id(str(agency_gtfs_id))
            result.setdefault(feed_id, set()).add(agency_id)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--datasets", required=True, help="key:schema,key:schema")
    args = parser.parse_args()

    payload = json.loads(args.artifact.read_text(encoding="utf-8"))
    edges = _all_edges(payload)
    feed_agencies = _feed_agencies(edges)

    conn = get_postgres_connection(args.database_url)
    repo = PostgresSourceRepository(conn, gtfs_datasets=_parse_datasets(args.datasets))
    try:
        infos = {info["dataset_key"]: info for info in repo.get_datasets_info()}
        by_agency: dict[str, set[str]] = {}
        for key, info in infos.items():
            for agency_id in str(info["agency_ids"]).split(","):
                if agency_id.strip():
                    by_agency.setdefault(agency_id.strip(), set()).add(key)

        feed_to_dataset: dict[str, str] = {}
        for feed_id, agencies in feed_agencies.items():
            candidates: set[str] = set()
            for agency_id in agencies:
                candidates.update(by_agency.get(agency_id, set()))
            if len(candidates) != 1:
                raise SystemExit(
                    f"feed OTP {feed_id}: impossibile mappare agencies={sorted(agencies)} "
                    f"su un solo dataset (candidati={sorted(candidates)})"
                )
            feed_to_dataset[feed_id] = candidates.pop()

        routes = {
            (row["dataset_key"], str(row["gtfs_route_id"])): row for row in repo.get_routes()
        }
        stops = {
            (row["dataset_key"], str(row["gtfs_stop_id"])): row for row in repo.get_stops()
        }
        checks: list[dict[str, Any]] = []
        for edge in edges:
            for leg in (edge.get("node") or {}).get("legs") or []:
                if not leg.get("transitLeg"):
                    continue
                route_gtfs = str(leg["route"]["gtfsId"])
                trip_gtfs = str(leg["trip"]["gtfsId"])
                from_gtfs = str(leg["from"]["stop"]["gtfsId"])
                to_gtfs = str(leg["to"]["stop"]["gtfsId"])
                feed_id, route_id = parse_otp_id(route_gtfs)
                _, trip_id = parse_otp_id(trip_gtfs)
                _, from_stop_id = parse_otp_id(from_gtfs)
                _, to_stop_id = parse_otp_id(to_gtfs)
                dataset_key = feed_to_dataset.get(feed_id)
                if dataset_key is None:
                    raise SystemExit(f"feed OTP {feed_id} senza mapping dataset")

                route = routes.get((dataset_key, route_id))
                trips = repo.get_trips(f"{dataset_key}:{route_id}")
                trip = next(
                    (row for row in trips if str(row["gtfs_trip_id"]) == trip_id), None
                )
                from_stop = stops.get((dataset_key, from_stop_id))
                to_stop = stops.get((dataset_key, to_stop_id))
                stop_times = repo.get_stop_times(f"{dataset_key}:{trip_id}")
                from_time = next(
                    (
                        row
                        for row in stop_times
                        if str(row["gtfs_stop_id"]) == from_stop_id
                    ),
                    None,
                )
                to_time = next(
                    (
                        row
                        for row in stop_times
                        if str(row["gtfs_stop_id"]) == to_stop_id
                    ),
                    None,
                )
                otp_start = (leg.get("start") or {}).get("scheduledTime") or ""
                otp_end = (leg.get("end") or {}).get("scheduledTime") or ""
                checks.append(
                    {
                        "otp_feed_id": feed_id,
                        "dataset_key": dataset_key,
                        "operator": infos[dataset_key]["operator_name"],
                        "otp_route_id": route_gtfs,
                        "persisted_route_id": route_id,
                        "route_match": route is not None,
                        "route_short_name": route.get("route_short_name") if route else None,
                        "otp_trip_id": trip_gtfs,
                        "persisted_trip_id": trip_id,
                        "trip_match": trip is not None,
                        "otp_from_stop_id": from_gtfs,
                        "persisted_from_stop_id": from_stop_id,
                        "from_stop_match": from_stop is not None,
                        "from_stop_name": from_stop["stop_name"] if from_stop else None,
                        "otp_to_stop_id": to_gtfs,
                        "persisted_to_stop_id": to_stop_id,
                        "to_stop_match": to_stop is not None,
                        "to_stop_name": to_stop["stop_name"] if to_stop else None,
                        "stop_times_count": len(stop_times),
                        "from_departure": from_time.get("departure_time")
                        if from_time
                        else None,
                        "to_arrival": to_time.get("arrival_time") if to_time else None,
                        "otp_start": otp_start,
                        "otp_end": otp_end,
                        "departure_time_match": bool(
                            from_time
                            and otp_start[11:19] == from_time.get("departure_time")
                        ),
                        "arrival_time_match": bool(
                            to_time and otp_end[11:19] == to_time.get("arrival_time")
                        ),
                    }
                )

        report = {
            "feed_to_dataset": feed_to_dataset,
            "feed_agencies": {key: sorted(value) for key, value in feed_agencies.items()},
            "datasets": {
                key: {
                    "operator_name": info["operator_name"],
                    "agency_ids": info["agency_ids"],
                    "gtfs_schema": info["gtfs_schema"],
                    "source_sha256": info["source_sha256"],
                }
                for key, info in infos.items()
            },
            "checks": checks,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        required = (
            "route_match",
            "trip_match",
            "from_stop_match",
            "to_stop_match",
            "departure_time_match",
            "arrival_time_match",
        )
        return 0 if all(all(check[name] for name in required) for check in checks) else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
