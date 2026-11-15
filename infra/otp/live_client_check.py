#!/usr/bin/env python3
"""Explicit live check of the implemented OTP client against a running OTP 2.10.

This is intentionally separate from the offline pytest suite. It uses the real
network only for the configured local OTP endpoint and writes a JSON summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.agents.mobility.otp_client import OtpClient  # noqa: E402


def gql(base_url: str, query: str) -> dict[str, Any]:
    response = httpx.post(
        f"{base_url.rstrip('/')}/otp/gtfs/v1",
        json={"query": query},
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body


def route_ids(plan: Any) -> list[str]:
    return [
        leg["route_id"]
        for itinerary in plan.itineraries
        for leg in itinerary.legs
        if leg.get("route_id")
    ]


def summarize(plan: Any) -> dict[str, Any]:
    return {
        "itineraries": len(plan.itineraries),
        "route_ids": route_ids(plan),
        "routing_errors": plan.routing_errors,
        "is_simulated": plan.is_simulated,
        "source_id": plan.source_id,
        "first_start": plan.itineraries[0].start if plan.itineraries else None,
        "first_duration_s": plan.itineraries[0].duration_s if plan.itineraries else None,
        "first_trip_id": (
            plan.itineraries[0].legs[0].get("trip_id") if plan.itineraries else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("live-client-check.json"),
    )
    args = parser.parse_args()

    routes = gql(
        args.base_url,
        "{ routes { gtfsId shortName longName mode } }",
    )["data"]["routes"]
    known = {str(route["gtfsId"]) for route in routes}
    required = {"1:1", "1:1.", "1:2", "1:4"}
    missing = required - known
    if missing:
        raise RuntimeError(f"route IDs feed-scoped mancanti nel feed live: {sorted(missing)}")

    client = OtpClient(
        base_url=args.base_url,
        timeout_s=10,
        mode="real",
        timezone="Europe/Rome",
    )
    common = {
        "from_lat": 40.851017,
        "from_lon": 14.272976,
        "to_lat": 40.759526,
        "to_lon": 14.451518,
        "depart_at": datetime(2026, 11, 16, 8, 0, tzinfo=ZoneInfo("Europe/Rome")),
        "first": 8,
        "modes": ("WALK", "BUS", "RAIL"),
        "transit_only": True,
    }
    baseline = client.plan_itineraries(**common)
    excluded = client.plan_itineraries(**common, exclude_route_ids=("1:1",))

    baseline_routes = route_ids(baseline)
    excluded_routes = route_ids(excluded)
    if "1:1" not in baseline_routes:
        raise RuntimeError(f"baseline senza 1:1: {baseline_routes}")
    if "1:1" in excluded_routes:
        raise RuntimeError(f"route esclusa ancora presente: {excluded_routes}")
    if not ({"1:4", "1:1."} & set(excluded_routes)):
        raise RuntimeError(f"nessuna alternativa rail attesa: {excluded_routes}")
    if baseline.is_simulated or excluded.is_simulated:
        raise RuntimeError("un risultato live non deve essere simulato")

    summary = {
        "base_url": args.base_url,
        "parameters": {
            "date": common["depart_at"].isoformat(),
            "origin": [common["from_lat"], common["from_lon"]],
            "destination": [common["to_lat"], common["to_lon"]],
            "first": common["first"],
            "modes": list(common["modes"]),
            "transit_only": common["transit_only"],
            "exclusion": ["1:1"],
        },
        "baseline": summarize(baseline),
        "excluded": summarize(excluded),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
