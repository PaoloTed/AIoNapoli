#!/usr/bin/env python3
"""Reproducible ANM/EAV checkpoint probe against OTP 2.10 GTFS GraphQL.

It never assumes feed IDs: feeds and agencies are read from the running graph.
Coordinates are documented in ``docs/reports/checkpoint-anm-routing.md``.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8081/otp/gtfs/v1"
DEPARTURE = "2026-11-16T08:00:00+01:00"
CASES = {
    "campano-cds": {
        "origin": (40.8943044, 14.2308735),
        "destination": (40.8047221, 14.1745403),
    },
    "chiaiano-cds": {
        "origin": (40.8909784539278, 14.2235637886917),
        "destination": (40.8047221, 14.1745403),
    },
}


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
    first: int = 5,
    transit_only: bool = True,
) -> str:
    direct_modes = "[]" if transit_only else "[WALK]"
    transit_only_arg = ", transitOnly: true" if transit_only else ""
    return f"""query {{
  planConnection(
    origin: {{ location: {{ coordinate: {{
      latitude: {origin[0]}, longitude: {origin[1]}
    }} }} }}
    destination: {{ location: {{ coordinate: {{
      latitude: {destination[0]}, longitude: {destination[1]}
    }} }} }}
    dateTime: {{ earliestDeparture: "{DEPARTURE}" }}
    first: {first}
    modes: {{ direct: {direct_modes}, transit: {{ transit: [
      {{ mode: SUBWAY }}, {{ mode: BUS }}, {{ mode: RAIL }}
    ] }}{transit_only_arg} }}
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
          route {{
            gtfsId shortName longName mode
            agency {{ gtfsId name }}
          }}
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)

    feeds = gql(args.base_url, "{ feeds { feedId } }", args.artifacts / "feeds.json")
    print("feeds", [feed["feedId"] for feed in feeds["data"]["feeds"]])
    routes = gql(
        args.base_url,
        "{ routes { gtfsId shortName longName mode agency { gtfsId name } } }",
        args.artifacts / "routes.json",
    )["data"]["routes"]
    targets = [route for route in routes if route["shortName"] in {"L1", "R7", "C1", "2"}]
    (args.artifacts / "target-routes.json").write_text(
        json.dumps(targets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for route in targets:
        print(
            "route",
            route["gtfsId"],
            route["shortName"],
            route["mode"],
            (route.get("agency") or {}).get("name"),
        )

    for name, case in CASES.items():
        for transit_only in (False, True):
            key = f"{name}-transitOnly-{str(transit_only).lower()}"
            data = gql(
                args.base_url,
                plan_query(
                    origin=case["origin"],
                    destination=case["destination"],
                    transit_only=transit_only,
                ),
                args.artifacts / f"routing-{key}.json",
            )
            connection = data["data"]["planConnection"]
            print(
                key,
                "itineraries",
                len(connection["edges"]),
                "errors",
                connection["routingErrors"],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
