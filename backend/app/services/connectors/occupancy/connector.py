"""Occupancy connector producing normalized occupancy_estimates rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.base import SourceRepository
from app.services.connectors.base import ConnectorOutcome


class OccupancyConnector:
    """Ingests simulated IR/APC occupancy estimates into occupancy_estimates."""

    source_id: str = "ir_sensors"
    frequency: str = "simulata"

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def _simulated_rows(self, ingested_at: str) -> list[dict[str, Any]]:
        return [
            {
                "vehicle_id": "ANM-2231",
                "line": "R2",
                "occupancy_pct": 91.0,
                "observed_at": "2026-11-14T17:40:00+00:00",
                "source_id": self.source_id,
                "data_reference": "occupancy:ir_simulated_bagnoli",
                "is_simulated": True,
                "ingested_at": ingested_at,
            }
        ]

    def run(self) -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        rows = self._simulated_rows(started_at.isoformat())
        written = self._repo.upsert_occupancy_estimates(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "occupancy",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "ok",
                "detail": "occupancy_simulata_dichiarata",
            }
        )
        return ConnectorOutcome(
            connector="occupancy",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="ok",
            detail="occupancy_simulata_dichiarata",
        )

    def fallback(self, reason: str = "manual_fallback") -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        rows = self._simulated_rows(started_at.isoformat())
        for r in rows:
            r["is_simulated"] = True
        written = self._repo.upsert_occupancy_estimates(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "occupancy",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "fallback",
                "detail": reason,
            }
        )
        return ConnectorOutcome(
            connector="occupancy",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )
