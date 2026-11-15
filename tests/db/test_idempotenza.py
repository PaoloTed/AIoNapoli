"""Idempotency tests verifying double connector ingestion produces zero duplicate rows."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection
from app.repositories.memory import InMemorySourceRepository
from app.repositories.postgres import PostgresSourceRepository
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector


def _run_all_connectors(
    repo: InMemorySourceRepository | PostgresSourceRepository,
    now: datetime,
) -> None:
    offline_http = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(httpx.ConnectError("offline", request=req))
        )
    )
    GtfsConnector(repo, http_client=offline_http).run_static()
    RssConnector(repo, client=offline_http).fallback()
    GtfsConnector(repo, http_client=offline_http).fallback(now=now)
    WeatherConnector(repo, client=offline_http).fallback()
    EventsConnector(repo).run()
    OccupancyConnector(repo).run()


def test_doppia_ingestion() -> None:
    """REQ-PER-05: running connectors twice produces identical row counts without duplicates."""
    now = datetime(2026, 11, 14, 17, 40, 0, tzinfo=timezone.utc)

    conn = get_sqlite_connection(":memory:")
    try:
        apply_migrations(conn)
        sql_repo = PostgresSourceRepository(conn)
        mem_repo = InMemorySourceRepository(load_fixtures=True)

        for repo in (mem_repo, sql_repo):
            _run_all_connectors(repo, now)
            counts_1 = (
                len(repo.get_zones()),
                len(repo.get_stops()),
                len(repo.get_routes()),
                len(repo.get_active_service_alerts()),
                len(repo.get_events()),
                len(repo.get_latest_weather()),
                len(repo.get_latest_occupancy()),
                len(repo.get_fresh_vehicle_positions(now=now)),
            )

            _run_all_connectors(repo, now)
            counts_2 = (
                len(repo.get_zones()),
                len(repo.get_stops()),
                len(repo.get_routes()),
                len(repo.get_active_service_alerts()),
                len(repo.get_events()),
                len(repo.get_latest_weather()),
                len(repo.get_latest_occupancy()),
                len(repo.get_fresh_vehicle_positions(now=now)),
            )
            assert counts_1 == counts_2
            assert all(c > 0 for c in counts_1)
    finally:
        conn.close()
