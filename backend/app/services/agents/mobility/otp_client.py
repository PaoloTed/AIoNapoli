"""OpenTripPlanner GraphQL client with deterministic fixture fallback (D-08)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class ItineraryResult:
    duration_min: int
    legs: list[dict[str, Any]]
    is_simulated: bool
    source_id: str
    data_reference: str
    fallback_reason: str | None = None


def load_otp_fixture() -> dict[str, Any]:
    """Load recorded OTP itinerary response fixture from shared/mocks/otp_fixture.json."""
    repo_root = Path(__file__).resolve().parents[5]
    fixture_path = repo_root / "shared" / "mocks" / "otp_fixture.json"
    if fixture_path.exists():
        return json.loads(fixture_path.read_text(encoding="utf-8"))
    return {
        "plan": {
            "itineraries": [
                {
                    "duration": 1200,
                    "walkDistance": 420.0,
                    "legs": [
                        {"mode": "BUS", "route": "151", "duration": 900},
                        {"mode": "RAIL", "route": "CUMANA", "duration": 300},
                    ],
                }
            ]
        }
    }


class OtpClient:
    """Queries OpenTripPlanner GraphQL API and falls back to recorded fixture if offline."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8080",
        timeout_s: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._http_client = http_client

    def plan_itinerary(
        self,
        *,
        from_lat: float = 40.8522,
        from_lon: float = 14.2724,
        to_lat: float = 40.8165,
        to_lon: float = 14.1672,
    ) -> ItineraryResult:
        query = (
            "query Plan($fromLat: Float!, $fromLon: Float!, $toLat: Float!, $toLon: Float!) { "
            "plan(from: {lat: $fromLat, lon: $fromLon}, to: {lat: $toLat, lon: $toLon}) { "
            "itineraries { duration walkDistance legs { mode route duration } } } }"
        )
        endpoint = f"{self._base_url}/otp/routers/default/index/graphql"
        payload = {
            "query": query,
            "variables": {
                "fromLat": from_lat,
                "fromLon": from_lon,
                "toLat": to_lat,
                "toLon": to_lon,
            },
        }
        try:
            if self._http_client is not None:
                resp = self._http_client.post(endpoint, json=payload, timeout=self._timeout_s)
            else:
                with httpx.Client(timeout=self._timeout_s) as client:
                    resp = client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            itineraries = ((data.get("data") or {}).get("plan") or {}).get("itineraries") or []
            if not itineraries:
                raise ValueError("empty_otp_itineraries")
            best = itineraries[0]
            duration_min = max(1, round(int(best.get("duration", 1200)) / 60))
            return ItineraryResult(
                duration_min=duration_min,
                legs=list(best.get("legs") or []),
                is_simulated=False,
                source_id="otp",
                data_reference=endpoint,
                fallback_reason=None,
            )
        except Exception as exc:
            fixture = load_otp_fixture()
            itineraries = (fixture.get("plan") or {}).get("itineraries") or []
            best = itineraries[0] if itineraries else {"duration": 1200, "legs": []}
            duration_min = max(1, round(int(best.get("duration", 1200)) / 60))
            return ItineraryResult(
                duration_min=duration_min,
                legs=list(best.get("legs") or []),
                is_simulated=True,
                source_id="otp_fixture",
                data_reference="fixture:shared/mocks/otp_fixture.json",
                fallback_reason=f"otp_non_raggiungibile:{type(exc).__name__}",
            )

