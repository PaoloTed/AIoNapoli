"""GTFS connector uniting static GTFS and GTFS-Realtime ingestion under one interface."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.domain.models.config import AppConfig
from app.repositories.base import SourceRepository
from app.services.connectors.base import ConnectorOutcome
from app.services.connectors.gtfs.client import GtfsStaticClient
from app.services.connectors.gtfs.rt_client import GtfsRtClient


class GtfsConnector:
    """Ingests static GTFS tables and GTFS-RT vehicle positions/trip updates."""

    source_id: str = "anm"
    frequency: str = "statico giornaliero, real-time circa 10 secondi"

    def __init__(
        self,
        repository: SourceRepository,
        *,
        config: AppConfig | None = None,
        rt_base_url: str = "https://proxy.busone.app/anm",
        headers: dict[str, str] | None = None,
        timeout_s: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._repo = repository
        if config is not None:
            effective_url = config.rt_base_url
            effective_timeout = config.rt_timeout_s
            effective_headers = {
                "X-BusOne-Client": config.rt_client_header,
                "X-BusOne-Use": config.rt_use_header,
            }
        else:
            effective_url = rt_base_url
            effective_timeout = timeout_s
            effective_headers = dict(headers or {})

        self._static = GtfsStaticClient(repository, source_id=self.source_id)
        self._rt = GtfsRtClient(
            base_url=effective_url,
            headers=effective_headers,
            timeout_s=effective_timeout,
            primary_source_id=self.source_id,
            http_client=http_client,
        )

    def fetch_status(self) -> dict[str, object]:
        return self._rt.fetch_status()

    def run_static(self) -> ConnectorOutcome:
        """Load the curated demo seed. This is the explicit demo/CLI path.

        The authoritative GTFS network is imported into its own schema by
        ``infra/postgres/import-gtfs.sh`` and read by the repository; this
        method must not be used to populate a real profile.
        """
        started_at = datetime.now(timezone.utc)
        rows_written = self._static.load_from_zones_seed()
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "gtfs",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": rows_written,
                "is_simulated": False,
                "outcome": "ok",
                "detail": "gtfs_static_demo_seed_ok",
            }
        )
        return ConnectorOutcome(
            connector="gtfs",
            source_id=self.source_id,
            rows_written=rows_written,
            is_simulated=False,
            outcome="ok",
            detail="gtfs_static_demo_seed_ok",
        )

    def run(self, *, mode: str = "rt", now: datetime | None = None) -> ConnectorOutcome:
        if mode == "static":
            return self.run_static()

        started_at = now or datetime.now(timezone.utc)
        # Do not seed demo network here: the real profile must use the GTFS
        # imported into its authoritative schema, never artificial zones.
        res = self._rt.fetch(now=started_at)
        written = 0
        if res.positions:
            written += self._repo.upsert_vehicle_positions(res.positions)
        if res.trip_updates:
            written += self._repo.upsert_trip_updates(res.trip_updates)

        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "gtfs-rt",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": res.is_simulated,
                "outcome": res.outcome,
                "detail": res.detail,
            }
        )
        return ConnectorOutcome(
            connector="gtfs-rt",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=res.is_simulated,
            outcome="fallback" if res.outcome == "fallback" else "ok",
            detail=res.detail,
        )

    def fallback(
        self, reason: str = "manual_fallback", now: datetime | None = None
    ) -> ConnectorOutcome:
        started_at = now or datetime.now(timezone.utc)
        res = self._rt.fallback_payload(reason=reason, now=started_at)
        written = self._repo.upsert_vehicle_positions(res.positions)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "gtfs-rt",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "fallback",
                "detail": reason,
            }
        )
        return ConnectorOutcome(
            connector="gtfs-rt",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )
