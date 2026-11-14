"""End-to-end offline execution and network-isolation verification tests."""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cli import main as cli_main
from app.domain.models.finding import Finding
from app.main import create_app
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.context.agent import ContextAgent
from app.services.agents.crowding.agent import CrowdingAgent
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import OtpClient
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector
from app.services.facade import BackendService
from app.services.orchestrator.pipeline import run_pipeline
from app.utils.clock import FixedClock


def test_senza_rete(capsys: pytest.CaptureFixture[str], fixed_clock: FixedClock) -> None:
    """REQ-DEG-01: full demo and connector-to-decision flow run offline without network access."""
    exit_code = cli_main(["demo", "--scenario", "bagnoli", "--profile", "memory"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"decision_id"' in captured.out

    # Full HTTP API demo flow offline
    app = create_app(service=BackendService(clock=fixed_clock))
    with TestClient(app) as client:
        r1 = client.post("/api/v1/decision", json={"scenario_id": "bagnoli"})
        assert r1.status_code == 200
        r2 = client.get("/api/v1/scenario/bagnoli/stream")
        assert r2.status_code == 200

    # Full degraded ingestion -> agents -> orchestrator pipeline offline
    repo = InMemorySourceRepository(load_fixtures=True)
    offline_http = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(httpx.ConnectError("offline", request=req))
        )
    )
    GtfsConnector(repo, http_client=offline_http).run_static()
    RssConnector(repo, client=offline_http).fallback()
    GtfsConnector(repo, http_client=offline_http).fallback(now=fixed_clock.now())
    WeatherConnector(repo, client=offline_http).fallback()
    EventsConnector(repo).run()
    OccupancyConnector(repo).run()

    otp = OtpClient(base_url="http://127.0.0.1:59999", http_client=offline_http)
    findings = [
        MobilityAgent(repo, otp_client=otp).evaluate(route_id="L2", now=fixed_clock.now()),
        CrowdingAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=fixed_clock.now()),
        ContextAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=fixed_clock.now()),
    ]
    assert all(isinstance(f, Finding) for f in findings)
    out = run_pipeline(findings, BackendService().config, clock=fixed_clock)
    assert out.decision_id


def test_rete_inibita() -> None:
    """NFR-08: network marker is disabled and INET sockets are blocked by default in pytest."""
    repo_root = Path(__file__).resolve().parents[2]
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = pyproject["tool"]["pytest"]["ini_options"]["addopts"]
    assert "not network" in addopts
    assert "--disable-socket" in addopts

    # Attempting to open a real INET socket must be blocked by pytest-socket
    with pytest.raises(Exception) as exc_info:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("1.1.1.1", 80))
    assert (
        "socket" in type(exc_info.value).__name__.lower()
        or "network" in str(exc_info.value).lower()
    )
