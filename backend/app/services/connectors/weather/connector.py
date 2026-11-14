"""Weather connector normalizing Open-Meteo / ARPA Campania snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.repositories.base import SourceRepository
from app.services.connectors.base import ConnectorOutcome


class WeatherConnector:
    """Ingests weather forecasts into weather_snapshots with simulated fallback."""

    source_id: str = "open_meteo"
    frequency: str = "oraria"

    def __init__(
        self,
        repository: SourceRepository,
        *,
        endpoint_url: str = "",
        timeout_s: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._repo = repository
        self._endpoint_url = endpoint_url
        self._timeout_s = timeout_s
        self._client = client

    def run(self) -> ConnectorOutcome:
        if not self._endpoint_url:
            return self.fallback(reason="endpoint_meteo_non_configurato")

        started_at = datetime.now(timezone.utc)
        try:
            if self._client is not None:
                resp = self._client.get(self._endpoint_url, timeout=self._timeout_s)
            else:
                with httpx.Client(timeout=self._timeout_s) as client:
                    resp = client.get(self._endpoint_url)
            resp.raise_for_status()
            payload = resp.json()
            current = payload.get("current") or {}
            precip = float(current.get("precipitation", 0.0))
            alert_level = str(current.get("alert_level") or "verde")
            heavy_rain = alert_level in ("arancione", "rossa")
            forecast_at = str(current.get("time") or started_at.isoformat())
            row: dict[str, Any] = {
                "snapshot_at": started_at.isoformat(),
                "forecast_at": forecast_at,
                "zone_id": current.get("zone_id") or "Z_BAGNOLI",
                "precipitation_mm": precip,
                "alert_level": alert_level,
                "heavy_rain": heavy_rain,
                "expected_impact": current.get("expected_impact") or "dato meteo live",
                "source_id": self.source_id,
                "data_reference": self._endpoint_url,
                "is_simulated": False,
                "ingested_at": started_at.isoformat(),
            }
            written = self._repo.upsert_weather_snapshots([row])
            finished_at = datetime.now(timezone.utc)
            self._repo.record_ingestion_run(
                {
                    "connector": "weather",
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "rows_written": written,
                    "is_simulated": False,
                    "outcome": "ok",
                    "detail": "weather_ok",
                }
            )
            return ConnectorOutcome(
                connector="weather",
                source_id=self.source_id,
                rows_written=written,
                is_simulated=False,
                outcome="ok",
                detail="weather_ok",
            )
        except Exception as exc:
            return self.fallback(reason=f"meteo_non_raggiungibile:{type(exc).__name__}")

    def fallback(self, reason: str = "manual_fallback") -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        rows: list[dict[str, Any]] = [
            {
                "snapshot_at": started_at.isoformat(),
                "forecast_at": "2026-11-14T17:00:00+00:00",
                "zone_id": "Z_BAGNOLI",
                "precipitation_mm": 34.0,
                "alert_level": "arancione",
                "heavy_rain": True,
                "expected_impact": "Pioggia intensa pomeridiana su fascia costiera",
                "source_id": self.source_id,
                "data_reference": "fallback:weather_simulated",
                "is_simulated": True,
                "ingested_at": started_at.isoformat(),
            }
        ]
        written = self._repo.upsert_weather_snapshots(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "weather",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "fallback",
                "detail": reason,
            }
        )
        return ConnectorOutcome(
            connector="weather",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )

