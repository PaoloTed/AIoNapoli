"""Unit tests verifying fallback rows consistently carry is_simulated=True."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.repositories.memory import InMemorySourceRepository
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector


def test_flag_coerente() -> None:
    """REQ-CONN-04: every connector in fallback mode persists rows with is_simulated=True."""
    now = datetime(2026, 11, 14, 17, 40, 0, tzinfo=timezone.utc)
    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(httpx.ConnectError("offline", request=req))
        )
    )

    outcomes = [
        RssConnector(repo, feed_url="https://example.invalid/rss", client=client).run(),
        GtfsConnector(repo, rt_base_url="https://example.invalid/anm", http_client=client).run(
            now=now
        ),
        WeatherConnector(repo, endpoint_url="https://example.invalid/weather", client=client).run(),
        EventsConnector(repo).fallback("test_fallback"),
        OccupancyConnector(repo).fallback("test_fallback"),
    ]
    assert all(o.is_simulated is True and o.outcome == "fallback" for o in outcomes)

    assert repo.get_active_service_alerts()
    assert all(r["is_simulated"] is True for r in repo.get_active_service_alerts())
    assert all(r["is_simulated"] is True for r in repo.get_fresh_vehicle_positions(now=now))
    assert all(r["is_simulated"] is True for r in repo.get_latest_weather())
    assert all(r["is_simulated"] is True for r in repo.get_events())
    assert all(r["is_simulated"] is True for r in repo.get_latest_occupancy())
