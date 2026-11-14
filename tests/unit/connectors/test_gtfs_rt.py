"""Unit tests for GTFS-Realtime client headers, provenance, and degraded proxy handling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.repositories.memory import InMemorySourceRepository
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.orchestrator.config import load_config


def test_header_identificativi(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-CONN-09: identification headers come from config, never hardcoded."""
    captured_headers: list[dict[str, str]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, json={"header": {"timestamp": 1763138388}, "entity": []})

    monkeypatch.setenv("RT_CLIENT_HEADER", "napoli-test-client-id")
    monkeypatch.setenv("RT_USE_HEADER", "nonprofit")
    cfg = load_config()

    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    conn = GtfsConnector(repo, config=cfg, http_client=client)
    conn.run(now=datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc))

    assert captured_headers
    assert captured_headers[0].get("x-busone-client") == "napoli-test-client-id"
    assert captured_headers[0].get("x-busone-use") == "nonprofit"


def test_fonte_primaria() -> None:
    """REQ-CONN-10: vehicle positions record primary source_id='anm' and proxy data_reference."""
    repo_root = Path(__file__).resolve().parents[3]
    vp_payload = json.loads(
        (repo_root / "shared" / "mocks" / "gtfs_rt_sample.json").read_text(encoding="utf-8")
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("vehicle-positions.json"):
            return httpx.Response(200, json=vp_payload)
        return httpx.Response(404, json={"detail": "not found"})

    now = datetime.fromtimestamp(1763138395, tz=timezone.utc)
    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    conn = GtfsConnector(
        repo,
        rt_base_url="https://proxy.example/anm",
        http_client=client,
    )
    outcome = conn.run(now=now)
    assert outcome.outcome == "ok"
    assert outcome.is_simulated is False
    assert outcome.rows_written == 2

    rows = repo.get_fresh_vehicle_positions(now=now)
    assert len(rows) == 2
    for row in rows:
        assert row["source_id"] == "anm"
        assert row["data_reference"].startswith(
            "https://proxy.example/anm/gtfs-rt/vehicle-positions.json?ts="
        )
        assert row["is_simulated"] is False


def test_fallback_proxy() -> None:
    """REQ-CONN-12: when proxy raises a network error, fallback writes is_simulated=True rows."""

    def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("proxy timeout", request=request)

    now = datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc)
    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    conn = GtfsConnector(repo, rt_base_url="https://proxy.example/anm", http_client=client)
    outcome = conn.run(now=now)

    assert outcome.outcome == "fallback"
    assert outcome.is_simulated is True
    assert outcome.rows_written > 0
    rows = repo.get_fresh_vehicle_positions(now=now)
    assert rows and all(r["is_simulated"] is True for r in rows)


def test_proxy_spento() -> None:
    """REQ-DEG-06: when RT proxy returns 503, connector degrades with is_simulated=True."""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="proxy down", request=request)

    now = datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc)
    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    conn = GtfsConnector(repo, rt_base_url="https://proxy.example/anm", http_client=client)
    outcome = conn.run(now=now)

    assert outcome.outcome == "fallback"
    assert outcome.is_simulated is True
    assert outcome.rows_written > 0


def test_risposta_vuota() -> None:
    """REQ-DEG-07: empty HTTP 200 RT response writes 0 rows and returns outcome='ok'."""

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"", request=request)

    now = datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc)
    repo = InMemorySourceRepository(load_fixtures=True)
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    conn = GtfsConnector(repo, rt_base_url="https://proxy.example/anm", http_client=client)
    outcome = conn.run(now=now)

    assert outcome.outcome == "ok"
    assert outcome.rows_written == 0
    assert outcome.detail == "empty_response"
    assert outcome.is_simulated is False
