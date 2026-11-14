"""Contract tests ensuring every specialized agent returns Finding | Refusal."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import Finding
from app.domain.models.refusal import Refusal
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


def test_finding_o_refusal() -> None:
    """REQ-AGT-01: all three agents always return Finding or Refusal without raising."""
    now = datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc)

    # Empty repository -> Refusals
    empty_repo = InMemorySourceRepository(load_fixtures=False)
    otp = OtpClient(base_url="http://127.0.0.1:59999", timeout_s=0.05)
    for out in (
        MobilityAgent(empty_repo, otp_client=otp).evaluate(route_id="L2", now=now),
        CrowdingAgent(empty_repo).evaluate(zone_id="Z_BAGNOLI", now=now),
        ContextAgent(empty_repo).evaluate(zone_id="Z_BAGNOLI", now=now),
    ):
        assert isinstance(out, Refusal)
        assert out.reason_code

    # Populated fallback repository -> Findings
    repo = InMemorySourceRepository(load_fixtures=True)
    RssConnector(repo).fallback()
    GtfsConnector(repo).fallback(now=now)
    WeatherConnector(repo).fallback()
    EventsConnector(repo).run()
    OccupancyConnector(repo).run()

    for out in (
        MobilityAgent(repo, otp_client=otp).evaluate(route_id="L2", now=now),
        CrowdingAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=now),
        ContextAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=now),
    ):
        assert isinstance(out, Finding)

