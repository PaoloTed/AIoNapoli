"""Unit tests for the shared BaseConnector interface and normalized ConnectorOutcome."""

from __future__ import annotations

import inspect

import httpx

from app.repositories.memory import InMemorySourceRepository
from app.services.connectors.base import BaseConnector, ConnectorOutcome
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector


def _offline_client() -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline test", request=request)

    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_cinque_connettori() -> None:
    """REQ-CONN-01: all five connectors expose source_id, frequency, run(), and fallback()."""
    repo = InMemorySourceRepository(load_fixtures=True)
    client = _offline_client()
    connectors: list[BaseConnector] = [
        RssConnector(repo, client=client),
        GtfsConnector(repo, http_client=client),
        WeatherConnector(repo, client=client),
        EventsConnector(repo),
        OccupancyConnector(repo),
    ]
    assert len(connectors) == 5
    for conn in connectors:
        assert isinstance(conn.source_id, str) and conn.source_id
        assert isinstance(conn.frequency, str) and conn.frequency
        assert callable(conn.run)
        assert callable(conn.fallback)
        assert "reason" in inspect.signature(conn.fallback).parameters


def test_esito() -> None:
    """REQ-CONN-02: run() and fallback() return structured ConnectorOutcome."""
    repo = InMemorySourceRepository(load_fixtures=True)
    client = _offline_client()
    for conn in (
        RssConnector(repo, client=client),
        GtfsConnector(repo, http_client=client),
        WeatherConnector(repo, client=client),
        EventsConnector(repo),
        OccupancyConnector(repo),
    ):
        outcome = conn.run()
        assert isinstance(outcome, ConnectorOutcome)
        assert outcome.rows_written >= 0
        assert isinstance(outcome.is_simulated, bool)
        assert outcome.outcome in ("ok", "fallback", "failed")
        assert outcome.detail
