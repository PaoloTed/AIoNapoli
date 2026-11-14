"""Events connector loading declared simulated geo-fenced urban events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.base import SourceRepository
from app.services.connectors.base import ConnectorOutcome


class EventsConnector:
    """Ingests declared simulated event dataset into events table."""

    source_id: str = "events_dataset"
    frequency: str = "giornaliera"

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def _simulated_rows(self, ingested_at: str) -> list[dict[str, Any]]:
        return [
            {
                "event_id": "EVT-BAGNOLI-AC-2026",
                "name": "Regata America's Cup - Bagnoli",
                "zone_id": "Z_BAGNOLI",
                "geofence": (
                    "POLYGON((14.155 40.808,14.178 40.808,"
                    "14.178 40.824,14.155 40.824,14.155 40.808))"
                ),
                "expected_attendance": 12000,
                "window_start": "2026-11-14T15:00:00+00:00",
                "window_end": "2026-11-14T21:00:00+00:00",
                "source_id": self.source_id,
                "data_reference": "dataset:events_simulated_bagnoli",
                "is_simulated": True,
                "ingested_at": ingested_at,
            }
        ]

    def run(self) -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        rows = self._simulated_rows(started_at.isoformat())
        written = self._repo.upsert_events(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "events",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "ok",
                "detail": "dataset_simulato_dichiarato",
            }
        )
        return ConnectorOutcome(
            connector="events",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="ok",
            detail="dataset_simulato_dichiarato",
        )

    def fallback(self, reason: str = "manual_fallback") -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        rows = self._simulated_rows(started_at.isoformat())
        for r in rows:
            r["is_simulated"] = True
        written = self._repo.upsert_events(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "events",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "fallback",
                "detail": reason,
            }
        )
        return ConnectorOutcome(
            connector="events",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )
