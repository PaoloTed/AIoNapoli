"""Unit tests for MobilityAgent refusals and offline OTP degradation."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.domain.models.finding import Finding
from app.domain.models.refusal import Refusal
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import OtpClient


def test_rifiuto_senza_gtfs() -> None:
    """REQ-AGT-02: missing GTFS routes triggers Refusal(reason_code='missing_gtfs')."""
    repo = InMemorySourceRepository(load_fixtures=False)
    agent = MobilityAgent(repo)
    res = agent.evaluate(route_id="L2")
    assert isinstance(res, Refusal)
    assert res.reason_code == "missing_gtfs"

    repo_with_fixtures = InMemorySourceRepository(load_fixtures=True)
    res_unknown_route = MobilityAgent(repo_with_fixtures).evaluate(route_id="L99")
    assert isinstance(res_unknown_route, Refusal)
    assert res_unknown_route.reason_code == "missing_gtfs"


def test_rifiuto_punto_non_mappato() -> None:
    """REQ-AGT-03: unmapped stop triggers Refusal(reason_code='unmapped_point')."""
    repo = InMemorySourceRepository(load_fixtures=True)
    agent = MobilityAgent(repo)
    res = agent.evaluate(route_id="L2", origin_stop_id="STOP_UNKNOWN")
    assert isinstance(res, Refusal)
    assert res.reason_code == "unmapped_point"


def test_otp_spento() -> None:
    """REQ-DEG-03: offline OTP falls back to fixture with is_simulated=True."""
    repo = InMemorySourceRepository(load_fixtures=True)

    def _failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OTP offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(_failing_handler))
    otp = OtpClient(base_url="http://localhost:8080", http_client=client)
    agent = MobilityAgent(repo, otp_client=otp)

    res = agent.evaluate(
        route_id="L2",
        origin_stop_id="STOP_GAR_01",
        destination_stop_id="STOP_BAG_01",
        now=datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc),
    )
    assert isinstance(res, Finding)
    assert res.is_simulated is True
    assert "fallback_reason" in res.content
