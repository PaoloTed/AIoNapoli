#!/usr/bin/env python3
"""Reproducible CHECKPOINT 1A/1B probe for the OTP 2.10.0 GTFS GraphQL API.

This script only talks to a running OTP instance. It does not modify the graph,
the repository or the GTFS feed. Requests and responses are written to the
artifact directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8080/otp/gtfs/v1"


def gql(base_url: str, query: str, path: Path) -> dict[str, Any]:
    payload_obj = {"query": query}
    payload = json.dumps(payload_obj).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_name(f"{path.stem}-request.json").write_text(
        json.dumps(payload_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    request = urllib.request.Request(
        base_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors in {path.name}: {data['errors']}")
    return data


def plan_query(
    *,
    origin: tuple[float, float],
    destination: tuple[float, float],
    departure: str,
    first: int,
    exclude_route: str | None = None,
    transit_only: bool = False,
) -> str:
    direct_modes = "[]" if transit_only else "[WALK]"
    transit_only_arg = ", transitOnly: true" if transit_only else ""
    filter_arg = ""
    if exclude_route:
        filter_arg = (
            ", preferences: { transit: { filters: [{ exclude: [{ routes: "
            f'["{exclude_route}"] }}] }}] }} }}'
        )
    return f"""query {{
  planConnection(
    origin: {{ location: {{ coordinate: {{
      latitude: {origin[0]}, longitude: {origin[1]}
    }} }} }}
    destination: {{ location: {{ coordinate: {{
      latitude: {destination[0]}, longitude: {destination[1]}
    }} }} }}
    dateTime: {{ earliestDeparture: "{departure}" }}
    first: {first}
    modes: {{ direct: {direct_modes}, transit: {{ transit: [
      {{ mode: BUS }}, {{ mode: RAIL }}
    ] }}{transit_only_arg} }}
    {filter_arg}
  ) {{
    edges {{
      node {{
        start
        end
        duration
        walkTime
        walkDistance
        numberOfTransfers
        generalizedCost
        legs {{
          mode
          transitLeg
          duration
          start {{ scheduledTime estimated {{ time delay }} }}
          end {{ scheduledTime estimated {{ time delay }} }}
          route {{ gtfsId shortName longName mode }}
          trip {{ gtfsId }}
          from {{ name lat lon stop {{ gtfsId name }} }}
          to {{ name lat lon stop {{ gtfsId name }} }}
          legGeometry {{ points length }}
        }}
      }}
    }}
    routingErrors {{ code description inputField }}
  }}
}}"""


def plan_summary(data: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    connection = (data.get("data") or {}).get("planConnection") or {}
    edges = connection.get("edges") or []
    route_ids: list[str] = []
    modes: list[str] = []
    for edge in edges:
        for leg in edge["node"].get("legs") or []:
            modes.append(str(leg.get("mode")))
            route = leg.get("route") or {}
            if route.get("gtfsId"):
                route_ids.append(str(route["gtfsId"]))
    errors = [
        str(error.get("code"))
        for error in (connection.get("routingErrors") or [])
        if error.get("code")
    ]
    return len(edges), route_ids, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path("artifacts"),
        help="Directory where request/response JSON files are written",
    )
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)

    feeds = gql(args.base_url, "{ feeds { feedId } }", args.artifacts / "feeds.json")
    feed_ids = [str(feed["feedId"]) for feed in feeds["data"]["feeds"]]
    if not feed_ids:
        raise RuntimeError("OTP returned no feeds")
    feed_id = feed_ids[0]

    routes_data = gql(
        args.base_url,
        "{ routes { gtfsId shortName longName mode } }",
        args.artifacts / "routes.json",
    )
    routes = routes_data["data"]["routes"]
    by_short: dict[str, list[str]] = {}
    for route in routes:
        by_short.setdefault(str(route["shortName"]), []).append(str(route["gtfsId"]))

    def unique_route(short_name: str) -> str:
        matches = by_short.get(short_name, [])
        if len(matches) != 1:
            raise RuntimeError(
                f"route shortName={short_name!r} is not unique in this feed: {matches}"
            )
        return matches[0]

    route_2 = unique_route("2")
    route_1 = unique_route("1")
    route_1_dot = unique_route("1.")
    route_4 = unique_route("4")

    departure = "2026-11-16T08:00:00+01:00"
    case_a_origin = (40.892929, 14.239837)  # Piscinola Scampia
    case_a_destination = (40.974147, 14.213685)  # Aversa

    baseline_a = gql(
        args.base_url,
        plan_query(
            origin=case_a_origin,
            destination=case_a_destination,
            departure=departure,
            first=5,
            transit_only=True,
        ),
        args.artifacts / "baseline-a.json",
    )
    n_a, routes_a, errors_a = plan_summary(baseline_a)
    if n_a == 0 or route_2 not in routes_a:
        raise RuntimeError(
            f"baseline A has no transit itinerary with {route_2}: {routes_a}"
        )
    if not any(route_id.startswith(f"{feed_id}:") for route_id in routes_a):
        raise RuntimeError(f"baseline A route IDs not feed-scoped: {routes_a}")

    excluded_a = gql(
        args.base_url,
        plan_query(
            origin=case_a_origin,
            destination=case_a_destination,
            departure=departure,
            first=5,
            exclude_route=route_2,
            transit_only=True,
        ),
        args.artifacts / "exclude-a.json",
    )
    n_ea, routes_ea, errors_ea = plan_summary(excluded_a)
    if route_2 in routes_ea:
        raise RuntimeError(f"excluded route {route_2} still present: {routes_ea}")

    case_b_origin = (40.851017, 14.272976)  # Napoli P. Garibaldi
    case_b_destination = (40.759526, 14.451518)  # Torre Annunziata - Oplonti
    baseline_b = gql(
        args.base_url,
        plan_query(
            origin=case_b_origin,
            destination=case_b_destination,
            departure=departure,
            first=8,
            transit_only=True,
        ),
        args.artifacts / "baseline-b.json",
    )
    n_b, routes_b, errors_b = plan_summary(baseline_b)
    if route_1 not in routes_b:
        raise RuntimeError(f"baseline B does not contain route 1: {routes_b}")

    excluded_b = gql(
        args.base_url,
        plan_query(
            origin=case_b_origin,
            destination=case_b_destination,
            departure=departure,
            first=8,
            exclude_route=route_1,
            transit_only=True,
        ),
        args.artifacts / "exclude-b.json",
    )
    n_eb, routes_eb, errors_eb = plan_summary(excluded_b)
    if route_1 in routes_eb:
        raise RuntimeError(f"excluded route {route_1} still present: {routes_eb}")
    if n_eb == 0 or not ({route_4, route_1_dot} & set(routes_eb)):
        raise RuntimeError(
            f"no transit alternative after excluding {route_1}: {routes_eb}"
        )

    summary = {
        "otp_base_url": args.base_url,
        "feed_id": feed_id,
        "route_ids": {
            "route_1": route_1,
            "route_1_dot": route_1_dot,
            "route_2": route_2,
            "route_4": route_4,
        },
        "case_a": {
            "baseline_itineraries": n_a,
            "baseline_transit_routes": routes_a,
            "baseline_routing_errors": errors_a,
            "excluded_itineraries": n_ea,
            "excluded_transit_routes": routes_ea,
            "excluded_routing_errors": errors_ea,
        },
        "case_b": {
            "baseline_itineraries": n_b,
            "baseline_transit_routes": routes_b,
            "baseline_routing_errors": errors_b,
            "excluded_itineraries": n_eb,
            "excluded_transit_routes": routes_eb,
            "excluded_routing_errors": errors_eb,
        },
    }
    (args.artifacts / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI error path
        print(f"PROBE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
