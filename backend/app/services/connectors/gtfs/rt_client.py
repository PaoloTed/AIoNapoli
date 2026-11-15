"""GTFS-Realtime HTTP client with ETag polling, configured headers, and safe fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.services.connectors.gtfs.rt_parser import parse_trip_updates, parse_vehicle_positions


@dataclass(frozen=True)
class GtfsRtFetchResult:
    positions: list[dict[str, Any]]
    trip_updates: list[dict[str, Any]]
    is_simulated: bool
    outcome: str
    detail: str
    etag: str | None = None


class GtfsRtClient:
    """Acquires GTFS-Realtime JSON feeds using identification headers from configuration."""

    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        timeout_s: float = 10.0,
        primary_source_id: str = "anm",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Identification headers must always come from configuration (REQ-CONN-09)
        self._headers = {k: v for k, v in headers.items() if v}
        self._timeout_s = timeout_s
        self._primary_source_id = primary_source_id
        self._http_client = http_client
        self._etags: dict[str, str] = {}

    def _get_json(self, endpoint_path: str) -> tuple[int, Any | None, str | None]:
        url = f"{self._base_url}{endpoint_path}"
        req_headers = dict(self._headers)
        if endpoint_path in self._etags:
            req_headers["If-None-Match"] = self._etags[endpoint_path]

        if self._http_client is not None:
            resp = self._http_client.get(url, headers=req_headers, timeout=self._timeout_s)
        else:
            with httpx.Client(timeout=self._timeout_s) as client:
                resp = client.get(url, headers=req_headers)

        if resp.status_code == 304:
            return 304, None, self._etags.get(endpoint_path)
        resp.raise_for_status()
        etag = resp.headers.get("ETag")
        if etag:
            self._etags[endpoint_path] = etag
        if not resp.content or not resp.content.strip():
            return resp.status_code, [], etag
        return resp.status_code, resp.json(), etag

    def fetch_status(self) -> dict[str, Any]:
        """Query /anm/status diagnostic endpoint."""
        status_path = "/status" if self._base_url.endswith("/anm") else "/anm/status"
        _, payload, _ = self._get_json(status_path)
        return payload if isinstance(payload, dict) else {"raw": payload}

    def fetch(self, *, now: datetime | None = None) -> GtfsRtFetchResult:
        """Fetch vehicle positions and trip updates, degrading gracefully on network error."""
        ref_now = now or datetime.now(timezone.utc)
        vp_path = "/gtfs-rt/vehicle-positions.json"
        tu_path = "/gtfs-rt/trip-updates.json"
        vp_url = f"{self._base_url}{vp_path}"
        tu_url = f"{self._base_url}{tu_path}"

        try:
            vp_status, vp_payload, vp_etag = self._get_json(vp_path)
            positions: list[dict[str, Any]] = []
            if vp_status != 304 and vp_payload is not None:
                positions = parse_vehicle_positions(
                    vp_payload,
                    proxy_url=vp_url,
                    primary_source_id=self._primary_source_id,
                    is_simulated=False,
                    now=ref_now,
                )

            trip_updates: list[dict[str, Any]] = []
            try:
                tu_status, tu_payload, _ = self._get_json(tu_path)
                if tu_status != 304 and tu_payload is not None:
                    trip_updates = parse_trip_updates(
                        tu_payload,
                        proxy_url=tu_url,
                        primary_source_id=self._primary_source_id,
                        is_simulated=False,
                        now=ref_now,
                    )
            except httpx.HTTPStatusError as tu_exc:
                # If trip-updates isn't published by mock/server (404), keep empty updates
                if tu_exc.response.status_code != 404:
                    raise

            detail = "empty_response" if not positions and not trip_updates else "rt_ok"
            return GtfsRtFetchResult(
                positions=positions,
                trip_updates=trip_updates,
                is_simulated=False,
                outcome="ok",
                detail=detail,
                etag=vp_etag,
            )
        except Exception as exc:
            return self.fallback_payload(
                reason=f"proxy_non_raggiungibile:{type(exc).__name__}",
                now=ref_now,
            )

    def fallback_payload(
        self,
        *,
        reason: str = "fallback_simulato",
        now: datetime | None = None,
    ) -> GtfsRtFetchResult:
        """Load simulated GTFS-RT fixture positions with is_simulated=True."""
        ref_now = now or datetime.now(timezone.utc)
        repo_root = Path(__file__).resolve().parents[5]
        sample_path = repo_root / "shared" / "mocks" / "gtfs_rt_sample.json"
        vp_url = f"{self._base_url}/gtfs-rt/vehicle-positions.json"
        if sample_path.exists():
            payload = json.loads(sample_path.read_text(encoding="utf-8"))
            positions = parse_vehicle_positions(
                payload,
                proxy_url=vp_url,
                primary_source_id=self._primary_source_id,
                is_simulated=True,
                now=ref_now,
            )
            # Refresh observed_at to current clock in simulated fallback
            for row in positions:
                row["observed_at"] = ref_now.isoformat()
        else:
            positions = [
                {
                    "vehicle_id": "ANM-SIM-01",
                    "route_id": "R2",
                    "trip_id": "TRIP_R2_01",
                    "observed_at": ref_now.isoformat(),
                    "latitude": 40.8206,
                    "longitude": 14.1785,
                    "bearing": 214.5,
                    "speed_mps": 5.5,
                    "zone_id": "Z_BAGNOLI",
                    "source_id": self._primary_source_id,
                    "data_reference": f"fallback:{vp_url}?ts={ref_now.isoformat()}",
                    "is_simulated": True,
                    "ingested_at": ref_now.isoformat(),
                }
            ]
        return GtfsRtFetchResult(
            positions=positions,
            trip_updates=[],
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )
